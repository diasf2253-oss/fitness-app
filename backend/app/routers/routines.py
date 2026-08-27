"""
Routine CRUD.
GET    /api/routines          — list all routines
POST   /api/routines          — create routine
GET    /api/routines/{id}     — get routine with exercises
PUT    /api/routines/{id}     — replace routine (name + exercise list)
DELETE /api/routines/{id}     — delete routine
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Routine, RoutineExercise, User
from app.schemas import RoutineCreate, RoutineOut, RoutineUpdate

router = APIRouter(prefix="/api/routines", tags=["routines"])


def _build_routine_exercises(
    db: Session, routine: Routine, exercise_defs: list, user_id: int
) -> None:
    """
    Replace all RoutineExercise rows for a routine with the provided list.
    Validates that each exercise_id exists and is visible to this user
    (global library or their own custom exercise).
    """
    # Clear existing rows (cascade handles DB deletion)
    routine.exercises.clear()
    for ex_def in exercise_defs:
        ex = (
            db.query(Exercise)
            .filter(
                Exercise.id == ex_def.exercise_id,
                or_(Exercise.user_id.is_(None), Exercise.user_id == user_id),
            )
            .first()
        )
        if not ex:
            raise HTTPException(
                status_code=404,
                detail=f"Exercise {ex_def.exercise_id} not found",
            )
        routine.exercises.append(
            RoutineExercise(
                user_id=user_id,
                exercise_id=ex_def.exercise_id,
                position=ex_def.position,
                target_sets=ex_def.target_sets,
                target_rep_low=ex_def.target_rep_low,
                target_rep_high=ex_def.target_rep_high,
                rest_seconds=ex_def.rest_seconds,
                target_rir=ex_def.target_rir,
            )
        )


@router.get("", response_model=list[RoutineOut])
def list_routines(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return db.query(Routine).filter(Routine.user_id == current_user.id).order_by(Routine.name).all()


@router.post("", response_model=RoutineOut, status_code=201)
def create_routine(
    body: RoutineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    routine = Routine(user_id=current_user.id, name=body.name, notes=body.notes)
    db.add(routine)
    db.flush()  # assigns routine.id before we attach exercises
    if body.exercises:
        _build_routine_exercises(db, routine, body.exercises, current_user.id)
    db.commit()
    db.refresh(routine)
    return routine


@router.get("/{routine_id}", response_model=RoutineOut)
def get_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    r = db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Routine not found")
    return r


@router.put("/{routine_id}", response_model=RoutineOut)
def update_routine(
    routine_id: int,
    body: RoutineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    r = db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Routine not found")
    if body.name is not None:
        r.name = body.name
    if body.notes is not None:
        r.notes = body.notes
    if body.exercises is not None:
        _build_routine_exercises(db, r, body.exercises, current_user.id)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{routine_id}", status_code=204)
def delete_routine(
    routine_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    r = db.get(Routine, routine_id)
    if not r or r.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Routine not found")
    db.delete(r)
    db.commit()
