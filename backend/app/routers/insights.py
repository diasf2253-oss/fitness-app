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
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.core.auth import require_auth
from app.core.db import get_db
from app.models import NutritionDay, SleepLog, StepsLog, User, WeightLog
from app.models import Session as WorkoutSession
from app.schemas import (
    CorrelationPair,
    CorrelationPoint,
    CorrelationsOut,
    TrainingSplit,
    WeeklyReviewOut,
)
from app.services.insights import (
    MAX_PAIRS,
    MIN_PAIR_N,
    MIN_SPLIT_N,
    WINDOW_DAYS,
    daily_volume,
    list_scale_trackers,
    pearson,
    period_metrics,
    tracker_map,
)

router = APIRouter(prefix="/api/insights", tags=["insights"])


# ---------------------------------------------------------------------------
# Weekly review
# ---------------------------------------------------------------------------


@router.get("/weekly", response_model=WeeklyReviewOut)
def weekly_review(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    today = date.today()
    return WeeklyReviewOut(
        current=period_metrics(db, today - timedelta(days=6), today, current_user.id),
        previous=period_metrics(db, today - timedelta(days=13), today - timedelta(days=7), current_user.id),
    )


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------

@router.get("/correlations", response_model=CorrelationsOut)
def correlations(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    today = date.today()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    user_id = current_user.id

    steps = {r.date: float(r.steps) for r in
             db.query(StepsLog).filter(StepsLog.user_id == user_id, StepsLog.date.between(start, today)).all()}
    sleep_h = {r.date: round(r.asleep_minutes / 60, 2) for r in
               db.query(SleepLog).filter(SleepLog.user_id == user_id, SleepLog.date.between(start, today)).all()}
    calories = {r.date: r.calories for r in
                db.query(NutritionDay).filter(NutritionDay.user_id == user_id, NutritionDay.date.between(start, today)).all()}
    weight = {r.date: r.weight_kg for r in
              db.query(WeightLog).filter(WeightLog.user_id == user_id, WeightLog.date.between(start, today)).all()}

    # Volume is zero-filled across the window: "did I train, and how much"
    # is the question, so rest days count as 0 rather than missing.
    volume_days = daily_volume(db, start, today, user_id)
    volume = {start + timedelta(days=i): volume_days.get(start + timedelta(days=i), 0.0)
              for i in range(WINDOW_DAYS)}

    series: dict[str, dict[date, float]] = {
        "Steps": steps,
        "Sleep (h)": sleep_h,
        "Calories": calories,
        "Weight (kg)": weight,
        "Training volume (kg)": volume,
    }

    scale_trackers = list_scale_trackers(db, user_id)
    for t in scale_trackers:
        series[t.name] = tracker_map(db, t.id, start, today)

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
        .filter(WorkoutSession.user_id == user_id, WorkoutSession.started_at >= datetime.combine(start, time.min))
        .all()
    }
    splits: list[TrainingSplit] = []
    for t in scale_trackers:
        values = tracker_map(db, t.id, start, today)
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
