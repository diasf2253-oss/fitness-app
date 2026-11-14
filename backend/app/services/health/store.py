"""
Health data store — the only place health rows (weight, steps, sleep,
nutrition) are written, plus the weight-interpolation helpers that read them.

Every writer (manual entry, Apple Health ingest, dev seed, sync) funnels
through these helpers, so the source-precedence rule lives here only.
HTTP endpoints live in routers/health.py and routers/nutrition.py.
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.models import NutritionDay, SleepLog, StepsLog, WeightLog
from app.schemas import NutritionDayCreate
from app.services.user_settings import get_or_create_settings

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

def write_blocked(row, source: str) -> bool:
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


def upsert_weight(db: DBSession, day: date, weight_kg: float, source: str, user_id: int) -> bool:
    """Insert or update weight_log for a given date. Returns True if new row."""
    row = db.query(WeightLog).filter(WeightLog.user_id == user_id, WeightLog.date == day).first()
    if write_blocked(row, source):
        return False
    if row:
        row.weight_kg = weight_kg
        row.source = source
        return False
    db.add(WeightLog(user_id=user_id, date=day, weight_kg=weight_kg, source=source))
    return True


def upsert_steps(db: DBSession, day: date, steps: int, source: str, user_id: int) -> bool:
    row = db.query(StepsLog).filter(StepsLog.user_id == user_id, StepsLog.date == day).first()
    if write_blocked(row, source):
        return False
    if row:
        row.steps = steps
        row.source = source
        return False
    db.add(StepsLog(user_id=user_id, date=day, steps=steps, source=source))
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
    user_id: int,
) -> bool:
    row = db.query(SleepLog).filter(SleepLog.user_id == user_id, SleepLog.date == day).first()
    if write_blocked(row, source):
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
        user_id=user_id,
        date=day,
        asleep_minutes=asleep_minutes,
        in_bed_minutes=in_bed_minutes,
        deep_minutes=deep_minutes,
        rem_minutes=rem_minutes,
        core_minutes=core_minutes,
        source=source,
    ))
    return True


def touch_last_ingest(db: DBSession, user_id: int) -> None:
    """Record the time of the last successful Apple Health ingest."""
    get_or_create_settings(db, user_id).health_last_ingest = datetime.utcnow()


# ---------------------------------------------------------------------------
# Weight interpolation — estimate a bodyweight for days with no reading.
#
# Used to fill gaps for display (dashboard chart, day detail) and to prefill
# the manual-log field. Estimates are drawn only from *real* readings (never
# from estimates or demo seed data), so a guess never compounds on a guess
# and stale sample data is replaced by an interpolation of your real weigh-ins.
# ---------------------------------------------------------------------------

def real_weight_points(db: DBSession, user_id: int) -> list[tuple[date, float]]:
    """Real weigh-ins only (excludes estimate/demo), date-ascending — the
    interpolation basis."""
    rows = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.source.notin_(DERIVED_SOURCES))
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


def upsert_nutrition(db: DBSession, body: NutritionDayCreate, user_id: int) -> NutritionDay:
    """
    Insert or overwrite a day's nutrition data (idempotent).
    `micros` only replaces when provided — a manual macro correction must
    not wipe the micronutrients Apple Health synced for that day.
    """
    row = db.query(NutritionDay).filter(
        NutritionDay.user_id == user_id, NutritionDay.date == body.date
    ).first()
    # Manual corrections are only replaced by other manual writes (same
    # precedence rule as write_blocked above)
    if row and row.source == "manual" and body.source != "manual":
        return row
    if row:
        row.calories = body.calories
        row.protein_g = body.protein_g
        row.carbs_g = body.carbs_g
        row.fat_g = body.fat_g
        if body.micros is not None:
            row.micros = body.micros
        row.source = body.source
    else:
        row = NutritionDay(user_id=user_id, **body.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row
