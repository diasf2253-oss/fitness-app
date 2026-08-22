"""
Apple Health ingest endpoints + health data read endpoints.

All health data — weight, steps, sleep, and nutrition including
micronutrients — arrives through Apple Health (YAZIO feeds it on-phone).

POST /api/ingest/health          — Health Auto Export JSON push (daily)
POST /api/ingest/health/shortcut — iOS Shortcut push (weight/steps/sleep)
POST /api/ingest/health-export   — export.zip/.xml upload (history backfill)
GET  /api/health/weight|steps|sleep|nutrition — date-range series
POST /api/health/weight|steps|sleep           — manual upserts

The Shortcut push and the export backfill share the validated ingest core in
app.health_ingest (HealthAggregator); the HAE push keeps its own inline
parsing for the wider nutrition/micronutrient payload.
"""
import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.health_metrics import HAE_NUTRITION, convert_amount, upsert_nutrition_partial
from app.models import NutritionDay, SleepLog, StepsLog, WeightLog
from app.schemas import (
    NutritionDayOut, SleepLogCreate, SleepLogOut,
    StepsLogCreate, StepsLogOut, WeightEstimateOut, WeightLogCreate, WeightLogOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# Non-authoritative weight sources: our own interpolated fills ('estimated')
# and dev/demo seed data ('sample'). Neither is a real tracked reading, so
# weight interpolation ignores them (a day carrying only one of these is
# treated as untracked and shown as an estimate), and neither may overwrite
# a real reading. Real sources today are 'manual' and 'apple_health'.
DERIVED_SOURCES = ("estimated", "sample")


# ---------------------------------------------------------------------------
# Upsert helpers — idempotent: re-sending the same data changes nothing.
#
# Source precedence: a day the user corrected by hand (source='manual') is
# only ever overwritten by another manual write — the correction exists
# precisely because the synced value was wrong. apple_health overwrites
# apple_health freely. A DERIVED_SOURCES write (interpolated estimate or
# demo seed) never buries a real reading, and any real reading overwrites
# derived data.
# Every writer funnels through these helpers, so the rule lives here only.
# ---------------------------------------------------------------------------

def _write_blocked(row, source: str) -> bool:
    """True when the existing row outranks this write and must be kept."""
    if row is None:
        return False
    # A hand correction is only overridden by another hand correction.
    if row.source == "manual" and source != "manual":
        return True
    # Derived data (estimate/demo) must never bury a real, tracked reading.
    if source in DERIVED_SOURCES and row.source not in DERIVED_SOURCES:
        return True
    return False


def upsert_weight(db: DBSession, day: date, weight_kg: float, source: str) -> bool:
    """Insert or update weight_log for a given date. Returns True if new row."""
    row = db.query(WeightLog).filter(WeightLog.date == day).first()
    if _write_blocked(row, source):
        return False
    if row:
        row.weight_kg = weight_kg
        row.source = source
        return False
    db.add(WeightLog(date=day, weight_kg=weight_kg, source=source))
    return True


def upsert_steps(db: DBSession, day: date, steps: int, source: str) -> bool:
    row = db.query(StepsLog).filter(StepsLog.date == day).first()
    if _write_blocked(row, source):
        return False
    if row:
        row.steps = steps
        row.source = source
        return False
    db.add(StepsLog(date=day, steps=steps, source=source))
    return True


def upsert_sleep(
    db: DBSession,
    day: date,
    asleep_minutes: int,
    in_bed_minutes: int,
    deep_minutes: Optional[int],
    rem_minutes: Optional[int],
    core_minutes: Optional[int],
    source: str,
) -> bool:
    row = db.query(SleepLog).filter(SleepLog.date == day).first()
    if _write_blocked(row, source):
        return False
    if row:
        row.asleep_minutes = asleep_minutes
        row.in_bed_minutes = in_bed_minutes
        row.deep_minutes = deep_minutes
        row.rem_minutes = rem_minutes
        row.core_minutes = core_minutes
        row.source = source
        return False
    db.add(SleepLog(
        date=day,
        asleep_minutes=asleep_minutes,
        in_bed_minutes=in_bed_minutes,
        deep_minutes=deep_minutes,
        rem_minutes=rem_minutes,
        core_minutes=core_minutes,
        source=source,
    ))
    return True


def touch_last_ingest(db: DBSession) -> None:
    """Record the time of the last successful Apple Health ingest."""
    from app.routers.settings import get_or_create_settings
    get_or_create_settings(db).health_last_ingest = datetime.utcnow()


# ---------------------------------------------------------------------------
# Weight interpolation — estimate a bodyweight for days with no reading.
#
# Used to fill gaps for display (dashboard chart, day detail) and to prefill
# the manual-log field. Estimates are drawn only from *real* readings (never
# from estimates or demo seed data), so a guess never compounds on a guess
# and stale sample data is replaced by an interpolation of your real weigh-ins.
# ---------------------------------------------------------------------------

def real_weight_points(db: DBSession) -> list[tuple[date, float]]:
    """Real weigh-ins only (excludes estimate/demo), date-ascending — the
    interpolation basis."""
    rows = (
        db.query(WeightLog)
        .filter(WeightLog.source.notin_(DERIVED_SOURCES))
        .order_by(WeightLog.date)
        .all()
    )
    return [(r.date, r.weight_kg) for r in rows]


def resolved_weight_for(
    day: date, row, basis: list[tuple[date, float]]
) -> tuple[Optional[float], bool, Optional[str]]:
    """
    The weight to show for a day, as (weight_kg, estimated, method).

    - A real reading (row present, source not derived) → its value, not
      estimated.
    - Otherwise (no row, or a derived sample/estimate row) → an interpolation
      of the surrounding real weigh-ins, flagged estimated.
    - If there is no real reading to interpolate from at all, fall back to the
      stored derived value if one exists (e.g. a pure demo/seed database), else
      nothing.
    """
    if row is not None and row.source not in DERIVED_SOURCES:
        return row.weight_kg, False, None
    est = estimate_weight_for(day, basis)
    if est is not None:
        return est[0], True, est[1]
    if row is not None:
        return row.weight_kg, False, None
    return None, False, None


def estimate_weight_for(
    day: date, points: list[tuple[date, float]]
) -> Optional[tuple[float, str]]:
    """
    Estimate bodyweight for a day with no tracked reading, from the nearest
    real weigh-ins on either side. Linear interpolation between the reading
    before and the reading after; if only one side exists, carry that value
    forward/back. `points` must be date-ascending. Returns (kg, method) or
    None when there is nothing to estimate from.
    """
    prev = nxt = None
    for d, kg in points:
        if d < day:
            prev = (d, kg)
        elif d > day:
            nxt = (d, kg)
            break
    if prev and nxt:
        span = (nxt[0] - prev[0]).days
        frac = (day - prev[0]).days / span
        return round(prev[1] + (nxt[1] - prev[1]) * frac, 1), "interpolated"
    if prev:
        return round(prev[1], 1), "carried_forward"
    if nxt:
        return round(nxt[1], 1), "carried_back"
    return None


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

@router.post("/api/ingest/health")
def ingest_health(
    payload: dict,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """
    Receives Health Auto Export JSON payload with shape:
        {"data": {"metrics": [...], "workouts": [...]}}

    Each metric: {"name": "step_count", "units": "count", "data": [...points]}
    Each point has a "date" string and quantity fields.

    Handles: step_count, weight_body_mass, sleep_analysis, and every
    nutrition metric in health_metrics.HAE_NUTRITION (macros + micros).
    Unknown metrics are ignored (logged).

    Re-sending the same payload is safe (idempotent upserts), and days
    the user corrected manually are never overwritten.
    """
    start_ts = datetime.utcnow()
    metrics = payload.get("data", {}).get("metrics", [])
    upserted = 0
    handled_names = set()
    unknown_names = set()
    # Nutrition accumulates across metrics; one upsert per day at the end
    nutrition_acc: dict[date, dict[str, float]] = defaultdict(dict)

    for metric in metrics:
        name = metric.get("name", "")
        units = metric.get("units", "")
        data_points = metric.get("data", [])

        if name == "step_count":
            handled_names.add(name)
            # Aggregate points per calendar date (Health may send multiple entries/day)
            by_date: dict[date, int] = {}
            for pt in data_points:
                try:
                    d = _parse_date(pt.get("date", ""))
                    qty = int(float(pt.get("qty", pt.get("value", 0))))
                    by_date[d] = by_date.get(d, 0) + qty
                except Exception as e:
                    logger.warning("step_count point parse error: %s — %s", pt, e)
            for d, steps in by_date.items():
                new = upsert_steps(db, d, steps, "apple_health")
                if new:
                    upserted += 1

        elif name == "weight_body_mass":
            handled_names.add(name)
            for pt in data_points:
                try:
                    d = _parse_date(pt.get("date", ""))
                    raw = float(pt.get("qty", pt.get("value", 0)))
                    # Convert lb → kg if needed
                    kg = raw * 0.453592 if units.lower() in ("lb", "lbs") else raw
                    new = upsert_weight(db, d, round(kg, 2), "apple_health")
                    if new:
                        upserted += 1
                except Exception as e:
                    logger.warning("weight point parse error: %s — %s", pt, e)

        elif name == "sleep_analysis":
            handled_names.add(name)
            # Health Auto Export sends per-stage intervals; aggregate per night.
            # The "night" is keyed to the calendar date the sleep started on.
            nights: dict[date, dict] = defaultdict(lambda: {
                "asleep": 0, "in_bed": 0, "deep": 0, "rem": 0, "core": 0
            })
            for pt in data_points:
                try:
                    d = _parse_date(pt.get("date", ""))
                    # Fields present in Health Auto Export v2+ format:
                    #   asleep, inBed, deep, rem, core  (in minutes or seconds)
                    u = units.lower()
                    factor = 1 / 60 if "second" in u else 1  # convert sec → min if needed

                    def get_min(key: str) -> int:
                        return int(float(pt.get(key, 0)) * factor)

                    nights[d]["asleep"] += get_min("asleep")
                    nights[d]["in_bed"] += get_min("inBed")
                    nights[d]["deep"] += get_min("deep")
                    nights[d]["rem"] += get_min("rem")
                    nights[d]["core"] += get_min("core")
                except Exception as e:
                    logger.warning("sleep point parse error: %s — %s", pt, e)

            for d, v in nights.items():
                new = upsert_sleep(
                    db, d,
                    asleep_minutes=v["asleep"],
                    in_bed_minutes=v["in_bed"],
                    deep_minutes=v["deep"] or None,
                    rem_minutes=v["rem"] or None,
                    core_minutes=v["core"] or None,
                    source="apple_health",
                )
                if new:
                    upserted += 1

        elif name in HAE_NUTRITION:
            handled_names.add(name)
            key = HAE_NUTRITION[name]
            for pt in data_points:
                try:
                    d = _parse_date(pt.get("date", ""))
                    qty = float(pt.get("qty", pt.get("value", 0)))
                    amount = convert_amount(qty, units, key)
                    if amount is None:
                        logger.warning("nutrition %s: unknown unit %r, skipped", name, units)
                        continue
                    day_values = nutrition_acc[d]
                    day_values[key] = day_values.get(key, 0.0) + amount
                except Exception as e:
                    logger.warning("nutrition point parse error: %s — %s", pt, e)

        else:
            unknown_names.add(name)

    for d, values in nutrition_acc.items():
        if upsert_nutrition_partial(db, d, values, "apple_health"):
            upserted += 1

    touch_last_ingest(db)
    db.commit()
    elapsed = (datetime.utcnow() - start_ts).total_seconds()

    if unknown_names:
        logger.info("Ignored unknown Apple Health metrics: %s", sorted(unknown_names))

    logger.info(
        "Health ingest complete in %.2fs — metrics handled: %s, rows upserted: %d",
        elapsed, sorted(handled_names), upserted,
    )

    return {
        "status": "ok",
        "metrics_handled": sorted(handled_names),
        "metrics_ignored": sorted(unknown_names),
        "rows_upserted": upserted,
    }


# ---------------------------------------------------------------------------
# iOS Shortcut ingest — a stable, always-on alternative to Health Auto Export.
#
# The HAE app's background pushes are unreliable (H4 diagnosis): they only
# fire when the app is opened, and the export window is fragile. An iOS
# Shortcut ("Get Health Sample" → "Get Contents of URL") can post the same
# core numbers on the phone's own automation, straight at the production API.
#
# It deliberately reuses the export.xml importer's validated pipeline via the
# shared HealthAggregator — units, timezone/night attribution, multi-source
# dedup, and manual-precedence — instead of the older inline HAE parsing, so
# a Shortcut push obeys the exact same rules a history backfill does.
#
# Payload (all sections optional; a section may be one object or a list):
#     {
#       "weight": [{"date": "2026-07-18", "kg": 82.5}],
#       "steps":  [{"date": "2026-07-18", "count": 11205}],
#       "sleep":  [{"date": "2026-07-18", "asleep_minutes": 427,
#                   "in_bed_minutes": 465, "deep_minutes": 68,
#                   "rem_minutes": 95, "core_minutes": 264}]
#     }
# See docs/HEALTH_INGEST_SHORTCUT.md for the full spec + Shortcut recipe.
# ---------------------------------------------------------------------------

# Accepted field aliases, so the Shortcut author isn't boxed into one spelling.
_WEIGHT_VALUE_KEYS = ("kg", "weight_kg", "value", "qty")
_STEPS_VALUE_KEYS = ("count", "steps", "value", "qty")
_SLEEP_FIELD_ALIASES = {
    "asleep": ("asleep_minutes", "asleep", "asleepMinutes"),
    "in_bed": ("in_bed_minutes", "in_bed", "inBed", "inBedMinutes"),
    "deep": ("deep_minutes", "deep", "deepMinutes"),
    "rem": ("rem_minutes", "rem", "remMinutes"),
    "core": ("core_minutes", "core", "coreMinutes"),
}


def _as_items(section) -> list[dict]:
    """A Shortcut may send one object or a list; a dict of items also works."""
    if section is None:
        return []
    if isinstance(section, dict):
        return [section]
    if isinstance(section, list):
        return [it for it in section if isinstance(it, dict)]
    return []


def _first(item: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in item and item[k] not in (None, ""):
            return item[k]
    return None


@router.post("/api/ingest/health/shortcut")
def ingest_health_shortcut(
    payload: dict,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """
    Ingest weight / steps / sleep posted by an iOS Shortcut, through the same
    validated pipeline as the export.xml backfill. Idempotent, and days the
    user corrected by hand are never overwritten. Bad items are skipped with
    a warning rather than failing the whole push.
    """
    from app.health_ingest import HealthAggregator, parse_day, parse_when, to_float

    agg = HealthAggregator()
    handled: set[str] = set()
    ignored: set[str] = set()

    # Case-insensitive lookup of the three known sections.
    sections = {str(k).lower(): v for k, v in payload.items()}

    for weight in _as_items(sections.get("weight")):
        agg.records_seen += 1
        try:
            when = parse_when(weight["date"])
            raw = _first(weight, _WEIGHT_VALUE_KEYS)
            if raw is None:
                agg.warn(f"weight item missing a value: {weight}")
                continue
            agg.add_weight(when, to_float(raw), weight.get("unit"), "apple_health")
            handled.add("weight")
        except Exception as e:
            agg.warn(f"weight item skipped: {e}")

    for steps in _as_items(sections.get("steps")):
        agg.records_seen += 1
        try:
            raw = _first(steps, _STEPS_VALUE_KEYS)
            if raw is None:
                agg.warn(f"steps item missing a value: {steps}")
                continue
            agg.add_steps(parse_day(steps["date"]), to_float(raw), "apple_health")
            handled.add("steps")
        except Exception as e:
            agg.warn(f"steps item skipped: {e}")

    for sleep in _as_items(sections.get("sleep")):
        agg.records_seen += 1
        try:
            night = parse_day(sleep["date"])
            minutes = {
                field: to_float(_first(sleep, aliases) or 0)
                for field, aliases in _SLEEP_FIELD_ALIASES.items()
            }
            if not (minutes["asleep"] or minutes["in_bed"]):
                agg.warn(f"sleep item has no asleep/in-bed minutes: {sleep}")
                continue
            agg.add_sleep_night(night, "apple_health", **minutes)
            handled.add("sleep")
        except Exception as e:
            agg.warn(f"sleep item skipped: {e}")

    for key in sections:
        if key not in ("weight", "steps", "sleep"):
            ignored.add(str(key))

    report = agg.finalize(db)
    touch_last_ingest(db)
    db.commit()

    logger.info(
        "Shortcut ingest — sections handled: %s, rows created: %d, warnings: %d",
        sorted(handled), report["rows_created"], len(report["warnings"]),
    )

    report["sections_handled"] = sorted(handled)
    report["ignored"] = sorted(ignored)
    return report


def _parse_date(date_str: str) -> date:
    """
    Parse date strings from Health Auto Export.
    Formats seen: "2024-01-15 08:30:00 -0500", "2024-01-15", "2024-01-15T08:30:00"
    We only want the calendar date portion.
    """
    # Strip timezone offset if present
    s = date_str.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:len(fmt) + 5], fmt).date()
        except ValueError:
            pass
    # Last resort: take just the date part
    return date.fromisoformat(s[:10])


# ---------------------------------------------------------------------------
# History backfill — Apple Health "Export All Health Data" upload
# ---------------------------------------------------------------------------

@router.post("/api/ingest/health-export")
def ingest_health_export(
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """
    One-time history import. Accepts the export.zip produced by the
    Health app (profile → "Export All Health Data") or a bare export.xml.
    Stream-parsed, so multi-hundred-MB exports are fine. Idempotent, and
    manually corrected days survive untouched.
    """
    from app.health_xml import import_export_file

    result = import_export_file(file.file, file.filename or "", db)
    if result.get("status") == "ok":
        touch_last_ingest(db)
        db.commit()
    logger.info("Health export backfill: %s", result)
    return result


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("/api/health/weight", response_model=list[WeightLogOut])
def get_weight_log(
    days: int = Query(90, ge=1, le=365),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    from datetime import timedelta
    since = date.today() - timedelta(days=days)
    return (
        db.query(WeightLog)
        .filter(WeightLog.date >= since)
        .order_by(WeightLog.date)
        .all()
    )


@router.get("/api/health/weight/estimate", response_model=WeightEstimateOut)
def estimate_weight(
    day: date = Query(..., alias="date"),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """
    Weight to show/prefill for a date. A real reading is returned as-is
    (estimated=False). A day with only demo/estimate data — or no data — is
    interpolated from the surrounding real weigh-ins (estimated=True), or
    returns a null weight when there's nothing to estimate from.
    """
    row = db.query(WeightLog).filter(WeightLog.date == day).first()
    wkg, est, method = resolved_weight_for(day, row, real_weight_points(db))
    if wkg is None:
        return WeightEstimateOut(date=day, weight_kg=None, estimated=False)
    if est:
        return WeightEstimateOut(
            date=day, weight_kg=wkg, estimated=True, method=method, source="estimated"
        )
    return WeightEstimateOut(
        date=day, weight_kg=wkg, estimated=False, source=(row.source if row else None)
    )


@router.post("/api/health/weight", response_model=WeightLogOut, status_code=201)
def log_weight_manual(
    body: WeightLogCreate,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    upsert_weight(db, body.date, body.weight_kg, body.source)
    db.commit()
    return db.query(WeightLog).filter(WeightLog.date == body.date).first()


@router.get("/api/health/steps", response_model=list[StepsLogOut])
def get_steps_log(
    days: int = Query(14, ge=1, le=365),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    from datetime import timedelta
    since = date.today() - timedelta(days=days)
    return (
        db.query(StepsLog)
        .filter(StepsLog.date >= since)
        .order_by(StepsLog.date)
        .all()
    )


@router.post("/api/health/steps", response_model=StepsLogOut, status_code=201)
def log_steps_manual(
    body: StepsLogCreate,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    upsert_steps(db, body.date, body.steps, body.source)
    db.commit()
    return db.query(StepsLog).filter(StepsLog.date == body.date).first()


@router.get("/api/health/sleep", response_model=list[SleepLogOut])
def get_sleep_log(
    days: int = Query(14, ge=1, le=365),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    from datetime import timedelta
    since = date.today() - timedelta(days=days)
    return (
        db.query(SleepLog)
        .filter(SleepLog.date >= since)
        .order_by(SleepLog.date)
        .all()
    )


@router.post("/api/health/sleep", response_model=SleepLogOut, status_code=201)
def log_sleep_manual(
    body: SleepLogCreate,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    upsert_sleep(
        db, body.date, body.asleep_minutes, body.in_bed_minutes,
        body.deep_minutes, body.rem_minutes, body.core_minutes, body.source
    )
    db.commit()
    return db.query(SleepLog).filter(SleepLog.date == body.date).first()


@router.get("/api/health/nutrition", response_model=list[NutritionDayOut])
def get_nutrition_log(
    days: int = Query(30, ge=1, le=365),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Same data as GET /api/nutrition, exposed under the /api/health/* scheme."""
    from datetime import timedelta
    since = date.today() - timedelta(days=days)
    return (
        db.query(NutritionDay)
        .filter(NutritionDay.date >= since)
        .order_by(NutritionDay.date)
        .all()
    )
