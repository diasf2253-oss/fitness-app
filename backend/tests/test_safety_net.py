"""
Safety net — the handful of flows whose breakage would erode trust in the app.

One legible file, one test class per flow:
  - Auth: every protected route rejects missing/wrong tokens, accepts the real one
  - Weight: logging a weight entry round-trips; re-saving a day corrects it
  - Workout: exercise → session → sets → complete → finish, end to end
  - Calories: a fresh app holds at the 2,300 kcal anchor (deep coverage of the
    adaptation engine lives in test_calorie_adapt.py and test_diet.py)
  - Apple Health: the sample Health Auto Export payload imports cleanly
    (deep coverage lives in test_health_ingest.py and test_apple_health.py)
"""
import json
import os
from datetime import date, datetime, timedelta

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
from app.models import WeightLog

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

SAMPLE_PAYLOAD_PATH = os.path.join(os.path.dirname(__file__), "sample_health_payload.json")

TODAY = date.today()


@pytest.fixture(autouse=True)
def clean_db():
    """Fresh tables per test; claim the get_db override, then hand it back."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_missing_token_is_rejected(self):
        r = client.get("/api/settings")
        assert r.status_code == 403  # HTTPBearer: no credentials at all

    def test_wrong_token_is_rejected(self):
        r = client.get("/api/settings", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401

    def test_valid_token_is_accepted(self):
        r = client.get("/api/settings", headers=AUTH)
        assert r.status_code == 200

    def test_writes_also_require_auth(self):
        r = client.post("/api/health/weight",
                        json={"date": str(TODAY), "weight_kg": 80.0})
        assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Logging a weight entry
# ---------------------------------------------------------------------------

class TestWeightEntry:
    def test_weight_entry_round_trips(self):
        r = client.post("/api/health/weight",
                        json={"date": str(TODAY), "weight_kg": 82.5}, headers=AUTH)
        assert r.status_code == 201
        body = r.json()
        assert body["weight_kg"] == 82.5
        assert body["source"] == "manual"

        rows = client.get("/api/health/weight", headers=AUTH).json()
        assert [(row["date"], row["weight_kg"]) for row in rows] == [(str(TODAY), 82.5)]

    def test_resaving_a_day_corrects_it(self):
        client.post("/api/health/weight",
                    json={"date": str(TODAY), "weight_kg": 82.5}, headers=AUTH)
        client.post("/api/health/weight",
                    json={"date": str(TODAY), "weight_kg": 83.0}, headers=AUTH)
        rows = client.get("/api/health/weight", headers=AUTH).json()
        assert len(rows) == 1  # upsert, not a duplicate
        assert rows[0]["weight_kg"] == 83.0


# ---------------------------------------------------------------------------
# Logging a workout
# ---------------------------------------------------------------------------

class TestWorkoutLogging:
    def test_full_workout_flow(self):
        # Create an exercise to log against
        r = client.post("/api/exercises", json={"name": "Safety-Net Bench Press"},
                        headers=AUTH)
        assert r.status_code == 201
        exercise_id = r.json()["id"]

        # Start an ad-hoc session
        r = client.post("/api/sessions", json={"name": "Push day"}, headers=AUTH)
        assert r.status_code == 201
        session_id = r.json()["id"]
        assert r.json()["ended_at"] is None

        # Add the exercise, then a set
        r = client.post(f"/api/sessions/{session_id}/exercises",
                        json={"exercise_id": exercise_id, "position": 1}, headers=AUTH)
        assert r.status_code == 201
        se_id = r.json()["id"]

        r = client.post(f"/api/sessions/{session_id}/exercises/{se_id}/sets",
                        json={"set_number": 1, "weight_kg": 80.0, "reps": 5},
                        headers=AUTH)
        assert r.status_code == 201
        set_id = r.json()["id"]

        # Edit the set the way the UI does (blur-save), then complete it
        r = client.patch(
            f"/api/sessions/{session_id}/exercises/{se_id}/sets/{set_id}",
            json={"weight_kg": 82.5, "reps": 6, "is_completed": True}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

        # The whole session reads back intact
        session = client.get(f"/api/sessions/{session_id}", headers=AUTH).json()
        [se] = session["exercises"]
        assert se["exercise"]["name"] == "Safety-Net Bench Press"
        [logged_set] = se["sets"]
        assert logged_set["weight_kg"] == 82.5
        assert logged_set["reps"] == 6
        assert logged_set["is_completed"] is True

        # Finish the workout
        ended = datetime.utcnow().isoformat()
        r = client.patch(f"/api/sessions/{session_id}", json={"ended_at": ended},
                         headers=AUTH)
        assert r.status_code == 200
        assert r.json()["ended_at"] is not None
        # No session is active any more
        assert client.get("/api/sessions/active", headers=AUTH).json() is None


# ---------------------------------------------------------------------------
# Calorie target — the 2,300 kcal anchor
# ---------------------------------------------------------------------------

class TestCalorieAnchor:
    def test_fresh_app_holds_at_the_2300_anchor(self):
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == 2300
        # Carbs flex around the fixed macros: (2300 − 180·4 − 100·9) / 4
        assert e["carb_target_g"] == 170
        assert "2300 kcal anchor" in e["note"]


# ---------------------------------------------------------------------------
# Apple Health import — the sample Health Auto Export payload
# ---------------------------------------------------------------------------

class TestAppleHealthImport:
    def test_sample_payload_imports(self):
        with open(SAMPLE_PAYLOAD_PATH) as f:
            payload = json.load(f)
        r = client.post("/api/ingest/health", json=payload, headers=AUTH)
        assert r.status_code == 200
        # 2 weight + 2 steps + 2 sleep + 2 nutrition days
        assert r.json()["rows_upserted"] == 8

        db = TestingSession()
        weights = db.query(WeightLog).order_by(WeightLog.date).all()
        db.close()
        assert [w.weight_kg for w in weights] == [84.2, 84.0]
        assert all(w.source == "apple_health" for w in weights)
