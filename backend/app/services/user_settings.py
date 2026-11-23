"""Per-user app settings (the AppSettings row) — shared lookup used by many
routers and services. HTTP endpoints live in routers/settings.py."""
from sqlalchemy.orm import Session as DBSession

from app.models import AppSettings


def get_or_create_settings(db: DBSession, user_id: int) -> AppSettings:
    """Fetch this user's settings row, creating it with defaults if absent."""
    row = db.query(AppSettings).filter(AppSettings.user_id == user_id).first()
    if not row:
        row = AppSettings(user_id=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row
