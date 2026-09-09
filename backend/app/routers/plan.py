"""
Plan items (Phase 8) — the trackable day/study/workout plan.

GET    /api/plan/{day}            — items for a date (ordered)
POST   /api/plan/{day}/items      — add one (manual by default)
PATCH  /api/plan/items/{id}       — toggle done / edit
DELETE /api/plan/items/{id}       — remove one

The AI Coach writes here too (source='coach') via its accept endpoint, which
reuses add_plan_item below so ordering and validation stay in one place.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import PlanItem, User
from app.schemas import PLAN_CATEGORIES, PlanItemCreate, PlanItemOut, PlanItemUpdate

router = APIRouter(prefix="/api/plan", tags=["plan"])


def add_plan_item(db: DBSession, day: date, body: PlanItemCreate, user_id: int) -> PlanItem:
    """Append a plan item to a day. Shared by the manual route and the Coach."""
    if not body.title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    category = body.category if body.category in PLAN_CATEGORIES else "task"

    max_pos = (
        db.query(PlanItem.position)
        .filter(PlanItem.user_id == user_id, PlanItem.date == day)
        .order_by(PlanItem.position.desc())
        .first()
    )
    item = PlanItem(
        user_id=user_id,
        date=day,
        title=body.title.strip(),
        start_time=body.start_time or None,
        end_time=body.end_time or None,
        category=category,
        notes=(body.notes.strip() if body.notes else None),
        position=(max_pos[0] + 1) if max_pos else 0,
        source=body.source,
    )
    db.add(item)
    return item


@router.get("/{day}", response_model=list[PlanItemOut])
def list_plan(
    day: date,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return (
        db.query(PlanItem)
        .filter(PlanItem.user_id == current_user.id, PlanItem.date == day)
        .order_by(PlanItem.position, PlanItem.start_time, PlanItem.id)
        .all()
    )


@router.post("/{day}/items", response_model=PlanItemOut, status_code=201)
def create_plan_item(
    day: date,
    body: PlanItemCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    item = add_plan_item(db, day, body, current_user.id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=PlanItemOut)
def update_plan_item(
    item_id: int,
    body: PlanItemUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    item = db.get(PlanItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Plan item not found")
    data = body.model_dump(exclude_unset=True)
    if "category" in data and data["category"] not in PLAN_CATEGORIES:
        data.pop("category")
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
def delete_plan_item(
    item_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    item = db.get(PlanItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Plan item not found")
    db.delete(item)
    db.commit()
