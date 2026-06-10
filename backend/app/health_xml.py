"""
Apple Health export.xml history backfill.

The Health app's "Export All Health Data" produces export.zip containing
export.xml — every Record ever written (often hundreds of MB). This module
stream-parses it and aggregates into the same daily tables the live
Health Auto Export push uses, so history and daily syncs line up.

De-duplication: Apple Health keeps overlapping records from multiple
sources (iPhone + Watch both count steps; several apps may write sleep).
Summing everything double-counts, so cumulative quantities are totalled
per (day, source) and the highest single source wins the day. Weight
takes the last reading of the day; nutrition keeps the single best source
per day (most calories logged, then most distinct fields).

Sleep night attribution: an interval belongs to the morning you woke up
from it — intervals ending at/after 18:00 are the pre-midnight chunk of
the *next* morning's night. (The live HAE push sends already-aggregated
nightly points, so the two paths agree except at pathological edges.)
"""
import logging
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import BinaryIO
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session as DBSession

from app.health_metrics import XML_DIETARY, convert_amount, upsert_nutrition_partial

logger = logging.getLogger(__name__)

STEP_TYPE = "HKQuantityTypeIdentifierStepCount"
WEIGHT_TYPE = "HKQuantityTypeIdentifierBodyMass"
SLEEP_TYPE = "HKCategoryTypeIdentifierSleepAnalysis"

# How many parse warnings to keep in the response before going quiet
_MAX_WARNINGS = 10


