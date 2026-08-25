"""
Phase 6 tests — generic trackers:
  - CRUD + kind validation + archive behavior
  - Log upserts (idempotent by date), null-clears
  - Habit streak calculation (incl. the today-not-logged grace)
  - Day detail + calendar integration
"""
from datetime import date, timedelta

from app.models import TrackerLog

from tests.conftest import TestingSession


def make_tracker(client, name="Meditate", kind="habit", unit=None):
    r = client.post("/api/trackers", json={"name": name, "kind": kind, "unit": unit})
    assert r.status_code == 201
    return r.json()


def log(client, tracker_id, day, value_num=None, value_text=None):
    return client.post(
        f"/api/trackers/{tracker_id}/log",
        json={"date": day, "value_num": value_num, "value_text": value_text},
    )


class TestTrackerCrud:
    def test_create_and_list(self, auth_client):
        make_tracker(auth_client, "Meditate", "habit")
        make_tracker(auth_client, "Reading", "number", unit="min")
        items = auth_client.get("/api/trackers").json()
        assert [t["name"] for t in items] == ["Meditate", "Reading"]
        assert items[0]["streak"] == 0          # habits get a streak
        assert items[1]["streak"] is None       # numbers don't

    def test_invalid_kind_rejected(self, auth_client):
        r = auth_client.post("/api/trackers", json={"name": "X", "kind": "banana"})
        assert r.status_code == 422

    def test_archive_hides_from_default_list(self, auth_client):
        t = make_tracker(auth_client)
        auth_client.patch(f"/api/trackers/{t['id']}", json={"is_archived": True})
        assert auth_client.get("/api/trackers").json() == []
        all_items = auth_client.get("/api/trackers?include_archived=true").json()
        assert len(all_items) == 1

    def test_delete_removes_history(self, auth_client):
        t = make_tracker(auth_client)
        log(auth_client, t["id"], "2026-06-01", value_num=1)
        assert auth_client.delete(f"/api/trackers/{t['id']}").status_code == 204
        db = TestingSession()
        assert db.query(TrackerLog).count() == 0
        db.close()


class TestTrackerLogs:
    def test_upsert_by_date(self, auth_client):
        t = make_tracker(auth_client, "Reading", "number", unit="min")
        log(auth_client, t["id"], "2026-06-01", value_num=30)
        log(auth_client, t["id"], "2026-06-01", value_num=45)
        series = auth_client.get(f"/api/trackers/{t['id']}/series?days=730").json()
        assert len(series) == 1
        assert series[0]["value_num"] == 45

    def test_null_values_clear_the_day(self, auth_client):
        t = make_tracker(auth_client, "Journal", "text")
        log(auth_client, t["id"], "2026-06-01", value_text="long day, good lift")
        r = log(auth_client, t["id"], "2026-06-01", value_text="")
        assert r.json() is None
        assert auth_client.get(f"/api/trackers/{t['id']}/series?days=730").json() == []

    def test_today_value_in_list(self, auth_client):
        t = make_tracker(auth_client, "Mood", "scale")
        log(auth_client, t["id"], date.today().isoformat(), value_num=4)
        items = auth_client.get("/api/trackers").json()
        assert items[0]["today"]["value_num"] == 4


class TestStreaks:
    def test_consecutive_days(self, auth_client):
        t = make_tracker(auth_client)
        today = date.today()
        for offset in (0, 1, 2):
            log(auth_client, t["id"], (today - timedelta(days=offset)).isoformat(), value_num=1)
        items = auth_client.get("/api/trackers").json()
        assert items[0]["streak"] == 3

    def test_gap_breaks_streak(self, auth_client):
        t = make_tracker(auth_client)
        today = date.today()
        log(auth_client, t["id"], today.isoformat(), value_num=1)
        log(auth_client, t["id"], (today - timedelta(days=2)).isoformat(), value_num=1)  # gap yesterday
        items = auth_client.get("/api/trackers").json()
        assert items[0]["streak"] == 1

    def test_unlogged_today_does_not_break_streak(self, auth_client):
        t = make_tracker(auth_client)
        today = date.today()
        for offset in (1, 2, 3):
            log(auth_client, t["id"], (today - timedelta(days=offset)).isoformat(), value_num=1)
        items = auth_client.get("/api/trackers").json()
        assert items[0]["streak"] == 3


class TestDayIntegration:
    def test_day_detail_includes_trackers(self, auth_client):
        t = make_tracker(auth_client, "Mood", "scale")
        j = make_tracker(auth_client, "Journal", "text")
        log(auth_client, t["id"], "2026-06-01", value_num=4)
        log(auth_client, j["id"], "2026-06-01", value_text="quiet day")
        day = auth_client.get("/api/day/2026-06-01").json()
        assert {x["name"]: x for x in day["trackers"]}["Mood"]["value_num"] == 4
        assert {x["name"]: x for x in day["trackers"]}["Journal"]["value_text"] == "quiet day"

    def test_calendar_counts_tracker_entries(self, auth_client):
        t = make_tracker(auth_client, "Mood", "scale")
        log(auth_client, t["id"], "2026-06-01", value_num=3)
        days = auth_client.get("/api/calendar/2026/06").json()["days"]
        by_date = {d["date"]: d for d in days}
        assert by_date["2026-06-01"]["trackers"] == 1
