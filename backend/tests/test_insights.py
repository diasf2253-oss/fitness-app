"""
Phase 7 tests — insights:
  - Pearson correctness + degenerate cases
  - Weekly review aggregation across two known weeks
  - Correlation pair thresholds (n >= 10) and detection
  - Training-day splits inclusion rules
"""
import os
from datetime import date, datetime, time, timedelta

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
from app.models import Session as WorkoutSession
from app.routers.insights import pearson

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


class TestPearson:
    def test_perfect_positive(self):
        assert pearson([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)

    def test_perfect_negative(self):
        assert pearson([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)

    def test_constant_series_undefined(self):
        assert pearson([1, 2, 3], [5, 5, 5]) is None

    def test_too_few_points(self):
        assert pearson([1], [2]) is None

    def test_known_value(self):
        # Hand-checked: r ≈ 0.7857 for these
        r = pearson([1, 2, 3, 4, 5], [2, 1, 4, 3, 5])
        assert r == pytest.approx(0.8, abs=0.02)


class TestWeeklyReview:
    def test_two_week_comparison(self):
        today = date.today()
        # Current week: steps 10000/day for 3 days; previous: 8000/day for 2
        for offset in (0, 1, 2):
            client.post("/api/health/steps",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "steps": 10000},
                        headers=AUTH)
        for offset in (8, 9):
            client.post("/api/health/steps",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "steps": 8000},
                        headers=AUTH)
        # Weight drops 0.5 kg inside the current week
        client.post("/api/health/weight",
                    json={"date": (today - timedelta(days=5)).isoformat(), "weight_kg": 84.0},
                    headers=AUTH)
        client.post("/api/health/weight",
                    json={"date": today.isoformat(), "weight_kg": 83.5}, headers=AUTH)

        data = client.get("/api/insights/weekly", headers=AUTH).json()
        assert data["current"]["steps_avg"] == 10000
        assert data["previous"]["steps_avg"] == 8000
        assert data["current"]["weight_change_kg"] == -0.5
        assert data["previous"]["weight_change_kg"] is None  # <2 readings

    def test_habits_and_scales_in_review(self):
        t = client.post("/api/trackers", json={"name": "Meditate", "kind": "habit"}, headers=AUTH).json()
        m = client.post("/api/trackers", json={"name": "Mood", "kind": "scale"}, headers=AUTH).json()
        today = date.today()
        for offset in (0, 1):
            client.post(f"/api/trackers/{t['id']}/log",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "value_num": 1},
                        headers=AUTH)
        client.post(f"/api/trackers/{m['id']}/log",
                    json={"date": today.isoformat(), "value_num": 4}, headers=AUTH)

        cur = client.get("/api/insights/weekly", headers=AUTH).json()["current"]
        assert cur["habits"] == [{"name": "Meditate", "done": 2, "days": 7}]
        assert cur["scales"] == [{"name": "Mood", "avg": 4.0}]


class TestCorrelations:
    def seed_pair_days(self, n, steps_for_day):
        today = date.today()
        for i in range(n):
            d = (today - timedelta(days=i)).isoformat()
            client.post("/api/health/sleep",
                        json={"date": d, "asleep_minutes": 360 + i * 10, "in_bed_minutes": 480},
                        headers=AUTH)
            client.post("/api/health/steps",
                        json={"date": d, "steps": steps_for_day(i)}, headers=AUTH)

    def test_strong_correlation_detected(self):
        # Steps move linearly with sleep → r ≈ 1 on the Sleep×Steps pair
        self.seed_pair_days(12, lambda i: 5000 + i * 500)
        data = client.get("/api/insights/correlations", headers=AUTH).json()
        pair = next(p for p in data["pairs"]
                    if {p["label_a"], p["label_b"]} == {"Sleep (h)", "Steps"})
        assert pair["n"] == 12
        assert pair["r"] == pytest.approx(1.0, abs=0.01)
        assert len(pair["points"]) == 12

    def test_min_n_threshold(self):
        # Only 5 overlapping days → pair must not appear
        self.seed_pair_days(5, lambda i: 5000 + i * 500)
        data = client.get("/api/insights/correlations", headers=AUTH).json()
        assert not any({p["label_a"], p["label_b"]} == {"Sleep (h)", "Steps"}
                       for p in data["pairs"])

    def test_training_split(self):
        m = client.post("/api/trackers", json={"name": "Mood", "kind": "scale"}, headers=AUTH).json()
        today = date.today()

        # 5 training days (sessions written directly so dates differ) + mood 5
        db = TestingSession()
        for offset in range(5):
            d = today - timedelta(days=offset)
            db.add(WorkoutSession(
                name=f"S{offset}",
                started_at=datetime.combine(d, time(hour=10)),
                ended_at=datetime.combine(d, time(hour=11)),
            ))
        db.commit()
        db.close()
        for offset in range(5):
            client.post(f"/api/trackers/{m['id']}/log",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "value_num": 5},
                        headers=AUTH)
        # 5 rest days with mood 3
        for offset in range(5, 10):
            client.post(f"/api/trackers/{m['id']}/log",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "value_num": 3},
                        headers=AUTH)

        data = client.get("/api/insights/correlations", headers=AUTH).json()
        assert data["training_splits"] == [{
            "name": "Mood", "with_avg": 5.0, "without_avg": 3.0,
            "n_with": 5, "n_without": 5,
        }]

    def test_split_needs_both_sides(self):
        m = client.post("/api/trackers", json={"name": "Mood", "kind": "scale"}, headers=AUTH).json()
        today = date.today()
        # Mood logged on rest days only → no split
        for offset in range(6):
            client.post(f"/api/trackers/{m['id']}/log",
                        json={"date": (today - timedelta(days=offset)).isoformat(), "value_num": 3},
                        headers=AUTH)
        data = client.get("/api/insights/correlations", headers=AUTH).json()
        assert data["training_splits"] == []
