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
from app.models import Exercise
from app.muscles import suggest_muscle_group
from app.schemas import ExerciseCreate, ExerciseOut, ExerciseUpdate

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(
    search: Optional[str] = Query(None, description="Substring search on name"),
    muscle: Optional[str] = Query(None, description="Filter by primary_muscle"),
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Return all exercises, optionally filtered by name search and/or muscle group."""
    q = db.query(Exercise)
    if search:
        q = q.filter(Exercise.name.ilike(f"%{search}%"))
    if muscle:
        q = q.filter(Exercise.primary_muscle.ilike(f"%{muscle}%"))
    return q.order_by(Exercise.name).all()


@router.post("", response_model=ExerciseOut, status_code=201)
def create_exercise(
    body: ExerciseCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Create a new custom exercise. The canonical muscle group is auto-tagged
    from the name when not provided, so custom exercises feed the Ranks map."""
    existing = db.query(Exercise).filter(Exercise.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Exercise name already exists")
    data = body.model_dump()
    if not data.get("primary_muscle_group"):
        data["primary_muscle_group"] = suggest_muscle_group(body.name, body.primary_muscle)
    ex = Exercise(**data)
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    ex = db.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


@router.put("/{exercise_id}", response_model=ExerciseOut)
def update_exercise(
    exercise_id: int,
    body: ExerciseUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_auth),
):
    ex = db.get(Exercise, exercise_id)
    if not ex:
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
    _: None = Depends(require_auth),
):
    ex = db.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    if not ex.is_custom:
        raise HTTPException(status_code=403, detail="Cannot delete built-in exercises")
    db.delete(ex)
    db.commit()
