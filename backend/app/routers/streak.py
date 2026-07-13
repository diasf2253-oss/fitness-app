"""Training streak — current + longest, recomputed from logged workouts and
persisted onto the single StreakState row.

GET /api/streak — the current streak snapshot
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Session, SessionExercise, Set, StreakState
from app.routers.settings import get_or_create_settings
from app.schemas import StreakOut
from app.streak import compute_streak

router = APIRouter(prefix="/api/streak", tags=["streak"])


def _workout_dates(db: DBSession) -> set[date]:
    """Calendar dates with at least one completed working set (a real workout)."""
    rows = (
        db.query(Session.started_at)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .filter(Set.is_completed == True, Set.is_warmup == False)   # noqa: E712
        .distinct()
        .all()
    )
    return {r.started_at.date() for r in rows}


def streak_snapshot(db: DBSession) -> StreakOut:
    """Recompute the streak, persist the snapshot (longest is monotonic), and
    return it. Shared by GET /api/streak and the dashboard."""
    settings = get_or_create_settings(db)
    result = compute_streak(_workout_dates(db), settings.streak_rest_gap)

    state = db.get(StreakState, 1)
    if not state:
        state = StreakState(id=1)
        db.add(state)
    state.current_streak = result.current
    state.longest_streak = max(state.longest_streak or 0, result.longest)
    state.last_workout_date = result.last_workout_date
    db.commit()

    return StreakOut(
        current=result.current,
        longest=state.longest_streak,
        last_workout_date=result.last_workout_date,
        rest_gap=settings.streak_rest_gap,
        alive=result.alive,
        at_risk=result.at_risk,
    )


@router.get("", response_model=StreakOut)
def get_streak(db: DBSession = Depends(get_db), _: None = Depends(require_auth)):
    return streak_snapshot(db)
