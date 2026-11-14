"""Settings > Account/Profile: height, display name, and password change."""
from app.auth import verify_password
from app.models import User
from tests.conftest import TestingSession


def test_height_round_trips_and_validates(auth_client):
    assert auth_client.get("/api/settings").json()["height_cm"] is None
    r = auth_client.put("/api/settings", json={"height_cm": 181.5})
    assert r.status_code == 200 and r.json()["height_cm"] == 181.5
    assert auth_client.get("/api/settings").json()["height_cm"] == 181.5
    # Out-of-range heights are rejected, not stored
    assert auth_client.put("/api/settings", json={"height_cm": 20}).status_code == 422


def test_rename_trims_and_rejects_blank(auth_client):
    r = auth_client.patch("/api/auth/me", json={"name": "  Felipe  "})
    assert r.status_code == 200 and r.json()["name"] == "Felipe"
    assert auth_client.get("/api/auth/me").json()["name"] == "Felipe"
    assert auth_client.patch("/api/auth/me", json={"name": "   "}).status_code == 400


def test_change_password_requires_the_current_one(auth_client):
    r = auth_client.post("/api/auth/change-password", json={"new_password": "another-pass-123"})
    assert r.status_code == 400
    r = auth_client.post("/api/auth/change-password",
                         json={"current_password": "wrong", "new_password": "another-pass-123"})
    assert r.status_code == 400
    db = TestingSession()
    try:
        u = db.query(User).first()
        assert not verify_password("another-pass-123", u.password_hash)
    finally:
        db.close()


def test_change_password_succeeds_with_the_right_current_one(auth_client):
    from tests.conftest import TEST_USER_PASSWORD
    r = auth_client.post("/api/auth/change-password", json={
        "current_password": TEST_USER_PASSWORD, "new_password": "another-pass-123"})
    assert r.status_code == 200
    db = TestingSession()
    try:
        assert verify_password("another-pass-123", db.query(User).first().password_hash)
    finally:
        db.close()
