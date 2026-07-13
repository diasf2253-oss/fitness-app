"""Next-session notes: surface once at the next session of the routine, then
auto-archive (still in history). Plus persistent per-exercise notes carry into
the session via the exercise."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_TOKEN"] = "testtoken"

from app.db import Base, get_db
from app.main import app

engine = create_engine(
    TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)
AUTH = {"Authorization": "Bearer testtoken"}


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


def make_routine(note_cue=None, label="A"):
    ex = client.post(
        "/api/exercises",
        json={"name": f"Squat {label}", "primary_muscle_group": "Quads", "notes": note_cue},
        headers=AUTH,
    ).json()
    routine = client.post(
        "/api/routines",
        json={"name": f"Lower {label}", "exercises": [
            {"exercise_id": ex["id"], "position": 0, "target_sets": 2,
             "target_rep_low": 5, "target_rep_high": 8, "rest_seconds": 120},
        ]},
        headers=AUTH,
    ).json()
    return ex, routine


def test_next_session_note_surfaces_once_then_archives():
    _, routine = make_routine()
    rid = routine["id"]

    note = client.post(f"/api/routines/{rid}/notes", json={"text": "add a set to squats"}, headers=AUTH).json()
    assert note["archived_at"] is None        # pending

    # First session of this routine surfaces the note
    s1 = client.post("/api/sessions", json={"name": "Lower A", "routine_id": rid}, headers=AUTH).json()
    assert [n["text"] for n in s1["next_session_notes"]] == ["add a set to squats"]
    # ...and it's now consumed/archived
    fetched = client.get(f"/api/routines/{rid}/notes?include_archived=false", headers=AUTH).json()
    assert fetched == []
    archived = client.get(f"/api/routines/{rid}/notes", headers=AUTH).json()
    assert archived[0]["surfaced_in_session_id"] == s1["id"] and archived[0]["archived_at"]

    # A later session of the same routine does NOT resurface it
    s2 = client.post("/api/sessions", json={"name": "Lower A", "routine_id": rid}, headers=AUTH).json()
    assert s2["next_session_notes"] == []

    # It's still visible on the session that consumed it (history)
    assert [n["text"] for n in client.get(f"/api/sessions/{s1['id']}", headers=AUTH).json()["next_session_notes"]] == ["add a set to squats"]


def test_note_only_surfaces_for_its_own_routine():
    _, r1 = make_routine(label="A")
    _, r2 = make_routine(label="B")
    client.post(f"/api/routines/{r1['id']}/notes", json={"text": "for r1"}, headers=AUTH)
    s = client.post("/api/sessions", json={"name": "other", "routine_id": r2["id"]}, headers=AUTH).json()
    assert s["next_session_notes"] == []      # belongs to r1, not r2


def test_persistent_exercise_note_shows_in_session():
    ex, routine = make_routine(note_cue="Brace hard, knees out")
    s = client.post("/api/sessions", json={"name": "Lower A", "routine_id": routine["id"]}, headers=AUTH).json()
    assert s["exercises"][0]["exercise"]["notes"] == "Brace hard, knees out"
    # editable via the exercise endpoint
    client.put(f"/api/exercises/{ex['id']}", json={"notes": "New cue"}, headers=AUTH)
    assert client.get(f"/api/exercises/{ex['id']}", headers=AUTH).json()["notes"] == "New cue"


def test_edit_and_delete_note():
    _, routine = make_routine()
    rid = routine["id"]
    note = client.post(f"/api/routines/{rid}/notes", json={"text": "draft"}, headers=AUTH).json()
    edited = client.patch(f"/api/routine-notes/{note['id']}", json={"text": "final"}, headers=AUTH).json()
    assert edited["text"] == "final"
    assert client.delete(f"/api/routine-notes/{note['id']}", headers=AUTH).status_code == 204
    assert client.get(f"/api/routines/{rid}/notes", headers=AUTH).json() == []
