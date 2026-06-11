"""
Insights (Phase 7) — turn accumulated data into understanding.

GET /api/insights/weekly        — this week vs last, identical metric sets
GET /api/insights/correlations  — Pearson r over daily pairs (90-day window)
                                  + scale-tracker averages on training days
                                  vs rest days

Honesty rules: correlations only appear with ≥ MIN_PAIR_N overlapping
days; splits need ≥ MIN_SPLIT_N days on each side; constant series have
no defined r and are skipped. The UI repeats the caveat that correlation
is not causation.
"""
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import (
    NutritionDay, Session as WorkoutSession, SessionExercise, Set as SetModel,
    SleepLog, StepsLog, Tracker, TrackerLog, WeightLog,
)
from app.schemas import (
    CorrelationPair, CorrelationPoint, CorrelationsOut, HabitWeek,
    ScaleWeek, TrainingSplit, WeekMetrics, WeeklyReviewOut,
)

router = APIRouter(prefix="/api/insights", tags=["insights"])

WINDOW_DAYS = 90
MIN_PAIR_N = 10
MIN_SPLIT_N = 5
MAX_PAIRS = 8


# ---------------------------------------------------------------------------
# Math
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shared series builders
# ---------------------------------------------------------------------------

def _daily_volume(db: DBSession, start: date, end: date) -> dict[date, float]:
    """Completed working-set volume per calendar day (kg)."""
    rows = (
        db.query(WorkoutSession.started_at, SetModel.weight_kg, SetModel.reps)
        .join(SessionExercise, WorkoutSession.id == SessionExercise.session_id)
        .join(SetModel, SessionExercise.id == SetModel.session_exercise_id)
        .filter(
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


def _scale_trackers(db: DBSession) -> list[Tracker]:
    return (
        db.query(Tracker)
        .filter(Tracker.kind == "scale", Tracker.is_archived.is_(False))
        .order_by(Tracker.position, Tracker.id)
        .all()
    )


def _tracker_map(db: DBSession, tracker_id: int, start: date, end: date) -> dict[date, float]:
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


# ---------------------------------------------------------------------------
# Weekly review
# ---------------------------------------------------------------------------

def period_metrics(db: DBSession, start: date, end: date) -> WeekMetrics:
    days_in_period = (end - start).days + 1

    steps_avg = (
        db.query(func.avg(StepsLog.steps))
        .filter(StepsLog.date.between(start, end))
        .scalar()
    )
    sleep_avg = (
        db.query(func.avg(SleepLog.asleep_minutes))
        .filter(SleepLog.date.between(start, end))
        .scalar()
    )
    calories_avg, protein_avg = (
        db.query(func.avg(NutritionDay.calories), func.avg(NutritionDay.protein_g))
        .filter(NutritionDay.date.between(start, end))
        .first()
    )

    weights = (
        db.query(WeightLog)
        .filter(WeightLog.date.between(start, end))
        .order_by(WeightLog.date)
        .all()
    )
    weight_change = (
        round(weights[-1].weight_kg - weights[0].weight_kg, 1)
        if len(weights) >= 2 else None
    )

    volume_by_day = _daily_volume(db, start, end)
    sessions = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.started_at >= datetime.combine(start, time.min),
            WorkoutSession.started_at < datetime.combine(end + timedelta(days=1), time.min),
        )
        .count()
    )

    scales = []
    habits = []
    for t in (
        db.query(Tracker)
        .filter(Tracker.is_archived.is_(False))
        .order_by(Tracker.position, Tracker.id)
        .all()
    ):
        if t.kind == "scale":
            values = list(_tracker_map(db, t.id, start, end).values())
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


@router.get("/weekly", response_model=WeeklyReviewOut)
def weekly_review(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    today = date.today()
    return WeeklyReviewOut(
        current=period_metrics(db, today - timedelta(days=6), today),
        previous=period_metrics(db, today - timedelta(days=13), today - timedelta(days=7)),
    )


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------

@router.get("/correlations", response_model=CorrelationsOut)
def correlations(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    today = date.today()
    start = today - timedelta(days=WINDOW_DAYS - 1)

    steps = {r.date: float(r.steps) for r in
             db.query(StepsLog).filter(StepsLog.date.between(start, today)).all()}
    sleep_h = {r.date: round(r.asleep_minutes / 60, 2) for r in
               db.query(SleepLog).filter(SleepLog.date.between(start, today)).all()}
    calories = {r.date: r.calories for r in
                db.query(NutritionDay).filter(NutritionDay.date.between(start, today)).all()}
    weight = {r.date: r.weight_kg for r in
              db.query(WeightLog).filter(WeightLog.date.between(start, today)).all()}

    # Volume is zero-filled across the window: "did I train, and how much"
    # is the question, so rest days count as 0 rather than missing.
    volume_days = _daily_volume(db, start, today)
    volume = {start + timedelta(days=i): volume_days.get(start + timedelta(days=i), 0.0)
              for i in range(WINDOW_DAYS)}

    series: dict[str, dict[date, float]] = {
        "Steps": steps,
        "Sleep (h)": sleep_h,
        "Calories": calories,
        "Weight (kg)": weight,
        "Training volume (kg)": volume,
    }

    scale_trackers = _scale_trackers(db)
    for t in scale_trackers:
        series[t.name] = _tracker_map(db, t.id, start, today)

    candidate_pairs: list[tuple[str, str]] = [
        ("Sleep (h)", "Training volume (kg)"),
        ("Sleep (h)", "Steps"),
        ("Steps", "Calories"),
        ("Calories", "Weight (kg)"),
    ]
    for t in scale_trackers:
        candidate_pairs.append((t.name, "Sleep (h)"))
        candidate_pairs.append((t.name, "Training volume (kg)"))

    pairs: list[CorrelationPair] = []
    for key_a, key_b in candidate_pairs:
        map_a, map_b = series[key_a], series[key_b]
        shared = sorted(set(map_a) & set(map_b))
        if len(shared) < MIN_PAIR_N:
            continue
        xs = [map_a[d] for d in shared]
        ys = [map_b[d] for d in shared]
        r = pearson(xs, ys)
        if r is None:
            continue
        pairs.append(CorrelationPair(
            label_a=key_a,
            label_b=key_b,
            r=round(r, 2),
            n=len(shared),
            points=[CorrelationPoint(date=d, a=map_a[d], b=map_b[d]) for d in shared],
        ))

    pairs.sort(key=lambda p: abs(p.r), reverse=True)
    pairs = pairs[:MAX_PAIRS]

    # Scale trackers on training days vs rest days. A "training day" is a
    # day with a session — volume can be zero (bodyweight work) and the
    # day still counts as trained.
    training_days = {
        row.started_at.date()
        for row in db.query(WorkoutSession.started_at)
        .filter(WorkoutSession.started_at >= datetime.combine(start, time.min))
        .all()
    }
    splits: list[TrainingSplit] = []
    for t in scale_trackers:
        values = _tracker_map(db, t.id, start, today)
        with_vals = [v for d, v in values.items() if d in training_days]
        without_vals = [v for d, v in values.items() if d not in training_days]
        if len(with_vals) >= MIN_SPLIT_N and len(without_vals) >= MIN_SPLIT_N:
            splits.append(TrainingSplit(
                name=t.name,
                with_avg=round(sum(with_vals) / len(with_vals), 1),
                without_avg=round(sum(without_vals) / len(without_vals), 1),
                n_with=len(with_vals),
                n_without=len(without_vals),
            ))

    return CorrelationsOut(window_days=WINDOW_DAYS, pairs=pairs, training_splits=splits)
