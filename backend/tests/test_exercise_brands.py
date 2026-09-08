"""
Per-user machine brands (settings.exercise_brands) + the exercise uuid they key on.

Brands live in the user's own settings, not on the Exercise row, because seeded
exercises are the SHARED library (user_id IS NULL) — a brand written there would
be visible to every other user in the friends beta. These tests pin both halves:
the uuid is exposed, and one user's brands never leak to another.
"""
from app.auth import hash_password
from app.models import Exercise, User

from tests.conftest import TestingSession


def test_exercise_out_exposes_uuid(auth_client):
    """Brands key on uuid (stable across devices), so the API must expose it."""
    auth_client.post("/api/exercises", json={"name": "Brand Test Machine", "equipment": "machine"})
    [ex] = [e for e in auth_client.get("/api/exercises").json() if e["name"] == "Brand Test Machine"]
    assert ex["uuid"] and isinstance(ex["uuid"], str)


def test_brands_round_trip_through_settings(auth_client):
    ex = auth_client.post(
        "/api/exercises", json={"name": "Chest Press Machine", "equipment": "machine"}
    ).json()

    r = auth_client.put("/api/settings", json={"exercise_brands": {ex["uuid"]: "Hammer Strength"}})
    assert r.status_code == 200, r.text
    assert auth_client.get("/api/settings").json()["exercise_brands"] == {ex["uuid"]: "Hammer Strength"}

    # Clearing one brand is just writing the map back without it.
    auth_client.put("/api/settings", json={"exercise_brands": {}})
    assert auth_client.get("/api/settings").json()["exercise_brands"] == {}


def test_brands_are_private_to_each_user(auth_client, client):
    """The whole reason brands aren't on the shared Exercise row.

    Uses a SEEDED exercise (user_id IS NULL — the shared library), not one
    created through the API: those are custom and already private to their
    owner, so they couldn't demonstrate the leak this design prevents.
    """
    db = TestingSession()
    shared = Exercise(user_id=None, name="Shared Cable Tower", equipment="cable",
                      primary_muscle_group="Back", is_custom=False)
    db.add(shared); db.commit(); db.refresh(shared)
    shared_uuid = shared.uuid
    db.close()

    ex = {"uuid": shared_uuid}
    auth_client.put("/api/settings", json={"exercise_brands": {ex["uuid"]: "Technogym"}})

    db = TestingSession()
    db.add(User(email="other@example.com", password_hash=hash_password("password123"),
                name="Other", role="user", status="active"))
    db.commit(); db.close()
    assert client.post("/api/auth/login",
                       json={"email": "other@example.com", "password": "password123"}).status_code == 200

    # The other user sees the same exercise, but none of the first user's brands.
    assert any(e["uuid"] == ex["uuid"] for e in client.get("/api/exercises").json())
    assert not (client.get("/api/settings").json().get("exercise_brands") or {})
