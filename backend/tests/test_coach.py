"""
Phase 8 tests — plan items + AI Coach.

The LLM calls themselves are never exercised here (no API key in CI). We test:
  - plan-item CRUD, toggle, ordering, day + calendar integration
  - coach status reflects the (absent) key
  - chat / planners return 503 when no key is configured
  - accept/day writes plan items (source='coach')
  - accept/workout builds a routine, creating missing exercises
The accept endpoints take the *approved proposal* as their body, so they're
fully testable without calling Claude.
"""
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_TOKEN"] = "testtoken"
os.environ["ANTHROPIC_API_KEY"] = ""  # Coach disabled for tests

from app.db import Base, get_db
from app.main import app
from app.models import PlanItem, Routine

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
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


# ---------------------------------------------------------------------------
# Plan items
# ---------------------------------------------------------------------------

class TestPlanCrud:
    def test_create_list_order(self):
        d = "2026-06-15"
        client.post(f"/api/plan/{d}/items",
                    json={"title": "Deep work", "start_time": "09:00", "category": "study"}, headers=AUTH)
        client.post(f"/api/plan/{d}/items",
                    json={"title": "Lunch", "start_time": "13:00", "category": "meal"}, headers=AUTH)
        items = client.get(f"/api/plan/{d}", headers=AUTH).json()
        assert [i["title"] for i in items] == ["Deep work", "Lunch"]
        assert items[0]["position"] == 0 and items[1]["position"] == 1
        assert items[0]["source"] == "manual"

    def test_toggle_done(self):
        d = "2026-06-15"
        item = client.post(f"/api/plan/{d}/items", json={"title": "Squats", "category": "workout"}, headers=AUTH).json()
        r = client.patch(f"/api/plan/items/{item['id']}", json={"is_done": True}, headers=AUTH)
        assert r.json()["is_done"] is True

    def test_invalid_category_falls_back_to_task(self):
        d = "2026-06-15"
        item = client.post(f"/api/plan/{d}/items", json={"title": "X", "category": "banana"}, headers=AUTH).json()
        assert item["category"] == "task"

    def test_delete(self):
        d = "2026-06-15"
        item = client.post(f"/api/plan/{d}/items", json={"title": "X"}, headers=AUTH).json()
        assert client.delete(f"/api/plan/items/{item['id']}", headers=AUTH).status_code == 204
        assert client.get(f"/api/plan/{d}", headers=AUTH).json() == []

    def test_requires_auth(self):
        assert client.get("/api/plan/2026-06-15").status_code == 403

    def test_day_and_calendar_integration(self):
        d = "2026-06-15"
        client.post(f"/api/plan/{d}/items", json={"title": "Read", "category": "study"}, headers=AUTH)
        day = client.get(f"/api/day/{d}", headers=AUTH).json()
        assert len(day["plan"]) == 1
        assert day["plan"][0]["title"] == "Read"
        cal = client.get("/api/calendar/2026/06", headers=AUTH).json()["days"]
        assert {c["date"]: c for c in cal}[d]["plan_items"] == 1


# ---------------------------------------------------------------------------
# Coach guard + accept
# ---------------------------------------------------------------------------

class TestCoachGuard:
    def test_status_disabled_without_key(self):
        r = client.get("/api/coach/status", headers=AUTH).json()
        assert r["enabled"] is False
        assert r["model"]  # model id still reported

    def test_chat_503_without_key(self):
        r = client.post("/api/coach/chat",
                        json={"messages": [{"role": "user", "content": "hi"}]}, headers=AUTH)
        assert r.status_code == 503

    def test_planners_503_without_key(self):
        for path in ("workout", "day", "study"):
            r = client.post(f"/api/coach/plan/{path}", json={}, headers=AUTH)
            assert r.status_code == 503, path


class TestCoachAccept:
    def test_accept_day_writes_plan_items(self):
        body = {
            "date": "2026-06-15",
            "items": [
                {"start_time": "09:00", "title": "Study calculus", "category": "study", "notes": "ch.4"},
                {"start_time": "12:30", "title": "Lunch", "category": "meal"},
            ],
        }
        r = client.post("/api/coach/accept/day", json=body, headers=AUTH)
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2
        assert all(i["source"] == "coach" for i in items)

        db = TestingSession()
        assert db.query(PlanItem).count() == 2
        db.close()

    def test_accept_workout_builds_routine_and_creates_exercises(self):
        # One existing exercise, one the coach invented
        client.post("/api/exercises",
                    json={"name": "Barbell Squat", "primary_muscle": "quads", "is_custom": True}, headers=AUTH)
        body = {
            "title": "Coached Lower",
            "exercises": [
                {"name": "Barbell Squat", "sets": 4, "rep_low": 5, "rep_high": 8, "rest_seconds": 180},
                {"name": "Nordic Curl", "sets": 3, "rep_low": 6, "rep_high": 10},
            ],
        }
        r = client.post("/api/coach/accept/workout", json=body, headers=AUTH)
        assert r.status_code == 200
        out = r.json()
        assert out["exercises"] == 2

        db = TestingSession()
        routine = db.query(Routine).filter(Routine.id == out["routine_id"]).first()
        assert routine.name == "Coached Lower"
        assert len(routine.exercises) == 2
        # Existing exercise reused (case-insensitive), new one created once
        names = {re.exercise.name for re in routine.exercises}
        assert names == {"Barbell Squat", "Nordic Curl"}
        db.close()

    def test_accept_workout_rejects_empty(self):
        r = client.post("/api/coach/accept/workout", json={"title": "X", "exercises": []}, headers=AUTH)
        assert r.status_code == 422
