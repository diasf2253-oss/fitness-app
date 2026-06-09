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
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Session, SessionExercise, Set
from app.schemas import PRRecord

router = APIRouter(prefix="/api/stats", tags=["stats"])


def epley_1rm(weight_kg: float, reps: int) -> float:
    """
    Epley formula for estimated 1-rep max.
    Reps are capped at 12 — higher rep sets have low 1RM prediction accuracy.
    Returns weight_kg unchanged for single-rep sets (mathematically correct).
    """
    capped_reps = min(reps, 12)
    if capped_reps <= 1:
        return weight_kg
    return weight_kg * (1 + capped_reps / 30)


def compute_prs_for_exercise(exercise_id: int, db: DBSession) -> Optional[PRRecord]:
    """
    Scan all completed working sets for an exercise and return the current PRs.
    Returns None if no completed working sets exist.
    """
    sets = (
        db.query(Set)
        .join(SessionExercise)
        .filter(
            SessionExercise.exercise_id == exercise_id,
            Set.is_completed == True,
            Set.is_warmup == False,
            Set.reps > 0,
            Set.weight_kg > 0,
        )
        .all()
    )

    if not sets:
        return None

    ex = db.get(Exercise, exercise_id)
    best_weight = max(s.weight_kg for s in sets)
    best_1rm = max(epley_1rm(s.weight_kg, s.reps) for s in sets)
    best_volume = max(s.weight_kg * s.reps for s in sets)

    return PRRecord(
        exercise_id=exercise_id,
        exercise_name=ex.name if ex else str(exercise_id),
        heaviest_weight_kg=best_weight,
        best_estimated_1rm=round(best_1rm, 1),
        best_set_volume=best_volume,
    )


@router.get("/prs", response_model=list[PRRecord])
def all_prs(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Return current PRs for every exercise that has logged working sets."""
    exercise_ids = (
        db.query(SessionExercise.exercise_id)
        .join(Set)
        .filter(Set.is_completed == True, Set.is_warmup == False)
        .distinct()
        .all()
    )
    results = []
    for (eid,) in exercise_ids:
        pr = compute_prs_for_exercise(eid, db)
        if pr:
            results.append(pr)
    return sorted(results, key=lambda x: x.exercise_name)


@router.get("/prs/{exercise_id}", response_model=Optional[PRRecord])
def exercise_pr(
    exercise_id: int,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    return compute_prs_for_exercise(exercise_id, db)


@router.get("/exercise/{exercise_id}/history")
def exercise_history(
    exercise_id: int,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
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
    _: None = Depends(require_auth),
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
