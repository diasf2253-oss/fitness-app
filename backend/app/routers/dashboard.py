"""
Dashboard endpoint — everything the home screen needs in ONE call,
so the phone PWA pays a single round-trip on cold start.

GET /api/dashboard
  - weight: last 90 days + 7-day moving average
  - steps: last 14 days
  - sleep: hours per night, last 14 days
  - nutrition_today: today's intake (zeros + logged=False when empty)
  - targets: from the settings row
  - training: rolling-7-day volume, session count, and recent PRs

Training numbers reuse the Phase 1 stats logic (stats.session_summary)
rather than reimplementing volume/PR math here.
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import NutritionDay, Session as WorkoutSession, SleepLog, StepsLog, WeightLog
from app.routers.health import DERIVED_SOURCES, real_weight_points, resolved_weight_for
from app.routers.settings import get_or_create_settings
from app.routers.stats import session_summary
from app.schemas import (
    DashboardOut, DashboardTargets, DashboardTraining, DashboardWeight,
    MovingAvgPoint, NutritionToday, RecentPR, SleepPoint, StepsPoint, WeightPoint,
)

router = APIRouter(tags=["dashboard"])

# Cap the PR list so one big session doesn't flood the widget
MAX_RECENT_PRS = 5


def moving_average_7d(series: list[tuple[date, float]]) -> list[tuple[date, float]]:
    """
    Trailing 7-day moving average over a (date, value) series.

    For each point, averages every reading within the previous 7 calendar
    days including the point itself (window = (d-6, ..., d]). Handles gaps:
    days without readings simply contribute nothing to the window.
    Input must be date-ascending; output has one point per input point.
    """
    out: list[tuple[date, float]] = []
    for i, (d, _val) in enumerate(series):
        window_start = d - timedelta(days=6)
        window_vals = [v for (dd, v) in series[: i + 1] if dd >= window_start]
        out.append((d, round(sum(window_vals) / len(window_vals), 2)))
    return out


@router.get("/api/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    today = date.today()

    # ---- Weight: 90-day series. Real weigh-ins show as-is; untracked days
    #      and days carrying only demo/estimate data are shown as interpolated
    #      estimates of the surrounding real readings (flagged). Moving average
    #      runs over the real readings only. ----
    weight_rows = (
        db.query(WeightLog)
        .filter(WeightLog.date >= today - timedelta(days=90))
        .order_by(WeightLog.date)
        .all()
    )
    by_date = {r.date: r for r in weight_rows}
    real_series = [(r.date, r.weight_kg) for r in weight_rows if r.source not in DERIVED_SOURCES]

    series_points: list[WeightPoint] = []
    if weight_rows:
        # Interpolate from the full history so a reading just outside the
        # window still anchors estimates near the window's leading edge.
        basis = real_weight_points(db)
        start = weight_rows[0].date
        for i in range((today - start).days + 1):
            d = start + timedelta(days=i)
            wkg, estimated, _ = resolved_weight_for(d, by_date.get(d), basis)
            if wkg is not None:
                series_points.append(WeightPoint(date=d, weight_kg=wkg, estimated=estimated))

    weight = DashboardWeight(
        series=series_points,
        moving_avg_7d=[
            MovingAvgPoint(date=d, avg_kg=v)
            for d, v in moving_average_7d(real_series)
        ],
    )

    # ---- Steps: last 14 days ----
    steps_rows = (
        db.query(StepsLog)
        .filter(StepsLog.date >= today - timedelta(days=14))
        .order_by(StepsLog.date)
        .all()
    )
    steps = [StepsPoint(date=r.date, steps=r.steps) for r in steps_rows]

    # ---- Sleep: hours per night, last 14 days ----
    sleep_rows = (
        db.query(SleepLog)
        .filter(SleepLog.date >= today - timedelta(days=14))
        .order_by(SleepLog.date)
        .all()
    )
    sleep = [
        SleepPoint(date=r.date, asleep_hours=round(r.asleep_minutes / 60, 1))
        for r in sleep_rows
    ]

    # ---- Nutrition: today's intake vs targets ----
    nut_row = db.query(NutritionDay).filter(NutritionDay.date == today).first()
    nutrition_today = NutritionToday(
        date=today,
        logged=nut_row is not None,
        calories=nut_row.calories if nut_row else 0.0,
        protein_g=nut_row.protein_g if nut_row else 0.0,
        carbs_g=nut_row.carbs_g if nut_row else 0.0,
        fat_g=nut_row.fat_g if nut_row else 0.0,
        micros=(nut_row.micros or {}) if nut_row else {},
    )

    s = get_or_create_settings(db)
    targets = DashboardTargets(
        calorie_target=s.calorie_target,
        protein_target_g=s.protein_target_g,
        fat_max_g=s.fat_max_g,
        unit_system=s.unit_system,
    )

    # ---- Training: reuse Phase 1 session summaries for the last 7 days ----
    week_start = datetime.combine(today - timedelta(days=6), time.min)
    week_sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.started_at >= week_start)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )

    week_volume = 0.0
    recent_prs: list[RecentPR] = []
    for ws in week_sessions:
        summary = session_summary(ws.id, db=db, _=None)
        week_volume += summary.total_volume_kg
        for pr in summary.prs_hit:
            recent_prs.append(RecentPR(**pr.model_dump(), date=ws.started_at.date()))

    training = DashboardTraining(
        week_volume_kg=round(week_volume, 1),
        sessions_this_week=len(week_sessions),
        recent_prs=recent_prs[:MAX_RECENT_PRS],
    )

    return DashboardOut(
        weight=weight,
        steps=steps,
        sleep=sleep,
        nutrition_today=nutrition_today,
        targets=targets,
        training=training,
    )
