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

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Session, SessionExercise, Set, User
from app.muscles import MUSCLE_GROUPS, resolved_volume_targets
from app.routers.settings import get_or_create_settings
from app.schemas import PRHit, PRRecord, SessionSummaryStats
from app.weight_trend import iso_week_start

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


def compute_prs_for_exercise(exercise_id: int, db: DBSession, user_id: int) -> Optional[PRRecord]:
    """
    Scan all completed working sets for an exercise and return the current PRs.
    Returns None if no completed working sets exist.
    """
    sets = (
        db.query(Set)
        .join(SessionExercise)
        .filter(
            Set.user_id == user_id,
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


@router.get("/session/{session_id}/summary", response_model=SessionSummaryStats)
def session_summary(
    session_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Compute the finish-workout summary for a session:
      - duration (started_at → ended_at)
      - total volume of completed working sets
      - PRs hit during this session

    PR detection compares each exercise's best set IN this session against its
    best set across ALL OTHER sessions. If the session beats the prior best
    (or there's no prior record), it counts as a PR.
    """
    user_id = current_user.id
    session = db.get(Session, session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Duration
    duration = None
    if session.ended_at:
        duration = int((session.ended_at - session.started_at).total_seconds() // 60)

    # Gather completed working sets in this session, grouped by exercise
    by_exercise: dict[int, list[Set]] = defaultdict(list)
    completed_sets = 0
    total_volume = 0.0
    for se in session.exercises:
        for s in se.sets:
            if s.is_completed and not s.is_warmup and s.reps > 0 and s.weight_kg > 0:
                by_exercise[se.exercise_id].append(s)
                completed_sets += 1
                total_volume += s.weight_kg * s.reps

    prs_hit: list[PRHit] = []

    for exercise_id, sets in by_exercise.items():
        ex = db.get(Exercise, exercise_id)
        ex_name = ex.name if ex else str(exercise_id)

        # This session's bests for this exercise
        session_best_weight = max(s.weight_kg for s in sets)
        session_best_1rm = max(epley_1rm(s.weight_kg, s.reps) for s in sets)
        session_best_volume = max(s.weight_kg * s.reps for s in sets)

        # Prior bests: all completed working sets for this exercise from OTHER sessions
        prior_sets = (
            db.query(Set)
            .join(SessionExercise)
            .filter(
                Set.user_id == user_id,
                SessionExercise.exercise_id == exercise_id,
                SessionExercise.session_id != session_id,
                Set.is_completed == True,
                Set.is_warmup == False,
                Set.reps > 0,
                Set.weight_kg > 0,
            )
            .all()
        )

        prior_weight = max((s.weight_kg for s in prior_sets), default=None)
        prior_1rm = max((epley_1rm(s.weight_kg, s.reps) for s in prior_sets), default=None)
        prior_volume = max((s.weight_kg * s.reps for s in prior_sets), default=None)

        # Heaviest weight PR
        if prior_weight is None or session_best_weight > prior_weight:
            prs_hit.append(PRHit(
                exercise_id=exercise_id, exercise_name=ex_name,
                kind="heaviest", value=round(session_best_weight, 1),
                previous_best=round(prior_weight, 1) if prior_weight else None,
            ))
        # Best estimated 1RM PR
        if prior_1rm is None or session_best_1rm > prior_1rm:
            prs_hit.append(PRHit(
                exercise_id=exercise_id, exercise_name=ex_name,
                kind="best_1rm", value=round(session_best_1rm, 1),
                previous_best=round(prior_1rm, 1) if prior_1rm else None,
            ))
        # Best single-set volume PR
        if prior_volume is None or session_best_volume > prior_volume:
            prs_hit.append(PRHit(
                exercise_id=exercise_id, exercise_name=ex_name,
                kind="best_volume", value=round(session_best_volume, 1),
                previous_best=round(prior_volume, 1) if prior_volume else None,
            ))

    return SessionSummaryStats(
        session_id=session_id,
        duration_minutes=duration,
        total_volume_kg=round(total_volume, 1),
        completed_sets=completed_sets,
        prs_hit=prs_hit,
    )


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
