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
from app.models import Activity, Session, SessionExercise, Set, StepsLog, StreakState
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


ACTIVE_STEPS_THRESHOLD = 10_000  # a 10k-step day counts as active (T6a)


def _active_dates(db: DBSession) -> set[date]:
    """Dates that keep the streak alive: a real workout, a logged sport
    session, or a 10k-step day. Sample-seeded rows never count."""
    dates = _workout_dates(db)
    dates |= {
        r.date
        for r in db.query(Activity.date).filter(Activity.source != "sample").distinct().all()
    }
    dates |= {
        r.date
        for r in db.query(StepsLog.date)
        .filter(StepsLog.steps >= ACTIVE_STEPS_THRESHOLD, StepsLog.source != "sample")
        .all()
    }
    return dates


def streak_snapshot(db: DBSession) -> StreakOut:
    """Recompute the streak, persist the snapshot (longest is monotonic), and
    return it. Shared by GET /api/streak and the dashboard."""
    settings = get_or_create_settings(db)
    result = compute_streak(_active_dates(db), settings.streak_rest_gap)

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
