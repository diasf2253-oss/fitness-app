"""
Phase 6 tests — generic trackers:
  - CRUD + kind validation + archive behavior
  - Log upserts (idempotent by date), null-clears
  - Habit streak calculation (incl. the today-not-logged grace)
  - Day detail + calendar integration
"""
import os
from datetime import date, timedelta

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
from app.models import TrackerLog

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


def make_tracker(name="Meditate", kind="habit", unit=None):
    r = client.post("/api/trackers", json={"name": name, "kind": kind, "unit": unit}, headers=AUTH)
    assert r.status_code == 201
    return r.json()


def log(tracker_id, day, value_num=None, value_text=None):
    return client.post(
        f"/api/trackers/{tracker_id}/log",
        json={"date": day, "value_num": value_num, "value_text": value_text},
        headers=AUTH,
    )


class TestTrackerCrud:
    def test_create_and_list(self):
        make_tracker("Meditate", "habit")
        make_tracker("Reading", "number", unit="min")
        items = client.get("/api/trackers", headers=AUTH).json()
        assert [t["name"] for t in items] == ["Meditate", "Reading"]
        assert items[0]["streak"] == 0          # habits get a streak
        assert items[1]["streak"] is None       # numbers don't

    def test_invalid_kind_rejected(self):
        r = client.post("/api/trackers", json={"name": "X", "kind": "banana"}, headers=AUTH)
        assert r.status_code == 422

    def test_archive_hides_from_default_list(self):
        t = make_tracker()
        client.patch(f"/api/trackers/{t['id']}", json={"is_archived": True}, headers=AUTH)
        assert client.get("/api/trackers", headers=AUTH).json() == []
        all_items = client.get("/api/trackers?include_archived=true", headers=AUTH).json()
        assert len(all_items) == 1

    def test_delete_removes_history(self):
        t = make_tracker()
        log(t["id"], "2026-06-01", value_num=1)
        assert client.delete(f"/api/trackers/{t['id']}", headers=AUTH).status_code == 204
        db = TestingSession()
        assert db.query(TrackerLog).count() == 0
        db.close()


class TestTrackerLogs:
    def test_upsert_by_date(self):
        t = make_tracker("Reading", "number", unit="min")
        log(t["id"], "2026-06-01", value_num=30)
        log(t["id"], "2026-06-01", value_num=45)
        series = client.get(f"/api/trackers/{t['id']}/series?days=730", headers=AUTH).json()
        assert len(series) == 1
        assert series[0]["value_num"] == 45

    def test_null_values_clear_the_day(self):
        t = make_tracker("Journal", "text")
        log(t["id"], "2026-06-01", value_text="long day, good lift")
        r = log(t["id"], "2026-06-01", value_text="")
        assert r.json() is None
        assert client.get(f"/api/trackers/{t['id']}/series?days=730", headers=AUTH).json() == []

    def test_today_value_in_list(self):
        t = make_tracker("Mood", "scale")
        log(t["id"], date.today().isoformat(), value_num=4)
        items = client.get("/api/trackers", headers=AUTH).json()
        assert items[0]["today"]["value_num"] == 4


class TestStreaks:
    def test_consecutive_days(self):
        t = make_tracker()
        today = date.today()
        for offset in (0, 1, 2):
            log(t["id"], (today - timedelta(days=offset)).isoformat(), value_num=1)
        items = client.get("/api/trackers", headers=AUTH).json()
        assert items[0]["streak"] == 3

    def test_gap_breaks_streak(self):
        t = make_tracker()
        today = date.today()
        log(t["id"], today.isoformat(), value_num=1)
        log(t["id"], (today - timedelta(days=2)).isoformat(), value_num=1)  # gap yesterday
        items = client.get("/api/trackers", headers=AUTH).json()
        assert items[0]["streak"] == 1

    def test_unlogged_today_does_not_break_streak(self):
        t = make_tracker()
        today = date.today()
        for offset in (1, 2, 3):
            log(t["id"], (today - timedelta(days=offset)).isoformat(), value_num=1)
        items = client.get("/api/trackers", headers=AUTH).json()
        assert items[0]["streak"] == 3


class TestDayIntegration:
    def test_day_detail_includes_trackers(self):
        t = make_tracker("Mood", "scale")
        j = make_tracker("Journal", "text")
        log(t["id"], "2026-06-01", value_num=4)
        log(j["id"], "2026-06-01", value_text="quiet day")
        day = client.get("/api/day/2026-06-01", headers=AUTH).json()
        assert {x["name"]: x for x in day["trackers"]}["Mood"]["value_num"] == 4
        assert {x["name"]: x for x in day["trackers"]}["Journal"]["value_text"] == "quiet day"

    def test_calendar_counts_tracker_entries(self):
        t = make_tracker("Mood", "scale")
        log(t["id"], "2026-06-01", value_num=3)
        days = client.get("/api/calendar/2026/06", headers=AUTH).json()["days"]
        by_date = {d["date"]: d for d in days}
        assert by_date["2026-06-01"]["trackers"] == 1
