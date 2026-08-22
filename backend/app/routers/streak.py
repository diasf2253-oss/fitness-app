"""Training streak — current + longest, recomputed from active days and
persisted onto the single StreakState row.

An "active day" is a real workout, a logged sport session (football/judo/
padel…), or a 10k-step day — workbook ruling T6a.

GET /api/streak — the current streak snapshot
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Activity, Session, SessionExercise, Set, StepsLog, StreakState, User
from app.routers.settings import get_or_create_settings
from app.schemas import StreakOut
from app.streak import compute_streak

router = APIRouter(prefix="/api/streak", tags=["streak"])


def _workout_dates(db: DBSession, user_id: int) -> set[date]:
    """Calendar dates with at least one completed working set (a real workout)."""
    rows = (
        db.query(Session.started_at)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .filter(Session.user_id == user_id, Set.is_completed == True, Set.is_warmup == False)   # noqa: E712
        .distinct()
        .all()
    )
    return {r.started_at.date() for r in rows}


ACTIVE_STEPS_THRESHOLD = 10_000  # a 10k-step day counts as active (T6a)


def _active_dates(db: DBSession, user_id: int) -> set[date]:
    """Dates that keep the streak alive: a real workout, a logged sport
    session, or a 10k-step day. Sample-seeded rows never count."""
    dates = _workout_dates(db, user_id)
    dates |= {
        r.date
        for r in db.query(Activity.date)
        .filter(Activity.user_id == user_id, Activity.source != "sample").distinct().all()
    }
    dates |= {
        r.date
        for r in db.query(StepsLog.date)
        .filter(
            StepsLog.user_id == user_id,
            StepsLog.steps >= ACTIVE_STEPS_THRESHOLD, StepsLog.source != "sample",
        )
        .all()
    }
    return dates


def streak_snapshot(db: DBSession, user_id: int) -> StreakOut:
    """Recompute the streak, persist the snapshot (longest is monotonic), and
    return it. Shared by GET /api/streak and the dashboard."""
    settings = get_or_create_settings(db, user_id)
    result = compute_streak(_active_dates(db, user_id), settings.streak_rest_gap)

    state = db.query(StreakState).filter(StreakState.user_id == user_id).first()
    if not state:
        state = StreakState(user_id=user_id)
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
def get_streak(db: DBSession = Depends(get_db), current_user: User = Depends(require_auth)):
    return streak_snapshot(db, current_user.id)
