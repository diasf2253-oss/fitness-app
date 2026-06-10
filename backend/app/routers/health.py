"""
Apple Health ingest endpoints + health data read endpoints.

All health data — weight, steps, sleep, and nutrition including
micronutrients — arrives through Apple Health (YAZIO feeds it on-phone).

POST /api/ingest/health         — Health Auto Export JSON push (daily)
POST /api/ingest/health-export  — export.zip/.xml upload (history backfill)
GET  /api/health/weight|steps|sleep|nutrition — date-range series
POST /api/health/weight|steps|sleep           — manual upserts
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
    StepsLogCreate, StepsLogOut, WeightLogCreate, WeightLogOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# Upsert helpers — idempotent: re-sending the same data changes nothing.
#
# Source precedence (Phase 3): a day the user corrected by hand
# (source='manual') is only ever overwritten by another manual write —
# the correction exists precisely because the synced value was wrong.
# apple_health and sample writes overwrite each other freely.
# Every writer funnels through these helpers, so the rule lives here only.
# ---------------------------------------------------------------------------

def _manual_wins(row, source: str) -> bool:
    """True when an existing manual row should block this write."""
    return row is not None and row.source == "manual" and source != "manual"


def upsert_weight(db: DBSession, day: date, weight_kg: float, source: str) -> bool:
    """Insert or update weight_log for a given date. Returns True if new row."""
    row = db.query(WeightLog).filter(WeightLog.date == day).first()
    if _manual_wins(row, source):
        return False
    if row:
        row.weight_kg = weight_kg
        row.source = source
        return False
    db.add(WeightLog(date=day, weight_kg=weight_kg, source=source))
    return True


def upsert_steps(db: DBSession, day: date, steps: int, source: str) -> bool:
    row = db.query(StepsLog).filter(StepsLog.date == day).first()
    if _manual_wins(row, source):
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
    if _manual_wins(row, source):
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
