"""Training streak — current + longest, recomputed from active days and
persisted onto the single StreakState row.

An "active day" is a real workout, a logged sport session (football/judo/
padel…), or a 10k-step day — workbook ruling T6a.

GET /api/streak — the current streak snapshot
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.core.auth import require_auth
from app.core.db import get_db
from app.models import User
from app.schemas import StreakOut
from app.services.training.streak import streak_snapshot

router = APIRouter(prefix="/api/streak", tags=["streak"])


@router.get("", response_model=StreakOut)
def get_streak(db: DBSession = Depends(get_db), current_user: User = Depends(require_auth)):
    return streak_snapshot(db, current_user.id)
