"""
Splits — a named group of routines (Push/Pull/Legs, Bro Split, …).

GET    /api/splits        — list this user's splits, with how many days each holds
POST   /api/splits        — create one, optionally built from a template
PUT    /api/splits/{id}   — rename / reorder
DELETE /api/splits/{id}   — delete the split ONLY; its routines survive, ungrouped

Routines carry `split_id`; NULL means ungrouped, which the UI shows as its own
bucket. Deleting a split must never take training history with it, so the
routines are detached explicitly rather than relying on cascade behaviour.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Routine, RoutineExercise, Split, User
from app.schemas import SplitCreate, SplitOut, SplitUpdate
from app.split_templates import SPLIT_TEMPLATES

router = APIRouter(prefix="/api/splits", tags=["splits"])


def _present(db: DBSession, split: Split) -> SplitOut:
    count = (
        db.query(func.count(Routine.id)).filter(Routine.split_id == split.id).scalar() or 0
    )
    return SplitOut(
        id=split.id, name=split.name, position=split.position,
        created_at=split.created_at, routine_count=count,
    )


def _get_owned(db: DBSession, split_id: int, user_id: int) -> Split:
    split = db.get(Split, split_id)
    if not split or split.user_id != user_id:
        raise HTTPException(status_code=404, detail="Split not found")
    return split


def _build_from_template(db: DBSession, user_id: int, split: Split, key: str) -> None:
    """Create the template's days and their exercises under `split`.

    Exercises are referenced by name and resolved against what this user can
    see. An unresolved name is skipped, not fatal — a trimmed library should
    still yield a usable split.
    """
    tpl = SPLIT_TEMPLATES.get(key)
    if tpl is None:
        raise HTTPException(status_code=400, detail=f"Unknown split template '{key}'")

    for day in tpl["days"]:
        routine = Routine(user_id=user_id, name=day["name"], split_id=split.id)
        db.add(routine)
        db.flush()
        position = 0
        for exercise_name, sets in day["exercises"]:
            ex = (
                db.query(Exercise)
                .filter(
                    Exercise.name == exercise_name,
                    or_(Exercise.user_id.is_(None), Exercise.user_id == user_id),
                )
                .first()
            )
            if ex is None:
                continue
            db.add(RoutineExercise(
                user_id=user_id, routine_id=routine.id, exercise_id=ex.id,
                position=position, target_sets=sets,
            ))
            position += 1


@router.get("", response_model=list[SplitOut])
def list_splits(
    db: DBSession = Depends(get_db), current_user: User = Depends(require_auth)
):
    splits = (
        db.query(Split)
        .filter(Split.user_id == current_user.id)
        .order_by(Split.position, Split.name)
        .all()
    )
    return [_present(db, s) for s in splits]


@router.post("", response_model=SplitOut, status_code=201)
def create_split(
    body: SplitCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    if body.template and body.template not in SPLIT_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown split template '{body.template}'")

    name = (body.name or "").strip()
    if not name and body.template:
        name = SPLIT_TEMPLATES[body.template]["name"]
    if not name:
        raise HTTPException(status_code=422, detail="A split needs a name")

    last = (
        db.query(func.max(Split.position)).filter(Split.user_id == current_user.id).scalar()
    )
    split = Split(user_id=current_user.id, name=name, position=(last or 0) + 1)
    db.add(split)
    db.flush()
    if body.template:
        _build_from_template(db, current_user.id, split, body.template)
    db.commit()
    db.refresh(split)
    return _present(db, split)


@router.put("/{split_id}", response_model=SplitOut)
def update_split(
    split_id: int,
    body: SplitUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    split = _get_owned(db, split_id, current_user.id)
    if body.name is not None:
        split.name = body.name.strip()
    if body.position is not None:
        split.position = body.position
    db.commit()
    db.refresh(split)
    return _present(db, split)


@router.delete("/{split_id}", status_code=204)
def delete_split(
    split_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    split = _get_owned(db, split_id, current_user.id)
    # Detach first: the routines (and every session logged against them) stay.
    db.query(Routine).filter(
        Routine.split_id == split.id, Routine.user_id == current_user.id
    ).update({Routine.split_id: None}, synchronize_session=False)
    db.delete(split)
    db.commit()


@router.get("/templates", response_model=list[dict])
def list_templates():
    """The ready-made splits offered when creating one."""
    return [
        {"key": k, "name": t["name"], "days": [d["name"] for d in t["days"]]}
        for k, t in SPLIT_TEMPLATES.items()
    ]
