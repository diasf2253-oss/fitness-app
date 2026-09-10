"""
Admin account tools: never create an admin with the template password, and
make an admin password change actually lock out whoever held the old one.
"""
import pytest

from app import auth_bootstrap
from app.auth import verify_password
from app.config import settings
from app.models import User
from app.set_admin_password import update_admin
from tests.conftest import ADMIN_USER_EMAIL, TestingSession, _make_user

NEW_PASSWORD = "brand-new-pass-123"


# ---------------------------------------------------------------------------
# Bootstrap (seed_admin / start.sh / Docker boot)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("password", ["changeme", " CHANGEME ", "short"])
def test_bootstrap_refuses_template_or_short_password(monkeypatch, password):
    monkeypatch.setattr(settings, "admin_email", "owner@example.com")
    monkeypatch.setattr(settings, "admin_password", password)
    db = TestingSession()
    try:
        with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
            auth_bootstrap.get_or_create_admin_user(db)
        assert db.query(User).count() == 0
    finally:
        db.close()


def test_bootstrap_creates_admin_with_real_password(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", "Owner@Example.com")
    monkeypatch.setattr(settings, "admin_password", "a-real-password")
    db = TestingSession()
    try:
        admin = auth_bootstrap.get_or_create_admin_user(db)
        assert admin.email == "owner@example.com"
        assert admin.role == "admin"
    finally:
        db.close()


def test_bootstrap_keeps_existing_admin_even_with_template_env(monkeypatch):
    """Installs whose .env still says changeme must keep booting."""
    _make_user(ADMIN_USER_EMAIL, "testpassword123", role="admin")
    monkeypatch.setattr(settings, "admin_password", "changeme")
    db = TestingSession()
    try:
        assert auth_bootstrap.get_or_create_admin_user(db).email == ADMIN_USER_EMAIL
    finally:
        db.close()


# ---------------------------------------------------------------------------
# python -m app.set_admin_password
# ---------------------------------------------------------------------------

def _update(email, password):
    db = TestingSession()
    try:
        return update_admin(db, email, password)
    finally:
        db.close()


def _admin():
    db = TestingSession()
    try:
        return db.query(User).filter_by(role="admin").one()
    finally:
        db.close()


def test_password_change_logs_out_every_admin_session(admin_client):
    assert admin_client.get("/api/auth/me").status_code == 200

    assert _update("", NEW_PASSWORD) is None

    assert admin_client.get("/api/auth/me").status_code == 401
    r = admin_client.post("/api/auth/login", json={
        "email": ADMIN_USER_EMAIL, "password": NEW_PASSWORD, "remember": True,
    })
    assert r.status_code == 200, r.text


def test_password_change_clears_forced_change():
    uid = _make_user(ADMIN_USER_EMAIL, "testpassword123", role="admin")
    db = TestingSession()
    db.get(User, uid).must_change_password = True
    db.commit()
    db.close()

    assert _update("", NEW_PASSWORD) is None
    assert _admin().must_change_password is False


def test_email_change_is_normalised():
    _make_user(ADMIN_USER_EMAIL, "testpassword123", role="admin")
    assert _update("  New@Example.com ", NEW_PASSWORD) is None
    assert _admin().email == "new@example.com"


def test_email_taken_by_another_account_is_refused():
    _make_user(ADMIN_USER_EMAIL, "testpassword123", role="admin")
    _make_user("friend@example.com", "testpassword123")

    error = _update("Friend@Example.com", NEW_PASSWORD)

    assert error and "already belongs" in error
    admin = _admin()
    assert admin.email == ADMIN_USER_EMAIL
    assert verify_password("testpassword123", admin.password_hash)   # untouched


def test_short_password_is_refused():
    _make_user(ADMIN_USER_EMAIL, "testpassword123", role="admin")
    assert "at least" in _update("", "short")
    assert verify_password("testpassword123", _admin().password_hash)
