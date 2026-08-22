"""
Trackers (Phase 6) — the generic "track anything" system.

GET    /api/trackers              — active trackers + today's value + streaks
POST   /api/trackers              — create (habit | scale | number | text)
PATCH  /api/trackers/{id}         — rename / reorder / archive
DELETE /api/trackers/{id}         — delete tracker AND its history
POST   /api/trackers/{id}/log     — upsert one day's entry
GET    /api/trackers/{id}/series  — date-ordered history for charts

Log semantics: one row per (tracker, date); posting with both values
null clears the day (so un-checking a habit or emptying the journal
deletes the row rather than storing an empty husk).
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Tracker, TrackerLog, User
from app.schemas import (
    TRACKER_KINDS, TrackerCreate, TrackerLogOut, TrackerLogValue,
    TrackerOut, TrackerUpdate,
)

router = APIRouter(prefix="/api/trackers", tags=["trackers"])


def habit_streak(db: DBSession, tracker_id: int, today: date) -> int:
    """
    Consecutive done-days ending today. An unlogged *today* doesn't break
    the streak (the day isn't over yet) — counting then starts yesterday.
    """
    done_dates = {
        row.date
        for row in db.query(TrackerLog.date)
        .filter(TrackerLog.tracker_id == tracker_id, TrackerLog.value_num >= 1)
        .all()
    }
    streak = 0
    d = today
    if d not in done_dates:
        d -= timedelta(days=1)
    while d in done_dates:
        streak += 1
        d -= timedelta(days=1)
    return streak


def _get_tracker(db: DBSession, tracker_id: int, user_id: int) -> Tracker:
    tracker = db.get(Tracker, tracker_id)
    if not tracker or tracker.user_id != user_id:
        raise HTTPException(status_code=404, detail="Tracker not found")
    return tracker


@router.get("", response_model=list[TrackerOut])
def list_trackers(
    include_archived: bool = Query(False),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Trackers for the daily check-in: ordered, with today's entry filled in."""
    q = db.query(Tracker).filter(Tracker.user_id == current_user.id)
    if not include_archived:
        q = q.filter(Tracker.is_archived.is_(False))
    trackers = q.order_by(Tracker.position, Tracker.id).all()

    today = date.today()
    out = []
    for t in trackers:
        log = (
            db.query(TrackerLog)
            .filter(TrackerLog.tracker_id == t.id, TrackerLog.date == today)
            .first()
        )
        item = TrackerOut.model_validate(t)
        if log:
            item.today = TrackerLogValue(
                date=log.date, value_num=log.value_num, value_text=log.value_text
            )
        if t.kind == "habit":
            item.streak = habit_streak(db, t.id, today)
        out.append(item)
    return out


@router.post("", response_model=TrackerOut, status_code=201)
def create_tracker(
    body: TrackerCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    if body.kind not in TRACKER_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {TRACKER_KINDS}")
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="name is required")

    max_pos = (
        db.query(Tracker.position)
        .filter(Tracker.user_id == current_user.id)
        .order_by(Tracker.position.desc())
        .first()
    )
    tracker = Tracker(
        user_id=current_user.id,
        name=body.name.strip(),
        kind=body.kind,
        unit=body.unit,
        position=(max_pos[0] + 1) if max_pos else 0,
    )
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    return tracker


@router.patch("/{tracker_id}", response_model=TrackerOut)
def update_tracker(
    tracker_id: int,
    body: TrackerUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    tracker = _get_tracker(db, tracker_id, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(tracker, field, value)
    db.commit()
    db.refresh(tracker)
    return tracker


@router.delete("/{tracker_id}", status_code=204)
def delete_tracker(
    tracker_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Hard delete, history included. The UI offers archive as the soft path."""
    tracker = _get_tracker(db, tracker_id, current_user.id)
    db.delete(tracker)
    db.commit()


@router.post("/{tracker_id}/log", response_model=Optional[TrackerLogOut])
def log_tracker(
    tracker_id: int,
    body: TrackerLogValue,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Upsert one day's entry; null values clear the day (returns null)."""
    _get_tracker(db, tracker_id, current_user.id)
    row = (
        db.query(TrackerLog)
        .filter(TrackerLog.tracker_id == tracker_id, TrackerLog.date == body.date)
        .first()
    )

    text = body.value_text.strip() if body.value_text else None
    if body.value_num is None and not text:
        if row:
            db.delete(row)
            db.commit()
        return None

    if row:
        row.value_num = body.value_num
        row.value_text = text
    else:
        row = TrackerLog(
            tracker_id=tracker_id, date=body.date,
            value_num=body.value_num, value_text=text,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{tracker_id}/series", response_model=list[TrackerLogOut])
def tracker_series(
    tracker_id: int,
    days: int = Query(90, ge=1, le=730),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    _get_tracker(db, tracker_id, current_user.id)
    since = date.today() - timedelta(days=days)
    return (
        db.query(TrackerLog)
        .filter(TrackerLog.tracker_id == tracker_id, TrackerLog.date >= since)
        .order_by(TrackerLog.date)
        .all()
    )
