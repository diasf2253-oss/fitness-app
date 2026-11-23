"""
App settings — single-row table, id=1 always.

GET  /api/settings    — read current settings
PUT  /api/settings    — update (partial: only send fields you want to change)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.core.auth import require_auth
from app.core.db import get_db
from app.models import User
from app.schemas import AppSettingsOut, AppSettingsUpdate
from app.services.user_settings import get_or_create_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


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
