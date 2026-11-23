"""
Stats and PR (personal record) calculations.

1RM formula (Epley): weight × (1 + reps / 30)
  - Only applied to working (non-warmup) sets
  - Reps capped at 12 for the estimate (heavy triples are more accurate than 20-rep sets)

PR categories tracked per exercise:
  - heaviest_weight_kg   : heaviest single working set
  - best_estimated_1rm   : best Epley 1RM across all working sets
  - best_set_volume      : highest weight × reps for a single working set

Routes:
  GET /api/stats/prs                   — all PRs
  GET /api/stats/prs/{exercise_id}     — PR for one exercise
  GET /api/stats/exercise/{id}/history — per-session history of 1RM + volume
  GET /api/stats/volume/weekly         — weekly training volume (kg × reps)
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.core.auth import require_auth
from app.core.db import get_db
from app.models import Exercise, Session, SessionExercise, Set, User
from app.schemas import PRRecord, SessionSummaryStats
from app.services.diet.weight_trend import iso_week_start
from app.services.training.muscles import MUSCLE_GROUPS, resolved_volume_targets
from app.services.training.stats import (
    compute_prs_for_exercise,
    epley_1rm,
    session_summary,
)
from app.services.user_settings import get_or_create_settings

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/session/{session_id}/summary", response_model=SessionSummaryStats)
def get_session_summary(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """The finish-workout summary for a session (duration, volume, PRs hit)."""
    session = db.get(Session, session_id)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_summary(db, session, current_user.id)


@router.get("/prs", response_model=list[PRRecord])
def all_prs(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Return current PRs for every exercise that has logged working sets."""
    exercise_ids = (
        db.query(SessionExercise.exercise_id)
        .join(Set)
        .filter(Set.user_id == current_user.id, Set.is_completed == True, Set.is_warmup == False)
        .distinct()
        .all()
    )
    results = []
    for (eid,) in exercise_ids:
        pr = compute_prs_for_exercise(eid, db, current_user.id)
        if pr:
            results.append(pr)
    return sorted(results, key=lambda x: x.exercise_name)


@router.get("/prs/{exercise_id}", response_model=Optional[PRRecord])
def exercise_pr(
    exercise_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return compute_prs_for_exercise(exercise_id, db, current_user.id)


@router.get("/exercise/{exercise_id}/history")
def exercise_history(
    exercise_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Per-session history for charting: estimated 1RM and total volume per session.
    Returns a list of {date, session_id, estimated_1rm, volume_kg} objects.
    """
    rows = (
        db.query(Session, SessionExercise, Set)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .filter(
            Session.user_id == current_user.id,
            SessionExercise.exercise_id == exercise_id,
            Set.is_completed == True,
            Set.is_warmup == False,
            Set.reps > 0,
            Set.weight_kg > 0,
        )
        .order_by(Session.started_at)
        .all()
    )

    # Group by session
    by_session: dict[int, dict] = {}
    for session, se, s in rows:
        if session.id not in by_session:
            by_session[session.id] = {
                "session_id": session.id,
                "date": session.started_at.date().isoformat(),
                "sets": [],
            }
        by_session[session.id]["sets"].append(s)

    history = []
    for sid, data in by_session.items():
        sets = data["sets"]
        best_1rm = max(epley_1rm(s.weight_kg, s.reps) for s in sets)
        total_volume = sum(s.weight_kg * s.reps for s in sets)
        history.append({
            "session_id": sid,
            "date": data["date"],
            "estimated_1rm": round(best_1rm, 1),
            "volume_kg": round(total_volume, 1),
        })

    return history


@router.get("/volume/weekly")
def weekly_volume(
    weeks: int = Query(8, ge=1, le=52),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Total training volume (sum of weight×reps for working completed sets)
    grouped by ISO week, for the last N weeks. Used for the dashboard chart.
    """
    since = datetime.utcnow() - timedelta(weeks=weeks)
    rows = (
        db.query(Session.started_at, Set.weight_kg, Set.reps)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .filter(
            Session.user_id == current_user.id,
            Session.started_at >= since,
            Set.is_completed == True,
            Set.is_warmup == False,
            Set.reps > 0,
            Set.weight_kg > 0,
        )
        .all()
    )

    # Aggregate by ISO year-week string, e.g. "2025-W01"
    by_week: dict[str, float] = defaultdict(float)
    for started_at, weight, reps in rows:
        iso = started_at.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        by_week[key] += weight * reps

    return [
        {"week": k, "volume_kg": round(v, 1)}
        for k, v in sorted(by_week.items())
    ]


# ---------------------------------------------------------------------------
# Sets-per-week per primary muscle group
# ---------------------------------------------------------------------------

def _resolved_targets(db: DBSession, user_id: int) -> dict[str, tuple[int, int]]:
    return resolved_volume_targets(get_or_create_settings(db, user_id).volume_targets)


@router.get("/volume-targets")
def get_volume_targets(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Effective weekly working-set target ranges per muscle (defaults with the
    user's overrides merged) — the single table this view and the generator read."""
    return {m: {"low": lo, "high": hi} for m, (lo, hi) in _resolved_targets(db, current_user.id).items()}


@router.get("/sets-per-week")
def sets_per_week(
    weeks: int = Query(8, ge=1, le=52),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Completed WORKING sets (not warm-ups) per primary muscle group per ISO
    week (Monday start), for the last N weeks, against each muscle's target
    range. Only the exercise's primary muscle group counts."""
    today = date.today()
    current_week = iso_week_start(today)
    first_week = current_week - timedelta(weeks=weeks - 1)
    since = datetime.combine(first_week, time.min)

    rows = (
        db.query(Session.started_at, Exercise.primary_muscle_group)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .join(Exercise, SessionExercise.exercise_id == Exercise.id)
        .filter(
            Session.user_id == current_user.id,
            Session.started_at >= since,
            Set.is_completed == True,   # noqa: E712
            Set.is_warmup == False,     # noqa: E712
        )
        .all()
    )

    counts: dict[tuple[date, str], int] = defaultdict(int)
    for started_at, group in rows:
        if not group:
            continue
        counts[(iso_week_start(started_at.date()), group)] += 1

    week_starts = [first_week + timedelta(weeks=i) for i in range(weeks)]
    targets = _resolved_targets(db, current_user.id)
    return {
        "muscle_groups": MUSCLE_GROUPS,
        "targets": {m: {"low": lo, "high": hi} for m, (lo, hi) in targets.items()},
        "weeks": [
            {
                "week_start": wk.isoformat(),
                "is_current": wk == current_week,
                "counts": {m: counts.get((wk, m), 0) for m in MUSCLE_GROUPS},
            }
            for wk in week_starts
        ],
    }
