"""
Shared "create the admin account" logic, used by both the one-off migration
backfill (backfill_owner.py — attaches all pre-multi-user data to this
account) and the idempotent `python -m app.seed_admin` CLI.
"""
from sqlalchemy.orm import Session as DBSession

from app.auth import hash_password
from app.config import settings
from app.models import User

# The placeholder from backend/.env.example. An admin created with it would
# carry a publicly documented password — and start.sh serves on 0.0.0.0.
_TEMPLATE_PASSWORDS = {"changeme"}
MIN_ADMIN_PASSWORD = 8   # same floor as signup / change-password (schemas.py)


def get_or_create_admin_user(db: DBSession) -> User:
    """
    Returns the admin user, creating it from ADMIN_EMAIL/ADMIN_PASSWORD if
    one doesn't exist yet. Raises rather than silently inventing credentials
    when those env vars aren't set, and refuses to create the admin with the
    template or a too-short password. An existing admin is returned as-is, so
    installs whose .env still holds the placeholder keep booting.
    """
    existing = db.query(User).filter(User.role == "admin").first()
    if existing:
        return existing

    if not settings.admin_email or not settings.admin_password:
        raise RuntimeError(
            "No admin user exists yet and ADMIN_EMAIL/ADMIN_PASSWORD are not "
            "set — set them in the environment before running this."
        )
    if (settings.admin_password.strip().lower() in _TEMPLATE_PASSWORDS
            or len(settings.admin_password) < MIN_ADMIN_PASSWORD):
        raise RuntimeError(
            "ADMIN_PASSWORD is still the template value or shorter than "
            f"{MIN_ADMIN_PASSWORD} characters — set a real password in "
            "backend/.env (or the environment) before creating the admin."
        )

    admin = User(
        email=settings.admin_email.strip().lower(),
        password_hash=hash_password(settings.admin_password),
        name="Admin",
        role="admin",
        status="active",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
