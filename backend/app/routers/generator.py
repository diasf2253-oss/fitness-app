"""Workout generator — preview a program and apply it as routines.

GET  /api/generator/options  — split types + muscle groups for the form
POST /api/generator/preview  — build a program from inputs (not persisted)
POST /api/generator/apply    — persist it, replacing previously-generated
                               routines only (hand-made routines are untouched)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app import generator
from app.auth import require_auth
from app.db import get_db
from app.generator import SPLIT_LABELS, SPLITS
from app.models import Exercise, Routine, RoutineExercise
from app.muscles import MUSCLE_GROUPS, resolved_volume_targets
from app.routers.settings import get_or_create_settings
from app.schemas import GeneratorRequest, RoutineOut

router = APIRouter(prefix="/api/generator", tags=["generator"])


def _validate(body: GeneratorRequest) -> None:
    if body.split_type not in SPLITS:
        raise HTTPException(status_code=422, detail=f"split_type must be one of {list(SPLITS)}")
    bad = [m for m in body.priority_muscles if m not in MUSCLE_GROUPS]
    if bad:
        raise HTTPException(status_code=422, detail=f"unknown priority muscles: {bad}")


def _exercises_by_group(db: DBSession) -> dict[str, list]:
    out: dict[str, list] = {}
    rows = db.query(Exercise).filter(Exercise.primary_muscle_group.isnot(None)).all()
    for ex in rows:
        out.setdefault(ex.primary_muscle_group, []).append(ex)
    return out


def _build(db: DBSession, body: GeneratorRequest) -> generator.GenProgram:
    targets = resolved_volume_targets(get_or_create_settings(db).volume_targets)
    return generator.generate(
        priority=body.priority_muscles,
        days_per_week=body.days_per_week,
        split_type=body.split_type,
        targets=targets,
        exercises_by_group=_exercises_by_group(db),
    )


def _program_dict(prog: generator.GenProgram) -> dict:
    return {
        "split_type": prog.split_type,
        "split_label": prog.split_label,
        "days_per_week": prog.days_per_week,
        "arrangement": prog.arrangement,
        "weekly_sets": prog.weekly_sets,
        "targets": {m: {"low": lo, "high": hi} for m, (lo, hi) in prog.targets.items()},
        "notes": prog.notes,
        "routines": [
            {
                "name": r.name,
                "day_type": r.day_type,
                "exercises": [
                    {
                        "exercise_id": e.exercise_id, "name": e.name,
                        "muscle_group": e.muscle_group, "sets": e.sets,
                        "rep_low": e.rep_low, "rep_high": e.rep_high,
                        "is_compound": e.is_compound,
                    }
                    for e in r.exercises
                ],
            }
            for r in prog.routines
        ],
    }


@router.get("/options")
def options(_: None = Depends(require_auth)):
    """Split types and muscle groups to drive the generator form."""
    return {
        "muscle_groups": MUSCLE_GROUPS,
        "split_types": [{"value": k, "label": SPLIT_LABELS[k]} for k in SPLITS],
    }


@router.post("/preview")
def preview(
    body: GeneratorRequest,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    _validate(body)
    return _program_dict(_build(db, body))


@router.post("/apply")
def apply(
    body: GeneratorRequest,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    """Persist the generated program. Deterministic, so it saves exactly what
    the review screen showed. Replaces only routines tagged 'generated'."""
    _validate(body)
    prog = _build(db, body)

    old = db.query(Routine).filter(Routine.source == "generated").all()
    replaced = len(old)
    for r in old:
        db.delete(r)
    db.flush()

    created: list[Routine] = []
    for r in prog.routines:
        routine = Routine(name=r.name, source="generated")
        db.add(routine)
        db.flush()
        for pos, e in enumerate(r.exercises):
            db.add(RoutineExercise(
                routine_id=routine.id,
                exercise_id=e.exercise_id,
                position=pos,
                target_sets=e.sets,
                target_rep_low=e.rep_low,
                target_rep_high=e.rep_high,
                rest_seconds=180 if e.is_compound else 90,
            ))
        created.append(routine)

    db.commit()
    for routine in created:
        db.refresh(routine)

    return {
        "replaced": replaced,
        "notes": prog.notes,
        "routines": [RoutineOut.model_validate(r) for r in created],
    }
