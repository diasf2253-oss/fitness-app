"""
Phase 4 tests — calendar markers and day detail.
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

from app.db import Base, get_db
from app.main import app

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


class TestCalendar:
    def test_empty_month(self):
        r = client.get("/api/calendar/2026/06", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"year": 2026, "month": 6, "days": []}

    def test_invalid_month_rejected(self):
        assert client.get("/api/calendar/2026/13", headers=AUTH).status_code == 422

    def test_markers_for_health_and_workouts(self):
        client.post("/api/health/weight",
                    json={"date": "2026-06-03", "weight_kg": 84}, headers=AUTH)
        client.post("/api/health/steps",
                    json={"date": "2026-06-03", "steps": 9000}, headers=AUTH)
        client.post("/api/sessions", json={"name": "Push day"}, headers=AUTH)  # today

        days = client.get("/api/calendar/2026/06", headers=AUTH).json()["days"]
        by_date = {d["date"]: d for d in days}
        assert by_date["2026-06-03"]["has_weight"] is True
        assert by_date["2026-06-03"]["steps"] == 9000
        assert by_date["2026-06-03"]["sessions"] == 0
        today = date.today().isoformat()
        assert by_date[today]["sessions"] == 1


class TestDayDetail:
    def test_empty_day(self):
        r = client.get("/api/day/2026-06-03", headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert data["sessions"] == []
        assert data["weight_kg"] is None
        assert data["nutrition"] is None

    def test_full_day_aggregation(self):
        d = "2026-06-03"
        client.post("/api/health/weight", json={"date": d, "weight_kg": 83.5}, headers=AUTH)
        client.post("/api/health/sleep",
                    json={"date": d, "asleep_minutes": 430, "in_bed_minutes": 465}, headers=AUTH)
        client.post("/api/nutrition",
                    json={"date": d, "calories": 2300, "protein_g": 175,
                          "carbs_g": 230, "fat_g": 78}, headers=AUTH)

        # A workout with one completed set — lands on today, not 2026-06-03
        ex = client.post("/api/exercises",
                         json={"name": "Row", "primary_muscle": "back", "is_custom": True},
                         headers=AUTH).json()
        session = client.post("/api/sessions", json={"name": "Pull"}, headers=AUTH).json()
        se = client.post(f"/api/sessions/{session['id']}/exercises",
                         json={"exercise_id": ex["id"], "position": 0,
                               "sets": [{"set_number": 1, "weight_kg": 60, "reps": 10}]},
                         headers=AUTH).json()
        client.patch(
            f"/api/sessions/{session['id']}/exercises/{se['id']}/sets/{se['sets'][0]['id']}",
            json={"is_completed": True}, headers=AUTH)

        day = client.get(f"/api/day/{d}", headers=AUTH).json()
        assert day["weight_kg"] == 83.5
        assert day["sleep"]["asleep_minutes"] == 430
        assert day["nutrition"]["calories"] == 2300
        assert day["sessions"] == []  # workout was today, not on d

        today = client.get(f"/api/day/{date.today().isoformat()}", headers=AUTH).json()
        assert len(today["sessions"]) == 1
        assert today["sessions"][0]["total_volume_kg"] == 600.0
