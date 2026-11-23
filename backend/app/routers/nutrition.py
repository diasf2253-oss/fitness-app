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

from app.core.auth import require_auth
from app.core.db import get_db
from app.models import NutritionDay, User
from app.schemas import NutritionDayCreate, NutritionDayOut
from app.services.health.store import upsert_nutrition

router = APIRouter(prefix="/api/nutrition", tags=["nutrition"])


@router.get("", response_model=list[NutritionDayOut])
def get_nutrition(
    days: int = Query(30, ge=1, le=365),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    since = date.today() - timedelta(days=days)
    return (
        db.query(NutritionDay)
        .filter(NutritionDay.user_id == current_user.id, NutritionDay.date >= since)
        .order_by(NutritionDay.date)
        .all()
    )


@router.post("", response_model=NutritionDayOut, status_code=201)
def log_nutrition(
    body: NutritionDayCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return upsert_nutrition(db, body, current_user.id)
