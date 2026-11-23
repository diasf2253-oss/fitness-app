"""
Insights math — period metrics (weekly review) and the helpers behind the
correlations view. HTTP endpoints live in routers/insights.py; the Coach's
data brief (services/coach_context.py) reuses period_metrics.

Honesty rules: correlations only appear with ≥ MIN_PAIR_N overlapping
days; splits need ≥ MIN_SPLIT_N days on each side; constant series have
no defined r and are skipped.
"""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.models import (
    NutritionDay,
    SessionExercise,
    SleepLog,
    StepsLog,
    Tracker,
    TrackerLog,
    WeightLog,
)
from app.models import (
    Session as WorkoutSession,
)
from app.models import (
    Set as SetModel,
)
from app.schemas import HabitWeek, ScaleWeek, WeekMetrics

WINDOW_DAYS = 90


MIN_PAIR_N = 10


MIN_SPLIT_N = 5


MAX_PAIRS = 8


def pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Pearson r; None for constant series (undefined) or n < 2."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def daily_volume(db: DBSession, start: date, end: date, user_id: int) -> dict[date, float]:
    """Completed working-set volume per calendar day (kg)."""
    rows = (
        db.query(WorkoutSession.started_at, SetModel.weight_kg, SetModel.reps)
        .join(SessionExercise, WorkoutSession.id == SessionExercise.session_id)
        .join(SetModel, SessionExercise.id == SetModel.session_exercise_id)
        .filter(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= datetime.combine(start, time.min),
            WorkoutSession.started_at < datetime.combine(end + timedelta(days=1), time.min),
            SetModel.is_completed.is_(True),
            SetModel.is_warmup.is_(False),
            SetModel.reps > 0,
            SetModel.weight_kg > 0,
        )
        .all()
    )
    acc: dict[date, float] = defaultdict(float)
    for started_at, weight, reps in rows:
        acc[started_at.date()] += weight * reps
    return dict(acc)


def list_scale_trackers(db: DBSession, user_id: int) -> list[Tracker]:
    return (
        db.query(Tracker)
        .filter(Tracker.user_id == user_id, Tracker.kind == "scale", Tracker.is_archived.is_(False))
        .order_by(Tracker.position, Tracker.id)
        .all()
    )


def tracker_map(db: DBSession, tracker_id: int, start: date, end: date) -> dict[date, float]:
    rows = (
        db.query(TrackerLog)
        .filter(
            TrackerLog.tracker_id == tracker_id,
            TrackerLog.date.between(start, end),
            TrackerLog.value_num.isnot(None),
        )
        .all()
    )
    return {r.date: r.value_num for r in rows}


def period_metrics(db: DBSession, start: date, end: date, user_id: int) -> WeekMetrics:
    days_in_period = (end - start).days + 1

    steps_avg = (
        db.query(func.avg(StepsLog.steps))
        .filter(StepsLog.user_id == user_id, StepsLog.date.between(start, end))
        .scalar()
    )
    sleep_avg = (
        db.query(func.avg(SleepLog.asleep_minutes))
        .filter(SleepLog.user_id == user_id, SleepLog.date.between(start, end))
        .scalar()
    )
    calories_avg, protein_avg = (
        db.query(func.avg(NutritionDay.calories), func.avg(NutritionDay.protein_g))
        .filter(NutritionDay.user_id == user_id, NutritionDay.date.between(start, end))
        .first()
    )

    weights = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date.between(start, end))
        .order_by(WeightLog.date)
        .all()
    )
    weight_change = (
        round(weights[-1].weight_kg - weights[0].weight_kg, 1)
        if len(weights) >= 2 else None
    )

    volume_by_day = daily_volume(db, start, end, user_id)
    sessions = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= datetime.combine(start, time.min),
            WorkoutSession.started_at < datetime.combine(end + timedelta(days=1), time.min),
        )
        .count()
    )

    scales = []
    habits = []
    for t in (
        db.query(Tracker)
        .filter(Tracker.user_id == user_id, Tracker.is_archived.is_(False))
        .order_by(Tracker.position, Tracker.id)
        .all()
    ):
        if t.kind == "scale":
            values = list(tracker_map(db, t.id, start, end).values())
            scales.append(ScaleWeek(
                name=t.name,
                avg=round(sum(values) / len(values), 1) if values else None,
            ))
        elif t.kind == "habit":
            done = (
                db.query(TrackerLog)
                .filter(
                    TrackerLog.tracker_id == t.id,
                    TrackerLog.date.between(start, end),
                    TrackerLog.value_num >= 1,
                )
                .count()
            )
            habits.append(HabitWeek(name=t.name, done=done, days=days_in_period))

    return WeekMetrics(
        date_from=start,
        date_to=end,
        volume_kg=round(sum(volume_by_day.values()), 1),
        sessions=sessions,
        steps_avg=round(steps_avg) if steps_avg is not None else None,
        sleep_avg_h=round(sleep_avg / 60, 1) if sleep_avg is not None else None,
        calories_avg=round(calories_avg) if calories_avg is not None else None,
        protein_avg_g=round(protein_avg) if protein_avg is not None else None,
        weight_change_kg=weight_change,
        scales=scales,
        habits=habits,
    )
