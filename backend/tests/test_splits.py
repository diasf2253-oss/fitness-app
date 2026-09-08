"""
Splits — grouping routines under Push/Pull/Legs, Bro Split, etc.

The load-bearing rules: a split is just a grouping (deleting one must never
delete training days), splits are per-user, and a template builds real days
with real exercises.
"""
from app.auth import hash_password
from app.models import User

from tests.conftest import TestingSession


def test_split_crud(auth_client):
    created = auth_client.post("/api/splits", json={"name": "Upper / Lower"})
    assert created.status_code == 201, created.text
    split = created.json()
    assert split["name"] == "Upper / Lower" and split["routine_count"] == 0

    renamed = auth_client.put(f"/api/splits/{split['id']}", json={"name": "U/L"})
    assert renamed.status_code == 200 and renamed.json()["name"] == "U/L"

    assert [s["name"] for s in auth_client.get("/api/splits").json()] == ["U/L"]

    assert auth_client.delete(f"/api/splits/{split['id']}").status_code == 204
    assert auth_client.get("/api/splits").json() == []


def test_deleting_a_split_keeps_its_routines(auth_client):
    """A split is organisation, not ownership — the days (and the history logged
    against them) must survive."""
    split = auth_client.post("/api/splits", json={"name": "Temp"}).json()
    ex_id = auth_client.post("/api/exercises", json={"name": "Split Test Press"}).json()["id"]
    routine = auth_client.post("/api/routines", json={
        "name": "Day 1", "split_id": split["id"],
        "exercises": [{"exercise_id": ex_id, "position": 0}],
    }).json()
    assert routine["split_id"] == split["id"]

    auth_client.delete(f"/api/splits/{split['id']}")

    survivor = auth_client.get(f"/api/routines/{routine['id']}")
    assert survivor.status_code == 200
    assert survivor.json()["split_id"] is None, "detached, not deleted"


def test_routine_count_reflects_membership(auth_client):
    split = auth_client.post("/api/splits", json={"name": "Counted"}).json()
    for n in ("A", "B"):
        auth_client.post("/api/routines", json={"name": n, "split_id": split["id"]})
    [out] = [s for s in auth_client.get("/api/splits").json() if s["id"] == split["id"]]
    assert out["routine_count"] == 2


def test_template_builds_days_with_exercises(auth_client):
    """The seeded library is empty in tests, so unresolvable names are skipped —
    the split and its days must still be created."""
    from app.models import Exercise

    db = TestingSession()
    db.add(Exercise(user_id=None, name="Barbell Squat", primary_muscle_group="Quads"))
    db.add(Exercise(user_id=None, name="Deadlift", primary_muscle_group="Back"))
    db.commit(); db.close()

    r = auth_client.post("/api/splits", json={"template": "ppl"})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Push / Pull / Legs"      # template supplies the name
    assert r.json()["routine_count"] == 3                # Push / Pull / Legs

    routines = {x["name"]: x for x in auth_client.get("/api/routines").json()}
    assert {"Push", "Pull", "Legs"} <= set(routines)
    # Only the two names that exist in this library were attached.
    legs = routines["Legs"]["exercises"]
    assert [e["exercise"]["name"] for e in legs] == ["Barbell Squat"]
    assert legs[0]["target_sets"] == 4


def test_unknown_template_is_rejected(auth_client):
    assert auth_client.post("/api/splits", json={"template": "nope"}).status_code == 400


def test_splits_are_per_user(auth_client, client):
    auth_client.post("/api/splits", json={"name": "Mine"})

    db = TestingSession()
    db.add(User(email="other@example.com", password_hash=hash_password("password123"),
                name="Other", role="user", status="active"))
    db.commit(); db.close()
    client.post("/api/auth/login", json={"email": "other@example.com", "password": "password123"})

    assert client.get("/api/splits").json() == []
