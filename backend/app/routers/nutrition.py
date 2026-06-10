"""
Nutrition log endpoints (manual entry + read).
The Apple Health ingest (Phase 3) writes to the same table with
source='apple_health' — YAZIO's data reaches us through Apple Health.

GET  /api/nutrition          — last N days
POST /api/nutrition          — upsert one day's macros
"""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import NutritionDay
from app.schemas import NutritionDayCreate, NutritionDayOut

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


def upsert_nutrition(db: DBSession, body: NutritionDayCreate) -> NutritionDay:
    """Insert or overwrite a day's nutrition data (idempotent)."""
    row = db.query(NutritionDay).filter(NutritionDay.date == body.date).first()
    if row:
        row.calories = body.calories
        row.protein_g = body.protein_g
        row.carbs_g = body.carbs_g
        row.fat_g = body.fat_g
        row.source = body.source
    else:
        row = NutritionDay(**body.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[NutritionDayOut])
def get_nutrition(
    days: int = Query(30, ge=1, le=365),
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    since = date.today() - timedelta(days=days)
    return (
        db.query(NutritionDay)
        .filter(NutritionDay.date >= since)
        .order_by(NutritionDay.date)
        .all()
    )


@router.post("", response_model=NutritionDayOut, status_code=201)
def log_nutrition(
    body: NutritionDayCreate,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    return upsert_nutrition(db, body)
