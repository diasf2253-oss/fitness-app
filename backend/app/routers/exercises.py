"""
Exercise library CRUD.
GET  /api/exercises          — list with optional search and muscle filter
POST /api/exercises          — create custom exercise
GET  /api/exercises/{id}     — get single exercise
PUT  /api/exercises/{id}     — update exercise
DELETE /api/exercises/{id}   — delete (only custom exercises)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, User
from app.muscles import suggest_muscle_group
from app.schemas import ExerciseCreate, ExerciseOut, ExerciseUpdate

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


def _visible_to(db: Session, user_id: int):
    """The shared global library plus this user's own custom exercises."""
    return db.query(Exercise).filter(
        or_(Exercise.user_id.is_(None), Exercise.user_id == user_id)
    )


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    search: Optional[str] = Query(None, description="Substring search on name"),
    muscle: Optional[str] = Query(None, description="Filter by primary_muscle"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Return all exercises visible to this user (global + their own custom
    ones), optionally filtered by name search and/or muscle group."""
    q = _visible_to(db, current_user.id)
    if search:
        q = q.filter(Exercise.name.ilike(f"%{search}%"))
    if muscle:
        q = q.filter(Exercise.primary_muscle.ilike(f"%{muscle}%"))
    return q.order_by(Exercise.name).all()


@router.post("", response_model=ExerciseOut, status_code=201)
def create_exercise(
    body: ExerciseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Create a new custom exercise, owned by the caller. The canonical
    muscle group is auto-tagged from the name when not provided, so custom
    exercises feed the Ranks map. `name` is globally unique across every
    user's library and the seeded set (a known v1 limitation)."""
    existing = db.query(Exercise).filter(Exercise.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Exercise name already exists")
    data = body.model_dump()
    if not data.get("primary_muscle_group"):
        data["primary_muscle_group"] = suggest_muscle_group(body.name, body.primary_muscle)
    ex = Exercise(user_id=current_user.id, **data)
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    ex = _visible_to(db, current_user.id).filter(Exercise.id == exercise_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


@router.put("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(
    exercise_id: int,
    body: ExerciseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    ex = db.get(Exercise, exercise_id)
    if not ex or ex.user_id != current_user.id:
        # user_id is None for the seeded global library — never editable
        # here, regardless of who asks.
        raise HTTPException(status_code=404, detail="Exercise not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(ex, field, value)
    db.commit()
    db.refresh(ex)
    return ex


@router.delete("/{exercise_id}", status_code=204)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    ex = db.get(Exercise, exercise_id)
    if not ex or ex.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Exercise not found")
    if not ex.is_custom:
        raise HTTPException(status_code=403, detail="Cannot delete built-in exercises")
    db.delete(ex)
    db.commit()
