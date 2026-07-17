"""
Tests for Apple Health ingest endpoint:
  - Correct parsing of step_count, weight_body_mass, sleep_analysis
  - Idempotency: re-posting the same payload changes nothing
  - lb → kg unit conversion for weight
"""
import json
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use an in-memory SQLite database for tests — never touches fitness.sqlite3
TEST_DB_URL = "sqlite:///:memory:"

# Override DATABASE_URL before importing the app so config picks it up
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_TOKEN"] = "testtoken"

from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import app
from app.models import StepsLog, WeightLog, SleepLog

# StaticPool ensures all connections share one in-memory SQLite database.
# Without it, each new connection gets a fresh empty DB and sees no tables.
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


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)
AUTH = {"Authorization": "Bearer testtoken"}

SAMPLE_PAYLOAD_PATH = os.path.join(os.path.dirname(__file__), "sample_health_payload.json")


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe health tables before each test for isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def post_sample():
    with open(SAMPLE_PAYLOAD_PATH) as f:
        payload = json.load(f)
    return client.post("/api/ingest/health", json=payload, headers=AUTH)


class TestHealthIngest:
    def test_ping_is_public(self):
        r = client.get("/api/ping")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "env" in body  # environment label for the STAGING badge

    def test_ingest_requires_auth(self):
        r = client.post("/api/ingest/health", json={"data": {}})
        assert r.status_code == 403  # no token

    def test_ingest_sample_payload(self):
        r = post_sample()
        assert r.status_code == 200
        data = r.json()
        # 2 weight + 2 steps + 2 sleep + 2 nutrition days
        assert data["rows_upserted"] == 8
        assert "step_count" in data["metrics_handled"]
        assert "weight_body_mass" in data["metrics_handled"]
        assert "sleep_analysis" in data["metrics_handled"]
        assert "dietary_energy" in data["metrics_handled"]
        assert "sodium" in data["metrics_handled"]

    def test_weight_stored_correctly(self):
        post_sample()
        db = TestingSession()
        rows = db.query(WeightLog).order_by(WeightLog.date).all()
        db.close()
        assert len(rows) == 2
        assert rows[0].weight_kg == pytest.approx(84.2, abs=0.01)
        assert rows[1].weight_kg == pytest.approx(84.0, abs=0.01)
        assert rows[0].source == "apple_health"

    def test_steps_stored_correctly(self):
        post_sample()
        db = TestingSession()
        rows = db.query(StepsLog).order_by(StepsLog.date).all()
        db.close()
        assert len(rows) == 2
        assert rows[0].steps == 8432
        assert rows[1].steps == 11205

    def test_sleep_stored_correctly(self):
        post_sample()
        db = TestingSession()
        rows = db.query(SleepLog).order_by(SleepLog.date).all()
        db.close()
        assert len(rows) == 2
        assert rows[0].asleep_minutes == 427
        assert rows[0].deep_minutes == 68
        assert rows[0].rem_minutes == 95

    def test_idempotent_repost(self):
        """Re-posting the same payload must not create duplicate rows."""
        r1 = post_sample()
        r2 = post_sample()
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Second post: no new rows created
        assert r2.json()["rows_upserted"] == 0

        db = TestingSession()
        assert db.query(WeightLog).count() == 2
        assert db.query(StepsLog).count() == 2
        assert db.query(SleepLog).count() == 2
        db.close()

    def test_lb_to_kg_conversion(self):
        """Weight in lb should be converted to kg on ingest."""
        payload = {
            "data": {
                "metrics": [{
                    "name": "weight_body_mass",
                    "units": "lb",
                    "data": [{"date": "2026-01-01", "qty": 185.0}],
                }],
                "workouts": [],
            }
        }
        r = client.post("/api/ingest/health", json=payload, headers=AUTH)
        assert r.status_code == 200
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        # 185 lb × 0.453592 ≈ 83.91 kg
        assert row.weight_kg == pytest.approx(83.91, abs=0.1)

    def test_unknown_metrics_ignored(self):
        """Unknown metric names should be silently ignored, not crash."""
        payload = {
            "data": {
                "metrics": [
                    {"name": "heart_rate", "units": "bpm", "data": []},
                    {"name": "vo2_max",    "units": "ml/kg/min", "data": []},
                ],
                "workouts": [],
            }
        }
        r = client.post("/api/ingest/health", json=payload, headers=AUTH)
        assert r.status_code == 200
        data = r.json()
        assert "heart_rate" in data["metrics_ignored"]
        assert "vo2_max" in data["metrics_ignored"]
        assert data["rows_upserted"] == 0
