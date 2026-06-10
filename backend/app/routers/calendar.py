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
from app.models import NutritionDay, Session as WorkoutSession, SleepLog, StepsLog, WeightLog
from app.routers.stats import session_summary
from app.schemas import CalendarDay, DayDetailOut, DaySession, MonthCalendarOut

router = APIRouter(tags=["calendar"])


def _sessions_on(db: DBSession, day: date) -> list[WorkoutSession]:
    start = datetime.combine(day, time.min)
    return (
        db.query(WorkoutSession)
        .filter(WorkoutSession.started_at >= start,
                WorkoutSession.started_at < start + timedelta(days=1))
        .order_by(WorkoutSession.started_at)
        .all()
    )


@router.get("/api/calendar/{year}/{month}", response_model=MonthCalendarOut)
def month_calendar(
    year: int,
    month: int,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    if not 1 <= month <= 12:
        raise HTTPException(status_code=422, detail="month must be 1-12")

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
        .filter(WorkoutSession.started_at >= month_start,
                WorkoutSession.started_at < month_end)
        .all()
    ):
        day_of(started_at.date()).sessions += 1

    for row in db.query(WeightLog).filter(WeightLog.date.between(first, last)).all():
        day_of(row.date).has_weight = True
    for row in db.query(StepsLog).filter(StepsLog.date.between(first, last)).all():
        day_of(row.date).steps = row.steps
    for row in db.query(SleepLog).filter(SleepLog.date.between(first, last)).all():
        day_of(row.date).has_sleep = True
    for row in db.query(NutritionDay).filter(NutritionDay.date.between(first, last)).all():
        day_of(row.date).has_nutrition = True

    return MonthCalendarOut(
        year=year,
        month=month,
        days=sorted(days.values(), key=lambda d: d.date),
    )


@router.get("/api/day/{day}", response_model=DayDetailOut)
def day_detail(
    day: date,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    sessions = []
    for ws in _sessions_on(db, day):
        summary = session_summary(ws.id, db=db, _=None)
        sessions.append(DaySession(
            id=ws.id,
            name=ws.name,
            duration_minutes=summary.duration_minutes,
            total_volume_kg=summary.total_volume_kg,
            completed_sets=summary.completed_sets,
        ))

    weight = db.query(WeightLog).filter(WeightLog.date == day).first()
    steps = db.query(StepsLog).filter(StepsLog.date == day).first()
    sleep = db.query(SleepLog).filter(SleepLog.date == day).first()
    nutrition = db.query(NutritionDay).filter(NutritionDay.date == day).first()

    return DayDetailOut(
        date=day,
        sessions=sessions,
        weight_kg=weight.weight_kg if weight else None,
        steps=steps.steps if steps else None,
        sleep=sleep,
        nutrition=nutrition,
    )
