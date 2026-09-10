"""
Idempotent CLI: creates the admin account (from ADMIN_EMAIL/ADMIN_PASSWORD)
and one active invite code, if either doesn't exist yet. Safe to run
repeatedly — running it again just reports what's already there. Run this
before app.seed on a fresh database (app.seed needs the admin account to
scope its sample routines/trackers to).

Run with:
    cd backend
    source .venv/bin/activate
    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... python -m app.seed_admin
"""
import sys
import os
import secrets

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.auth_bootstrap import get_or_create_admin_user
from app.db import SessionLocal
from app.models import InviteCode


def seed_admin():
    db = SessionLocal()
    try:
        admin = get_or_create_admin_user(db)
        print(f"Admin account: {admin.email} (id={admin.id}, status={admin.status})")

        code = db.query(InviteCode).filter(InviteCode.active.is_(True)).first()
        if code is None:
            code = InviteCode(code=secrets.token_urlsafe(9), label="first beta code")
            db.add(code)
            db.commit()
            print(f"Created invite code: {code.code}")
        else:
            print(f"Active invite code already exists: {code.code}")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        seed_admin()
    except RuntimeError as e:
        # Shown by start.sh and the Docker boot log — a message, not a traceback.
        sys.exit(f"Can't create the admin account: {e}")
