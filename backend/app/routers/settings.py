"""
App settings — single-row table, id=1 always.

GET  /api/settings    — read current settings
PUT  /api/settings    — update (partial: only send fields you want to change)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import AppSettings, User
from app.schemas import AppSettingsOut, AppSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_or_create_settings(db: DBSession, user_id: int) -> AppSettings:
    """Fetch this user's settings row, creating it with defaults if absent."""
    row = db.query(AppSettings).filter(AppSettings.user_id == user_id).first()
    if not row:
        row = AppSettings(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=AppSettingsOut)
def read_settings(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return get_or_create_settings(db, current_user.id)


@router.put("", response_model=AppSettingsOut)
def update_settings(
    body: AppSettingsUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    row = get_or_create_settings(db, current_user.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row
