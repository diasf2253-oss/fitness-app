"""
Admin utility: change the admin account's login email and/or password.

Prompts for the new email (Enter keeps the current one) and for the new
password with typing HIDDEN (getpass), so the password is never echoed to the
screen or saved in shell history — it goes straight into a one-way argon2
hash in the database.

Run with:
    cd backend
    source .venv/bin/activate
    python -m app.set_admin_password

It edits whatever database DATABASE_URL points at (the local
fitness.sqlite3 by default).
"""
import getpass

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User


def main() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if admin is None:
            print("No admin account found — run `python -m app.seed_admin` first.")
            return

        print(f"Current admin account: {admin.email}")
        email = input("New admin email (Enter to keep current): ").strip().lower()
        new = getpass.getpass("New password: ")
        confirm = getpass.getpass("Confirm new password: ")

        if new != confirm:
            print("Passwords don't match — nothing changed.")
            return
        if len(new) < 8:
            print("Password must be at least 8 characters — nothing changed.")
            return

        if email:
            admin.email = email
        admin.password_hash = hash_password(new)
        db.commit()
        print(f"Admin is {admin.email}; password updated.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
