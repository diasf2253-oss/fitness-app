"""
Workout session management + live set logging.

Key design: a session lives in the DB from the moment you tap "Start workout".
Closing the browser tab mid-workout is safe — the session persists.

Routes:
  POST   /api/sessions                          — start a new session
  GET    /api/sessions                          — list sessions (history)
  GET    /api/sessions/{id}                     — full session detail
  PATCH  /api/sessions/{id}                     — update name / ended_at / notes
  DELETE /api/sessions/{id}                     — delete session

  POST   /api/sessions/{id}/exercises           — add exercise to session
  DELETE /api/sessions/{id}/exercises/{se_id}   — remove exercise

  POST   /api/sessions/{id}/exercises/{se_id}/sets        — add set
  PATCH  /api/sessions/{id}/exercises/{se_id}/sets/{s_id} — update set
  DELETE /api/sessions/{id}/exercises/{se_id}/sets/{s_id} — delete set

  GET    /api/sessions/{id}/previous-sets/{exercise_id}   — last session's sets
         (used to pre-fill weight/reps inputs in the workout screen)
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from sqlalchemy import or_

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Routine, RoutineExercise, Session, SessionExercise, Set, User
from app.routers.routine_notes import consume_pending_notes
from app.schemas import (
    SessionCreate, SessionExerciseCreate, SessionExerciseOut, SessionOut,
    SessionSummary, SessionUpdate, SetCreate, SetOut, SetUpdate,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    body: SessionCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Start a new workout session.
    If routine_id is given, pre-populate exercises and empty set rows
    matching the routine's target sets.
    """
    user_id = current_user.id
    session = Session(
        user_id=user_id,
        name=body.name,
        routine_id=body.routine_id,
        notes=body.notes,
    )
    db.add(session)
    db.flush()  # get session.id

    if body.routine_id:
        routine = db.get(Routine, body.routine_id)
        if not routine or routine.user_id != user_id:
            raise HTTPException(status_code=404, detail="Routine not found")
        for re in sorted(routine.exercises, key=lambda x: x.position):
            se = SessionExercise(
                user_id=user_id,
                session_id=session.id,
                exercise_id=re.exercise_id,
                position=re.position,
            )
            db.add(se)
            db.flush()
            for i in range(1, re.target_sets + 1):
                db.add(Set(
                    user_id=user_id,
                    session_exercise_id=se.id,
                    set_number=i,
                    weight_kg=0.0,
                    reps=0,
                ))
        # Surface any pending next-session notes for this routine, once.
        consume_pending_notes(db, body.routine_id, session.id, user_id)

    db.commit()
    db.refresh(session)
    return session


@router.get("/active", response_model=Optional[SessionOut])
def get_active_session(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Return the most recent in-progress session (ended_at is NULL), or null.
    The workout screen calls this on load so an interrupted workout resumes
    after a browser refresh or tab close.
    """
    return (
        db.query(Session)
        .filter(Session.user_id == current_user.id, Session.ended_at.is_(None))
        .order_by(Session.started_at.desc())
        .first()
    )


@router.get("", response_model=list[SessionSummary])
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Return sessions newest-first, paginated."""
    return (
        db.query(Session)
        .filter(Session.user_id == current_user.id)
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    s = db.get(Session, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(
    session_id: int,
    body: SessionUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    s = db.get(Session, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    s = db.get(Session, session_id)
    if not s or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s)
    db.commit()


# ---------------------------------------------------------------------------
# Previous sets — pre-fill weight/reps from last time this exercise was done
# ---------------------------------------------------------------------------

@router.get("/{session_id}/previous-sets/{exercise_id}", response_model=list[SetOut])
def get_previous_sets(
    session_id: int,
    exercise_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Find the most recent completed session (before this one) that included
    exercise_id, and return its working sets.
    Used to pre-populate the weight/reps inputs so I can beat my last session.
    """
    current = db.get(Session, session_id)
    if not current or current.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Find the latest SessionExercise for this exercise before the current session
    prev_se = (
        db.query(SessionExercise)
        .join(Session)
        .filter(
            Session.user_id == current_user.id,
            SessionExercise.exercise_id == exercise_id,
            Session.id != session_id,
            Session.ended_at.isnot(None),  # only finished sessions
        )
        .order_by(Session.started_at.desc())
        .first()
    )
    if not prev_se:
        return []
    return prev_se.sets


# ---------------------------------------------------------------------------
# Session exercises
# ---------------------------------------------------------------------------

@router.post("/{session_id}/exercises", response_model=SessionExerciseOut, status_code=201)
def add_exercise_to_session(
    session_id: int,
    body: SessionExerciseCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    user_id = current_user.id
    s = db.get(Session, session_id)
    if not s or s.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    ex = db.query(Exercise).filter(
        Exercise.id == body.exercise_id,
        or_(Exercise.user_id.is_(None), Exercise.user_id == user_id),
    ).first()
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    se = SessionExercise(
        user_id=user_id,
        session_id=session_id,
        exercise_id=body.exercise_id,
        position=body.position,
    )
    db.add(se)
    db.flush()

    for set_data in body.sets:
        db.add(Set(user_id=user_id, session_exercise_id=se.id, **set_data.model_dump()))

    db.commit()
    db.refresh(se)
    return se


@router.delete("/{session_id}/exercises/{se_id}", status_code=204)
def remove_exercise_from_session(
    session_id: int,
    se_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    se = db.get(SessionExercise, se_id)
    if not se or se.session_id != session_id or se.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session exercise not found")
    db.delete(se)
    db.commit()


# ---------------------------------------------------------------------------
# Sets
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/exercises/{se_id}/sets",
    response_model=SetOut,
    status_code=201,
)
def add_set(
    session_id: int,
    se_id: int,
    body: SetCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    se = db.get(SessionExercise, se_id)
    if not se or se.session_id != session_id or se.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session exercise not found")
    new_set = Set(user_id=current_user.id, session_exercise_id=se_id, **body.model_dump())
    db.add(new_set)
    db.commit()
    db.refresh(new_set)
    return new_set


@router.patch(
    "/{session_id}/exercises/{se_id}/sets/{set_id}",
    response_model=SetOut,
)
def update_set(
    session_id: int,
    se_id: int,
    set_id: int,
    body: SetUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    s = db.get(Set, set_id)
    if not s or s.session_exercise_id != se_id or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    # Auto-set completed_at when marking complete, if not explicitly provided
    if body.is_completed and s.completed_at is None:
        s.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return s


@router.delete(
    "/{session_id}/exercises/{se_id}/sets/{set_id}",
    status_code=204,
)
def delete_set(
    session_id: int,
    se_id: int,
    set_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    s = db.get(Set, set_id)
    if not s or s.session_exercise_id != se_id or s.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Set not found")
    db.delete(s)
    db.commit()
