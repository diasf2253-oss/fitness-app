"""
App settings — single-row table, id=1 always.

GET  /api/settings    — read current settings
PUT  /api/settings    — update (partial: only send fields you want to change)
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import AppSettings
from app.schemas import AppSettingsOut, AppSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_or_create_settings(db: DBSession) -> AppSettings:
    """Fetch the single settings row, creating it with defaults if absent."""
    row = db.get(AppSettings, 1)
    if not row:
        row = AppSettings(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=AppSettingsOut)
def read_settings(
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    return get_or_create_settings(db)


@router.put("", response_model=AppSettingsOut)
def update_settings(
    body: AppSettingsUpdate,
    db: DBSession = Depends(get_db),
    _: None = Depends(require_auth),
):
    row = get_or_create_settings(db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row
