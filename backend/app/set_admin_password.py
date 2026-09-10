"""
Admin utility: change the admin account's login email and/or password.

Prompts for the new email (Enter keeps the current one) and for the new
password with typing HIDDEN (getpass), so the password is never echoed to the
screen or saved in shell history — it goes straight into a one-way argon2
hash in the database. Every existing admin session is logged out, so anyone
still holding the old password's session is locked out too.

Run with:
    cd backend
    source .venv/bin/activate
    python -m app.set_admin_password

It edits whatever database DATABASE_URL points at (the local
fitness.sqlite3 by default).
"""
import getpass

from sqlalchemy.orm import Session as DBSession

from app.auth import hash_password
from app.auth_bootstrap import MIN_ADMIN_PASSWORD
from app.db import SessionLocal
from app.models import AuthSession, User


def update_admin(db: DBSession, email: str, password: str) -> str | None:
    """Set the admin's email (blank = keep) and password. Returns an error
    message instead of raising, so the CLI can print it; None on success."""
    admin = db.query(User).filter(User.role == "admin").first()
    if admin is None:
        return "No admin account found — run `python -m app.seed_admin` first."
    if len(password) < MIN_ADMIN_PASSWORD:
        return f"Password must be at least {MIN_ADMIN_PASSWORD} characters — nothing changed."

    email = email.strip().lower()
    if email and email != admin.email:
        taken = db.query(User).filter(User.email == email, User.id != admin.id).first()
        if taken:
            return f"{email} already belongs to another account — nothing changed."
        admin.email = email

    admin.password_hash = hash_password(password)
    admin.must_change_password = False
    # Same rule as the in-app change/reset flows: a new password must lock
    # out anyone still holding a session from the old one.
    db.query(AuthSession).filter(AuthSession.user_id == admin.id).delete(
        synchronize_session=False
    )
    db.commit()
    return None


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            print("No admin account found — run `python -m app.seed_admin` first.")
            return

        print(f"Current admin account: {admin.email}")
        email = input("New admin email (Enter to keep current): ")
        new = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm new password: ")
        if new != confirm:
            print("Passwords don't match — nothing changed.")
            return

        error = update_admin(db, email, new)
        if error:
            print(error)
            return
        print(f"Admin is {admin.email}; password updated and every existing "
              "session logged out.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