def _parse_dt(s: str) -> datetime:
    """export.xml datetimes look like '2024-01-15 08:30:00 +0100'."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")


def _night_of(end: datetime) -> date:
    """Attribute a sleep interval to the wake-up morning (see module doc)."""
    d = end.date()
    if end.hour >= 18:
        return d + timedelta(days=1)
    return d


def import_export_file(fileobj: BinaryIO, filename: str, db: DBSession) -> dict:
    """Parse an export.zip / export.xml stream and upsert daily rows."""
    if filename.lower().endswith(".zip") or zipfile.is_zipfile(fileobj):
        fileobj.seek(0)
        zf = zipfile.ZipFile(fileobj)
        xml_names = [n for n in zf.namelist() if n.endswith("export.xml")]
        if not xml_names:
            return {"status": "error", "detail": "No export.xml found inside the zip."}
        stream: BinaryIO = zf.open(xml_names[0])
    else:
        fileobj.seek(0)
        stream = fileobj

    # ---- Accumulators ----
    steps_by_day_source: dict[tuple[date, str], int] = defaultdict(int)
    weight_by_day: dict[date, tuple[datetime, float]] = {}  # latest reading wins
    sleep_acc: dict[tuple[date, str], dict[str, float]] = defaultdict(
        lambda: {"asleep": 0.0, "in_bed": 0.0, "deep": 0.0, "rem": 0.0, "core": 0.0}
    )
    diet_by_day_source: dict[tuple[date, str], dict[str, float]] = defaultdict(dict)
    ignored_types: set[str] = set()
    warnings: list[str] = []
    records_seen = 0

    def warn(msg: str) -> None:
        if len(warnings) < _MAX_WARNINGS:
            warnings.append(msg)

    context = ET.iterparse(stream, events=("start", "end"))
    _, root = next(context)  # grab the root so we can clear processed children

    for event, elem in context:
        if event != "end" or elem.tag != "Record":
            continue
        records_seen += 1
        rtype = elem.get("type", "")
        try:
            source = elem.get("sourceName", "unknown")

            if rtype == STEP_TYPE:
                start = _parse_dt(elem.get("startDate"))
                steps_by_day_source[(start.date(), source)] += int(float(elem.get("value", 0)))

            elif rtype == WEIGHT_TYPE:
                start = _parse_dt(elem.get("startDate"))
                raw = float(elem.get("value", 0))
                unit = (elem.get("unit") or "kg").lower()
                kg = raw * 0.453592 if unit in ("lb", "lbs") else raw / 1000 if unit == "g" else raw
                prev = weight_by_day.get(start.date())
                if prev is None or start >= prev[0]:
                    weight_by_day[start.date()] = (start, round(kg, 2))

            elif rtype == SLEEP_TYPE:
                start = _parse_dt(elem.get("startDate"))
                end = _parse_dt(elem.get("endDate"))
                minutes = (end - start).total_seconds() / 60
                if minutes > 0:
                    value = elem.get("value", "")
                    night = sleep_acc[(_night_of(end), source)]
                    if "InBed" in value:
                        night["in_bed"] += minutes
                    elif "Asleep" in value:
                        night["asleep"] += minutes
                        if "Deep" in value:
                            night["deep"] += minutes
                        elif "REM" in value:
                            night["rem"] += minutes
                        elif "Core" in value:
                            night["core"] += minutes

            elif rtype in XML_DIETARY:
                key = XML_DIETARY[rtype]
                start = _parse_dt(elem.get("startDate"))
                amount = convert_amount(float(elem.get("value", 0)), elem.get("unit", ""), key)
                if amount is None:
                    warn(f"{rtype}: unknown unit {elem.get('unit')!r}, skipped")
                else:
                    day_values = diet_by_day_source[(start.date(), source)]
                    day_values[key] = day_values.get(key, 0.0) + amount

            elif rtype:
                ignored_types.add(rtype)

        except Exception as e:
            warn(f"{rtype}: {e}")
        finally:
            elem.clear()
            root.clear()

    # ---- Finalize: best source per day, then upsert ----
    from app.routers.health import upsert_sleep, upsert_steps, upsert_weight

    created = 0

    best_steps: dict[date, int] = {}
    for (d, _src), total in steps_by_day_source.items():
        if total > best_steps.get(d, 0):
            best_steps[d] = total
    for d, steps in best_steps.items():
        created += upsert_steps(db, d, steps, "apple_health")

    for d, (_ts, kg) in weight_by_day.items():
        created += upsert_weight(db, d, kg, "apple_health")

    best_sleep: dict[date, dict[str, float]] = {}
    for (d, _src), v in sleep_acc.items():
        # Legacy records may only carry InBed — still worth keeping
        score = v["asleep"] or v["in_bed"]
        kept = best_sleep.get(d)
        if kept is None or score > (kept["asleep"] or kept["in_bed"]):
            best_sleep[d] = v
    for d, v in best_sleep.items():
        created += upsert_sleep(
            db, d,
            asleep_minutes=round(v["asleep"]),
            in_bed_minutes=round(v["in_bed"]),
            deep_minutes=round(v["deep"]) or None,
            rem_minutes=round(v["rem"]) or None,
            core_minutes=round(v["core"]) or None,
            source="apple_health",
        )

    best_diet: dict[date, dict[str, float]] = {}
    for (d, _src), values in diet_by_day_source.items():
        kept = best_diet.get(d)
        rank = (values.get("calories", 0.0), len(values))
        if kept is None or rank > (kept.get("calories", 0.0), len(kept)):
            best_diet[d] = values
    for d, values in best_diet.items():
        created += upsert_nutrition_partial(db, d, values, "apple_health")

    all_days = (
        list(best_steps) + list(weight_by_day) + list(best_sleep) + list(best_diet)
    )
    return {
        "status": "ok",
        "records_parsed": records_seen,
        "days": {
            "steps": len(best_steps),
            "weight": len(weight_by_day),
            "sleep": len(best_sleep),
            "nutrition": len(best_diet),
        },
        "rows_created": created,
        "date_range": {
            "from": min(all_days).isoformat() if all_days else None,
            "to": max(all_days).isoformat() if all_days else None,
        },
        "ignored_types": sorted(ignored_types)[:25],
        "warnings": warnings,
    }
