"""Training streak — rewards consistent training without punishing rest days.

The streak counts logged workouts; it survives up to ``rest_gap`` rest days
between workouts and only breaks when more than that many consecutive days
pass with no logged workout (default gap 1 → a normal rest day is fine, 2+
empty days in a row breaks it).

Two halves:
  - compute_streak: pure logic, no database (easy to unit-test).
  - streak_snapshot: gathers the user's active days from the database, runs
    compute_streak and persists the result onto StreakState (structured so a
    future points/gamification layer can hook on without reshaping this
    computation). Shared by GET /api/streak, the dashboard and the report.

An "active day" is a real workout, a logged sport session (football/judo/
padel…), or a 10k-step day — workbook ruling T6a.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session as DBSession

from app.models import Activity, Session, SessionExercise, Set, StepsLog, StreakState
from app.schemas import StreakOut
from app.services.user_settings import get_or_create_settings


@dataclass
class StreakResult:
    current: int                       # length of the live chain (0 if broken)
    longest: int                       # longest chain ever
    last_workout_date: date | None
    alive: bool                        # is the current streak still going?
    at_risk: bool                      # alive, but one more rest day breaks it


def compute_streak(workout_dates, rest_gap: int = 1, today: date | None = None) -> StreakResult:
    """Current and longest streak from the set of dates that had a logged
    workout. Consecutive workouts up to ``rest_gap + 1`` days apart keep the
    chain; a larger gap breaks it."""
    if today is None:
        today = date.today()
    days = sorted(set(workout_dates))
    if not days:
        return StreakResult(0, 0, None, False, False)

    max_apart = rest_gap + 1   # consecutive workouts this many days apart still chain

    # Longest chain anywhere in history.
    longest = chain = 1
    for prev, cur in zip(days, days[1:]):
        chain = chain + 1 if (cur - prev).days <= max_apart else 1
        longest = max(longest, chain)

    # Chain ending at the most recent workout.
    current_chain = 1
    i = len(days) - 1
    while i > 0 and (days[i] - days[i - 1]).days <= max_apart:
        current_chain += 1
        i -= 1

    last = days[-1]
    elapsed = (today - last).days
    alive = elapsed <= max_apart
    return StreakResult(
        current=current_chain if alive else 0,
        longest=longest,
        last_workout_date=last,
        alive=alive,
        at_risk=alive and elapsed == max_apart,
    )


# ---------------------------------------------------------------------------
# Database side — active days in, persisted snapshot out
# ---------------------------------------------------------------------------

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
