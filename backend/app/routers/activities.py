"""Activity log — sport sessions outside the gym (football / judo / padel).

GET    /api/activities?days=30   — recent activities, newest first
POST   /api/activities           — log one
DELETE /api/activities/{id}      — remove one
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Activity, User, WeightLog
from app.schemas import ActivityCreate, ActivityOut
from app.activity_burn import activity_kcal

router = APIRouter(prefix="/api/activities", tags=["activities"])


def latest_weight(db: DBSession, user_id: int) -> float:
    """Most recent logged bodyweight, for the burn estimate. 75 kg fallback."""
    row = (
        db.query(WeightLog)
        .filter(WeightLog.user_id == user_id)
        .order_by(WeightLog.date.desc())
        .first()
    )
    return row.weight_kg if row else 75.0


def to_out(a: Activity, weight_kg: float) -> ActivityOut:
    return ActivityOut(
        id=a.id,
        date=a.date,
        type=a.type,
        duration_min=a.duration_min,
        notes=a.notes,
        calories_est=activity_kcal(a.type, a.duration_min, weight_kg),
    )


@router.get("", response_model=list[ActivityOut])
def list_activities(
    days: int = Query(30, ge=1, le=365),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    since = date.today() - timedelta(days=days)
    rows = (
        db.query(Activity)
        .filter(Activity.user_id == current_user.id, Activity.date >= since)
        .order_by(Activity.date.desc(), Activity.id.desc())
        .all()
    )
    w = latest_weight(db, current_user.id)
    return [to_out(a, w) for a in rows]


@router.post("", response_model=ActivityOut, status_code=201)
def create_activity(
    body: ActivityCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    a = Activity(
        user_id=current_user.id,
        date=body.date,
        type=body.type.strip().lower(),
        duration_min=body.duration_min,
        notes=body.notes,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return to_out(a, latest_weight(db, current_user.id))


@router.delete("/{activity_id}", status_code=204)
def delete_activity(
    activity_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    a = db.get(Activity, activity_id)
    if not a or a.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(a)
    db.commit()
    return None
