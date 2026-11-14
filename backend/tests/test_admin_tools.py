"""
Admin account tools: the passwordless admin bootstrap (seed_admin / start.sh /
Docker boot) and the admin's "password reset link" button.
"""
import httpx
import pytest

from app import auth_bootstrap
from app.config import settings
from app.models import User
from tests.conftest import ADMIN_USER_EMAIL, TestingSession, _make_user


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("email", ["", "   ", "not-an-email", "You@Example.com"])
def test_bootstrap_refuses_without_a_real_admin_email(monkeypatch, email):
    monkeypatch.setattr(settings, "admin_email", email)
    db = TestingSession()
    try:
        with pytest.raises(RuntimeError, match="ADMIN_EMAIL"):
            auth_bootstrap.get_or_create_admin_user(db)
        assert db.query(User).count() == 0
    finally:
        db.close()


def test_bootstrap_creates_a_passwordless_admin(monkeypatch):
    monkeypatch.setattr(settings, "admin_email", " Owner@Example.com ")
    db = TestingSession()
    try:
        admin = auth_bootstrap.get_or_create_admin_user(db)
        assert admin.email == "owner@example.com"
        assert admin.role == "admin" and admin.status == "active"
        # Sign-in is Supabase's job: no local password, not linked until the
        # admin first signs in with that email.
        assert admin.password_hash is None
        assert admin.supabase_uid is None
    finally:
        db.close()


def test_bootstrap_keeps_an_existing_admin(monkeypatch):
    _make_user(ADMIN_USER_EMAIL, role="admin")
    monkeypatch.setattr(settings, "admin_email", "someone-else@example.com")
    db = TestingSession()
    try:
        assert auth_bootstrap.get_or_create_admin_user(db).email == ADMIN_USER_EMAIL
        assert db.query(User).count() == 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /api/admin/users/{id}/reset-link
# ---------------------------------------------------------------------------

def test_reset_link_comes_back_from_supabase(admin_client, fake_supabase, monkeypatch):
    monkeypatch.setattr(settings, "supabase_secret_key", "sb_secret_test")
    friend_id = _make_user("friend@example.com")
    fake_supabase.admin_response = httpx.Response(
        200, json={"action_link": "https://test-project.supabase.co/auth/v1/verify?token=abc&type=recovery"})

    r = admin_client.post(f"/api/admin/users/{friend_id}/reset-link")

    assert r.status_code == 200, r.text
    assert r.json() == {
        "email": "friend@example.com",
        "action_link": "https://test-project.supabase.co/auth/v1/verify?token=abc&type=recovery",
    }
    assert fake_supabase.admin_calls == [
        ("/admin/generate_link", {"type": "recovery", "email": "friend@example.com"})]
    # A new-style secret key travels only in the apikey header (it's no JWT).
    assert fake_supabase.admin_headers == {"apikey": "sb_secret_test"}


def test_legacy_service_role_key_is_also_sent_as_bearer(admin_client, fake_supabase, monkeypatch):
    monkeypatch.setattr(settings, "supabase_secret_key", "eyJhbGciOi.legacy.service-role")
    friend_id = _make_user("friend@example.com")
    fake_supabase.admin_response = httpx.Response(200, json={"action_link": "https://x.test/l"})
    assert admin_client.post(f"/api/admin/users/{friend_id}/reset-link").status_code == 200
    assert fake_supabase.admin_headers == {
        "apikey": "eyJhbGciOi.legacy.service-role",
        "Authorization": "Bearer eyJhbGciOi.legacy.service-role",
    }


def test_reset_link_needs_the_secret_key(admin_client, fake_supabase):
    friend_id = _make_user("friend@example.com")
    r = admin_client.post(f"/api/admin/users/{friend_id}/reset-link")
    assert r.status_code == 503
    assert "SUPABASE_SECRET_KEY" in r.json()["detail"]
    assert fake_supabase.admin_calls == []


def test_reset_link_for_someone_not_yet_on_the_new_login(admin_client, monkeypatch):
    monkeypatch.setattr(settings, "supabase_secret_key", "sb_secret_test")
    friend_id = _make_user("friend@example.com", linked=False)
    r = admin_client.post(f"/api/admin/users/{friend_id}/reset-link")
    assert r.status_code == 409
    assert "hasn't signed in with the new login" in r.json()["detail"]


def test_reset_link_is_admin_only(auth_client):
    r = auth_client.post(f"/api/admin/users/{auth_client.test_user_id}/reset-link")
    assert r.status_code == 403


def test_admin_list_shows_who_has_linked_their_login(admin_client):
    _make_user("old-timer@example.com", linked=False)
    users = {u["email"]: u for u in admin_client.get("/api/admin/users").json()}
    assert users[ADMIN_USER_EMAIL]["login_linked"] is True
    assert users["old-timer@example.com"]["login_linked"] is False
