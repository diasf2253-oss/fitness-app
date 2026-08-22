"""
Calendar + day-detail endpoints — power the desktop right rail.

GET /api/calendar/{year}/{month}  — per-day data markers for the month grid
GET /api/day/{day}                — everything recorded on one date

Workout numbers reuse stats.session_summary (no duplicated math).
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import (
    NutritionDay, PlanItem, Session as WorkoutSession, SleepLog, StepsLog,
    Tracker, TrackerLog, User, WeightLog,
)
from app.routers.health import DERIVED_SOURCES, real_weight_points, resolved_weight_for
from app.routers.stats import session_summary
from app.schemas import (
    CalendarDay, DayDetailOut, DaySession, DayTracker, MonthCalendarOut, PlanItemOut,
)

router = APIRouter(tags=["calendar"])


def _sessions_on(db: DBSession, day: date, user_id: int) -> list[WorkoutSession]:
    start = datetime.combine(day, time.min)
    return (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= start,
                WorkoutSession.started_at < start + timedelta(days=1))
        .order_by(WorkoutSession.started_at)
        .all()
    )


@router.get("/api/calendar/{year}/{month}", response_model=MonthCalendarOut)
def month_calendar(
    year: int,
    month: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="month must be 1-12")

    user_id = current_user.id
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    month_start = datetime.combine(first, time.min)
    month_end = datetime.combine(last + timedelta(days=1), time.min)

    days: dict[date, CalendarDay] = {}

    def day_of(d: date) -> CalendarDay:
        if d not in days:
            days[d] = CalendarDay(date=d)
        return days[d]

    for (started_at,) in (
        db.query(WorkoutSession.started_at)
        .filter(WorkoutSession.user_id == user_id,
                WorkoutSession.started_at >= month_start,
                WorkoutSession.started_at < month_end)
        .all()
    ):
        day_of(started_at.date()).sessions += 1

    for row in (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id, WeightLog.date.between(first, last),
                WeightLog.source.notin_(DERIVED_SOURCES))
        .all()
    ):
        day_of(row.date).has_weight = True
    for row in db.query(StepsLog).filter(StepsLog.user_id == user_id, StepsLog.date.between(first, last)).all():
        day_of(row.date).steps = row.steps
    for row in db.query(SleepLog).filter(SleepLog.user_id == user_id, SleepLog.date.between(first, last)).all():
        day_of(row.date).has_sleep = True
    for row in db.query(NutritionDay).filter(NutritionDay.user_id == user_id, NutritionDay.date.between(first, last)).all():
        day_of(row.date).has_nutrition = True
    for row in (
        db.query(TrackerLog)
        .join(Tracker, Tracker.id == TrackerLog.tracker_id)
        .filter(Tracker.user_id == user_id, TrackerLog.date.between(first, last))
        .all()
    ):
        day_of(row.date).trackers += 1
    for row in db.query(PlanItem).filter(PlanItem.user_id == user_id, PlanItem.date.between(first, last)).all():
        day_of(row.date).plan_items += 1

    return MonthCalendarOut(
        year=year,
        month=month,
        days=sorted(days.values(), key=lambda d: d.date),
    )


@router.get("/api/day/{day}", response_model=DayDetailOut)
def day_detail(
    day: date,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    user_id = current_user.id
    sessions = []
    for ws in _sessions_on(db, day, user_id):
        summary = session_summary(ws.id, db=db, current_user=current_user)
        sessions.append(DaySession(
            id=ws.id,
            name=ws.name,
            duration_minutes=summary.duration_minutes,
            total_volume_kg=summary.total_volume_kg,
            completed_sets=summary.completed_sets,
        ))

    weight_row = db.query(WeightLog).filter(WeightLog.user_id == user_id, WeightLog.date == day).first()
    weight_kg, weight_estimated, _ = resolved_weight_for(
        day, weight_row, real_weight_points(db, user_id)
    )

    steps = db.query(StepsLog).filter(StepsLog.user_id == user_id, StepsLog.date == day).first()
    sleep = db.query(SleepLog).filter(SleepLog.user_id == user_id, SleepLog.date == day).first()
    nutrition = db.query(NutritionDay).filter(NutritionDay.user_id == user_id, NutritionDay.date == day).first()

    tracker_rows = (
        db.query(Tracker, TrackerLog)
        .join(TrackerLog, TrackerLog.tracker_id == Tracker.id)
        .filter(Tracker.user_id == user_id, TrackerLog.date == day)
        .order_by(Tracker.position, Tracker.id)
        .all()
    )
    trackers = [
        DayTracker(
            name=t.name, kind=t.kind, unit=t.unit,
            value_num=log.value_num, value_text=log.value_text,
        )
        for t, log in tracker_rows
    ]

    plan = (
        db.query(PlanItem)
        .filter(PlanItem.user_id == user_id, PlanItem.date == day)
        .order_by(PlanItem.position, PlanItem.start_time, PlanItem.id)
        .all()
    )

    return DayDetailOut(
        date=day,
        sessions=sessions,
        weight_kg=weight_kg,
        weight_estimated=weight_estimated,
        steps=steps.steps if steps else None,
        sleep=sleep,
        nutrition=nutrition,
        trackers=trackers,
        plan=[PlanItemOut.model_validate(p) for p in plan],
    )
