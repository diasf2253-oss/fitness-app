"""
Shared "create the admin account" logic, used by both the one-off migration
backfill (backfill_owner.py — attaches all pre-multi-user data to this
account) and the idempotent `python -m app.cli.seed_admin` CLI.

There's no admin password: sign-in runs through Supabase Auth. The admin
account is created here from ADMIN_EMAIL alone, and the first time someone
signs in through Supabase with that (verified) email, app/core/auth.py links the
two — that's the moment the admin can actually log in.
"""
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.models import User

# The placeholder from backend/.env.example — nobody can sign in as it.
_TEMPLATE_EMAILS = {"you@example.com"}


def get_or_create_admin_user(db: DBSession) -> User:
    """
    Returns the admin user, creating it from ADMIN_EMAIL if one doesn't
    exist yet. Raises rather than inventing an address when ADMIN_EMAIL
    isn't set (or is still the template's). An existing admin is returned
    as-is.
    """
    existing = db.query(User).filter(User.role == "admin").first()
    if existing:
        return existing

    email = settings.admin_email.strip().lower()
    if not email or "@" not in email or email in _TEMPLATE_EMAILS:
        raise RuntimeError(
            "No admin user exists yet and ADMIN_EMAIL is not set to your email "
            "address (it's empty or still the template's you@example.com) — "
            "set it in the environment (or backend/.env) before running this."
        )

    admin = User(email=email, name="Admin", role="admin", status="active")
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin
