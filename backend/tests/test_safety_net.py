"""
Safety net — the handful of flows whose breakage would erode trust in the app.

One legible file, one test class per flow:
  - Auth: every protected route rejects an unauthenticated request, accepts a
    logged-in session; a second user can never reach the first user's data
  - Weight: logging a weight entry round-trips; re-saving a day corrects it
  - Workout: exercise → session → sets → complete → finish, end to end
  - Calories: a fresh app holds at the 2,300 kcal anchor (deep coverage of the
    adaptation engine lives in test_calorie_adapt.py and test_diet.py)
  - Apple Health: the sample Health Auto Export payload imports cleanly
    (deep coverage lives in test_health_ingest.py and test_apple_health.py)

Auth fixtures (`client`, `auth_client`) come from conftest.py — see its
docstring for the pattern other test files still need to migrate to.
"""
import json
import os
from datetime import date, datetime

from app.auth import hash_password
from app.models import User, WeightLog

from tests.conftest import TestingSession

SAMPLE_PAYLOAD_PATH = os.path.join(os.path.dirname(__file__), "sample_health_payload.json")

TODAY = date.today()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_unauthenticated_request_is_rejected(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 401

    def test_authenticated_request_is_accepted(self, auth_client):
        r = auth_client.get("/api/settings")
        assert r.status_code == 200

    def test_writes_also_require_auth(self, client):
        r = client.post("/api/health/weight", json={"date": str(TODAY), "weight_kg": 80.0})
        assert r.status_code == 401

    def test_second_user_cannot_reach_the_first_users_data(self, auth_client, client):
        """The core multi-tenant guarantee: a resource id that exists for one
        user must 404 (not leak) for a different, equally-authenticated user."""
        routine = auth_client.post("/api/routines", json={"name": "Owner's routine"})
        assert routine.status_code == 201
        routine_id = routine.json()["id"]

        db = TestingSession()
        other = User(
            email="other@example.com", password_hash=hash_password("otherpassword123"),
            name="Other User", role="user", status="active",
        )
        db.add(other)
        db.commit()
        db.close()

        r = client.post("/api/auth/login", json={
            "email": "other@example.com", "password": "otherpassword123", "remember": True,
        })
        assert r.status_code == 200

        assert client.get(f"/api/routines/{routine_id}").status_code == 404
        assert client.get("/api/routines").json() == []


# ---------------------------------------------------------------------------
# Logging a weight entry
# ---------------------------------------------------------------------------

class TestWeightEntry:
    def test_weight_entry_round_trips(self, auth_client):
        r = auth_client.post("/api/health/weight", json={"date": str(TODAY), "weight_kg": 82.5})
        assert r.status_code == 201
        body = r.json()
        assert body["weight_kg"] == 82.5
        assert body["source"] == "manual"

        rows = auth_client.get("/api/health/weight").json()
        assert [(row["date"], row["weight_kg"]) for row in rows] == [(str(TODAY), 82.5)]

    def test_resaving_a_day_corrects_it(self, auth_client):
        auth_client.post("/api/health/weight", json={"date": str(TODAY), "weight_kg": 82.5})
        auth_client.post("/api/health/weight", json={"date": str(TODAY), "weight_kg": 83.0})
        rows = auth_client.get("/api/health/weight").json()
        assert len(rows) == 1  # upsert, not a duplicate
        assert rows[0]["weight_kg"] == 83.0


# ---------------------------------------------------------------------------
# Logging a workout
# ---------------------------------------------------------------------------

class TestWorkoutLogging:
    def test_full_workout_flow(self, auth_client):
        # Create an exercise to log against
        r = auth_client.post("/api/exercises", json={"name": "Safety-Net Bench Press"})
        assert r.status_code == 201
        exercise_id = r.json()["id"]

        # Start an ad-hoc session
        r = auth_client.post("/api/sessions", json={"name": "Push day"})
        assert r.status_code == 201
        session_id = r.json()["id"]
        assert r.json()["ended_at"] is None

        # Add the exercise, then a set
        r = auth_client.post(f"/api/sessions/{session_id}/exercises",
                             json={"exercise_id": exercise_id, "position": 1})
        assert r.status_code == 201
        se_id = r.json()["id"]

        r = auth_client.post(f"/api/sessions/{session_id}/exercises/{se_id}/sets",
                             json={"set_number": 1, "weight_kg": 80.0, "reps": 5})
        assert r.status_code == 201
        set_id = r.json()["id"]

        # Edit the set the way the UI does (blur-save), then complete it
        r = auth_client.patch(
            f"/api/sessions/{session_id}/exercises/{se_id}/sets/{set_id}",
            json={"weight_kg": 82.5, "reps": 6, "is_completed": True})
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

        # The whole session reads back intact
        session = auth_client.get(f"/api/sessions/{session_id}").json()
        [se] = session["exercises"]
        assert se["exercise"]["name"] == "Safety-Net Bench Press"
        [logged_set] = se["sets"]
        assert logged_set["weight_kg"] == 82.5
        assert logged_set["reps"] == 6
        assert logged_set["is_completed"] is True

        # Finish the workout
        ended = datetime.utcnow().isoformat()
        r = auth_client.patch(f"/api/sessions/{session_id}", json={"ended_at": ended})
        assert r.status_code == 200
        assert r.json()["ended_at"] is not None
        # No session is active any more
        assert auth_client.get("/api/sessions/active").json() is None


# ---------------------------------------------------------------------------
# Calorie target — the 2,300 kcal anchor
# ---------------------------------------------------------------------------

class TestCalorieAnchor:
    def test_fresh_app_holds_at_the_2300_anchor(self, auth_client):
        e = auth_client.get("/api/diet").json()["energy"]
        assert e["calorie_target"] == 2300
        # Carbs flex around the fixed macros: (2300 − 180·4 − 100·9) / 4
        assert e["carb_target_g"] == 170
        assert "2300 kcal anchor" in e["note"]


# ---------------------------------------------------------------------------
# Apple Health import — the sample Health Auto Export payload
# ---------------------------------------------------------------------------

class TestAppleHealthImport:
    def test_sample_payload_imports(self, auth_client):
        with open(SAMPLE_PAYLOAD_PATH) as f:
            payload = json.load(f)
        me = auth_client.get("/api/auth/me").json()
        ingest_headers = {"Authorization": f"Bearer {me['ingest_token']}"}

        r = auth_client.post("/api/ingest/health", json=payload, headers=ingest_headers)
        assert r.status_code == 200
        # 2 weight + 2 steps + 2 sleep + 2 nutrition days
        assert r.json()["rows_upserted"] == 8

        db = TestingSession()
        weights = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == auth_client.test_user_id)
            .order_by(WeightLog.date)
            .all()
        )
        db.close()
        assert [w.weight_kg for w in weights] == [84.2, 84.0]
        assert all(w.source == "apple_health" for w in weights)
