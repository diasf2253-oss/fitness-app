"""
Apple Health ingest endpoint + health data read endpoints.

POST /api/ingest/health      — receives Health Auto Export JSON, upserts rows
GET  /api/health/weight      — weight log (paginated, date range)
GET  /api/health/steps       — steps log
GET  /api/health/sleep       — sleep log
"""
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
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
# Last-write-wins for now. Phase 3 hook: when the Apple Health ingest should
# stop overwriting rows the user corrected by hand, branch here on the
# existing row's source ('manual' beats 'apple_health') instead of always
# overwriting — every writer funnels through these helpers.
# ---------------------------------------------------------------------------

def upsert_weight(db: DBSession, day: date, weight_kg: float, source: str) -> bool:
    """Insert or update weight_log for a given date. Returns True if new row."""
    row = db.query(WeightLog).filter(WeightLog.date == day).first()
    if row:
        row.weight_kg = weight_kg
        row.source = source
        return False
    db.add(WeightLog(date=day, weight_kg=weight_kg, source=source))
    return True


def upsert_steps(db: DBSession, day: date, steps: int, source: str) -> bool:
    row = db.query(StepsLog).filter(StepsLog.date == day).first()
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

    Handles: step_count, weight_body_mass, sleep_analysis
    Unknown metrics are ignored (logged).

    Re-sending the same payload is safe (idempotent upserts).
    """
    start_ts = datetime.utcnow()
    metrics = payload.get("data", {}).get("metrics", [])
    upserted = 0
    handled_names = set()
    unknown_names = set()

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
            from collections import defaultdict
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

        else:
            unknown_names.add(name)

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
