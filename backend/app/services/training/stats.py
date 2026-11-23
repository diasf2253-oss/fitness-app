"""
Strength stats — the single source of truth for 1RM and PR math.

1RM formula (Epley): weight × (1 + reps / 30)
  - Only applied to working (non-warmup) sets
  - Reps capped at 12 for the estimate (heavy triples are more accurate than 20-rep sets)

PR categories tracked per exercise:
  - heaviest_weight_kg   : heaviest single working set
  - best_estimated_1rm   : best Epley 1RM across all working sets
  - best_set_volume      : highest weight × reps for a single working set

HTTP endpoints live in routers/stats.py; ranks, report, dashboard and
calendar reuse these functions.
"""
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from app.models import Exercise, Session, SessionExercise, Set
from app.schemas import PRHit, PRRecord, SessionSummaryStats


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


def session_summary(db: DBSession, session: Session, user_id: int) -> SessionSummaryStats:
    """
    Compute the finish-workout summary for a session:
      - duration (started_at → ended_at)
      - total volume of completed working sets
      - PRs hit during this session

    PR detection compares each exercise's best set IN this session against its
    best set across ALL OTHER sessions. If the session beats the prior best
    (or there's no prior record), it counts as a PR.
    """
    session_id = session.id

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
