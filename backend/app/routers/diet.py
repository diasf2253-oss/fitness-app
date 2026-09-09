"""Diet — adaptive energy, macros, and micronutrient analysis in one call.

GET  /api/diet         — the whole Diet view
POST /api/diet/recalc  — re-run the weekly adaptation now (ignores the
                         once-per-week guard; handy after correcting weights)

The calorie target is an anchored, weekly-trend step model (see
``app.calorie_adapt``): it starts at a user-set anchor (2,300 kcal) and moves
±one step once per completed ISO week toward the signed weekly goal. It is
never recomputed from scratch. Protein and fat targets are manual; carbs flex.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app import calorie_adapt
from app.activity_burn import activity_kcal
from app.auth import require_auth
from app.calorie_adapt import carbs_from_target
from app.db import get_db
from app.models import Activity, NutritionDay, User, WeightLog
from app.nutrition_rda import build_breakdown
from app.routers.settings import get_or_create_settings
from app.schemas import ActivityOut, DietOut, EnergySummary, NutrientStatus
from app.weight_trend import iso_week_start, weekly_averages

router = APIRouter(prefix="/api/diet", tags=["diet"])

LOOKBACK_DAYS = 35      # how far back to pull weight + nutrition rows
MICRO_AVG_DAYS = 7      # most-recent logged days the micro average covers


def _resolved_ceiling(settings, weight_by_date, intake_by_date, today):
    """Manual override if set, else estimated maintenance (a guardrail only)."""
    if settings.calorie_ceiling is not None:
        return settings.calorie_ceiling
    est = calorie_adapt.estimate_maintenance(weight_by_date, intake_by_date, today)
    return int(round(est / 10.0) * 10) if est is not None else None


def _adapt_if_due(db, settings, weight_by_date, ceiling, today, *, force=False):
    """Run the once-per-week adaptation, persisting the moved target. With
    ``force`` we re-evaluate even if this week was already processed."""
    last_week = None if force else settings.last_adapted_week
    result = calorie_adapt.adapt_target(
        current_target=settings.calorie_target,
        goal_kg_per_week=settings.goal_kg_per_week,
        step_kcal=settings.adapt_step_kcal,
        tolerance_kg=settings.adapt_tolerance_kg,
        floor=settings.calorie_floor,
        ceiling=ceiling,
        weight_by_date=weight_by_date,
        today=today,
        last_adapted_week=last_week,
    )
    if result.due:
        settings.calorie_target = result.target
        settings.last_adapted_week = iso_week_start(today)
        db.commit()
        db.refresh(settings)
    return result


def build_diet(db: DBSession, user_id: int, *, force_recalc: bool = False) -> DietOut:
    today = date.today()
    settings = get_or_create_settings(db, user_id)

    since = today - timedelta(days=LOOKBACK_DAYS)
    weights = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date >= since)
        .order_by(WeightLog.date).all()
    )
    nutrition = (
        db.query(NutritionDay)
        .filter(NutritionDay.user_id == user_id, NutritionDay.date >= since)
        .order_by(NutritionDay.date).all()
    )
    weight_by_date = {w.date: w.weight_kg for w in weights}
    intake_by_date = {n.date: n.calories for n in nutrition}

    ceiling = _resolved_ceiling(settings, weight_by_date, intake_by_date, today)
    _adapt_if_due(db, settings, weight_by_date, ceiling, today, force=force_recalc)

    # ---- average intake ----
    def avg_intake(days: int):
        start = today - timedelta(days=days)
        vals = [n.calories for n in nutrition if n.date > start and n.calories]
        return round(sum(vals) / len(vals)) if vals else None

    # ---- micronutrient average over the most recent logged days ----
    recent_nut = [n for n in nutrition if n.micros][-MICRO_AVG_DAYS:]
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for n in recent_nut:
        for k, v in (n.micros or {}).items():
            if v is None:
                continue
            try:
                sums[k] = sums.get(k, 0.0) + float(v)
                counts[k] = counts.get(k, 0) + 1
            except (TypeError, ValueError):
                continue
    avg_micros = {k: sums[k] / counts[k] for k in sums}
    nutrients = [NutrientStatus(**row) for row in build_breakdown(avg_micros, settings.sex)]

    # ---- weekly trend (reuses Part 2's function — same source as the chart) ----
    weeks = weekly_averages(weight_by_date, today)
    completed = [w for w in weeks if not w.is_current_week]
    weekly_change = None
    entries_last_week = completed[-1].n_entries if completed else None
    have_compare = (
        len(completed) >= 2
        and completed[-1].week_start - completed[-2].week_start == timedelta(days=7)
    )
    if have_compare:
        weekly_change = round(completed[-1].avg_kg - completed[-2].avg_kg, 2)
    weight_trend = weeks[-1].avg_kg if weeks else None

    # ---- macros (protein/fat manual; carbs fill the remainder) ----
    protein = settings.protein_target_g
    fat = settings.fat_max_g
    carb = carbs_from_target(settings.calorie_target, protein, fat) if settings.calorie_target else None

    adaptive_ready = settings.last_adapted_week is not None
    min_entries = calorie_adapt.MIN_ENTRIES_FOR_ADAPT
    note = None
    if not have_compare:
        note = (
            f"Gathering data — the target adapts each Monday once there are two "
            f"consecutive weeks with at least {min_entries} weigh-ins. Holding at "
            f"your {settings.calorie_target} kcal anchor."
        )
    elif entries_last_week is not None and entries_last_week < min_entries:
        note = (
            f"Holding — last completed week had only {entries_last_week} "
            f"weigh-in(s); {min_entries} are needed to adapt."
        )

    next_adapt = iso_week_start(today) + timedelta(days=7)

    energy = EnergySummary(
        calorie_target=settings.calorie_target,
        goal_kg_per_week=settings.goal_kg_per_week,
        protein_target_g=protein,
        fat_target_g=fat,
        carb_target_g=carb,
        adaptive_ready=adaptive_ready,
        weekly_change_kg=weekly_change,
        last_adapted=settings.last_adapted_week,
        next_adapt=next_adapt,
        entries_last_week=entries_last_week,
        floor=settings.calorie_floor,
        ceiling=ceiling,
        weight_trend_kg=weight_trend,
        avg_intake_7d=avg_intake(7),
        avg_intake_14d=avg_intake(14),
        note=note,
    )

    # ---- activities (last 14 days, with informational burn estimate) ----
    latest_w = weights[-1].weight_kg if weights else 75.0
    act_rows = (
        db.query(Activity)
        .filter(Activity.user_id == user_id, Activity.date >= today - timedelta(days=14))
        .order_by(Activity.date.desc(), Activity.id.desc())
        .all()
    )
    activities = [
        ActivityOut(
            id=a.id, date=a.date, type=a.type, duration_min=a.duration_min,
            notes=a.notes, calories_est=activity_kcal(a.type, a.duration_min, latest_w),
        )
        for a in act_rows
    ]

    return DietOut(
        energy=energy, nutrients=nutrients, nutrient_days=len(recent_nut), activities=activities,
    )


@router.get("", response_model=DietOut)
def get_diet(db: DBSession = Depends(get_db), current_user: User = Depends(require_auth)):
    return build_diet(db, current_user.id)


@router.post("/recalc", response_model=DietOut)
def recalc_diet(db: DBSession = Depends(get_db), current_user: User = Depends(require_auth)):
    return build_diet(db, current_user.id, force_recalc=True)
