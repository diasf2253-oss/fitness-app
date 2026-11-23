"""Day-plan items (the hidden Plan feature, kept for the Coach). HTTP
endpoints live in routers/plan.py."""
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from app.models import PlanItem
from app.schemas import PLAN_CATEGORIES, PlanItemCreate


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
