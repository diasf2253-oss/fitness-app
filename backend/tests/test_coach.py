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

The Coach is disabled in tests via ANTHROPIC_API_KEY="" (set in conftest.py
before the app imports), so chat/planner endpoints 503.
"""
from app.models import PlanItem, Routine

from tests.conftest import TestingSession


# ---------------------------------------------------------------------------
# Plan items
# ---------------------------------------------------------------------------

class TestPlanCrud:
    def test_create_list_order(self, auth_client):
        d = "2026-06-15"
        auth_client.post(f"/api/plan/{d}/items",
                         json={"title": "Deep work", "start_time": "09:00", "category": "study"})
        auth_client.post(f"/api/plan/{d}/items",
                         json={"title": "Lunch", "start_time": "13:00", "category": "meal"})
        items = auth_client.get(f"/api/plan/{d}").json()
        assert [i["title"] for i in items] == ["Deep work", "Lunch"]
        assert items[0]["position"] == 0 and items[1]["position"] == 1
        assert items[0]["source"] == "manual"

    def test_toggle_done(self, auth_client):
        d = "2026-06-15"
        item = auth_client.post(f"/api/plan/{d}/items", json={"title": "Squats", "category": "workout"}).json()
        r = auth_client.patch(f"/api/plan/items/{item['id']}", json={"is_done": True})
        assert r.json()["is_done"] is True

    def test_invalid_category_falls_back_to_task(self, auth_client):
        d = "2026-06-15"
        item = auth_client.post(f"/api/plan/{d}/items", json={"title": "X", "category": "banana"}).json()
        assert item["category"] == "task"

    def test_delete(self, auth_client):
        d = "2026-06-15"
        item = auth_client.post(f"/api/plan/{d}/items", json={"title": "X"}).json()
        assert auth_client.delete(f"/api/plan/items/{item['id']}").status_code == 204
        assert auth_client.get(f"/api/plan/{d}").json() == []

    def test_requires_auth(self, client):
        assert client.get("/api/plan/2026-06-15").status_code == 401

    def test_day_and_calendar_integration(self, auth_client):
        d = "2026-06-15"
        auth_client.post(f"/api/plan/{d}/items", json={"title": "Read", "category": "study"})
        day = auth_client.get(f"/api/day/{d}").json()
        assert len(day["plan"]) == 1
        assert day["plan"][0]["title"] == "Read"
        cal = auth_client.get("/api/calendar/2026/06").json()["days"]
        assert {c["date"]: c for c in cal}[d]["plan_items"] == 1


# ---------------------------------------------------------------------------
# Coach guard + accept
# ---------------------------------------------------------------------------

class TestCoachGuard:
    def test_status_disabled_without_key(self, auth_client):
        r = auth_client.get("/api/coach/status").json()
        assert r["enabled"] is False
        assert r["model"]  # model id still reported

    def test_chat_503_without_key(self, auth_client):
        r = auth_client.post("/api/coach/chat",
                             json={"messages": [{"role": "user", "content": "hi"}]})
        assert r.status_code == 503

    def test_planners_503_without_key(self, auth_client):
        for path in ("workout", "day", "study"):
            r = auth_client.post(f"/api/coach/plan/{path}", json={})
            assert r.status_code == 503, path


class TestCoachAccept:
    def test_accept_day_writes_plan_items(self, auth_client):
        body = {
            "date": "2026-06-15",
            "items": [
                {"start_time": "09:00", "title": "Study calculus", "category": "study", "notes": "ch.4"},
                {"start_time": "12:30", "title": "Lunch", "category": "meal"},
            ],
        }
        r = auth_client.post("/api/coach/accept/day", json=body)
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 2
        assert all(i["source"] == "coach" for i in items)

        db = TestingSession()
        assert db.query(PlanItem).count() == 2
        db.close()

    def test_accept_workout_builds_routine_and_creates_exercises(self, auth_client):
        # One existing exercise, one the coach invented
        auth_client.post("/api/exercises",
                         json={"name": "Barbell Squat", "primary_muscle": "quads", "is_custom": True})
        body = {
            "title": "Coached Lower",
            "exercises": [
                {"name": "Barbell Squat", "sets": 4, "rep_low": 5, "rep_high": 8, "rest_seconds": 180},
                {"name": "Nordic Curl", "sets": 3, "rep_low": 6, "rep_high": 10},
            ],
        }
        r = auth_client.post("/api/coach/accept/workout", json=body)
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

    def test_accept_workout_rejects_empty(self, auth_client):
        r = auth_client.post("/api/coach/accept/workout", json={"title": "X", "exercises": []})
        assert r.status_code == 422
