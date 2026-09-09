"""
Phase 9 sync tests — device-to-device pull/push:
  - manifest counts, pull full / incremental (since)
  - push: uuid-keyed insert with FK resolution (exercise → session →
    session_exercise → set), last-write-wins updates, older skipped
  - health rows respect source precedence on merge (manual is sacred)
  - natural-key fallback (same exercise name created on both devices)
  - missing parents skip with a warning instead of crashing
  - roundtrip pull→push is a no-op (no echo inserts/updates)

Sync scopes every row to the authenticated user server-side; the client
never sends user_id, so the push payloads below carry none.
"""
from datetime import date, datetime, timedelta

from app.models import Exercise, Session, Set, Tracker, WeightLog

from tests.conftest import TestingSession


def push(client, tables):
    return client.post("/api/sync/push", json={"tables": tables})


def iso(dt):
    return dt.isoformat()


NOW = datetime(2026, 7, 10, 12, 0, 0)


class TestManifestAndPull:
    def test_requires_auth(self, client):
        assert client.get("/api/sync/manifest").status_code == 401
        assert client.get("/api/sync/pull").status_code == 401
        assert client.post("/api/sync/push", json={"tables": {}}).status_code == 401

    def test_manifest_counts(self, auth_client):
        auth_client.post("/api/health/weight",
                         json={"date": "2026-06-01", "weight_kg": 84})
        m = auth_client.get("/api/sync/manifest").json()
        assert m["tables"]["weight_log"]["rows"] == 1
        assert m["tables"]["weight_log"]["last_updated"] is not None
        assert m["tables"]["session"]["rows"] == 0

    def test_pull_full_and_incremental(self, auth_client):
        auth_client.post("/api/health/weight",
                         json={"date": "2026-06-01", "weight_kg": 84})
        full = auth_client.get("/api/sync/pull").json()
        assert len(full["tables"]["weight_log"]) == 1
        row = full["tables"]["weight_log"][0]
        assert row["weight_kg"] == 84
        assert "id" not in row              # device-local ids never travel
        assert row["updated_at"] is not None

        # since=now → nothing new
        later = auth_client.get(
            "/api/sync/pull", params={"since": full["server_time"]}
        ).json()
        assert later["tables"] == {}


class TestPushEntities:
    def test_workout_chain_inserts_via_uuids(self, auth_client):
        r = push(auth_client, {
            "exercise": [{"uuid": "ex-1", "name": "Bench Press", "is_custom": False,
                          "updated_at": iso(NOW)}],
            "session": [{"uuid": "s-1", "name": "Push day",
                         "routine_uuid": None,
                         "started_at": iso(NOW), "updated_at": iso(NOW)}],
            "session_exercise": [{"uuid": "se-1", "session_uuid": "s-1",
                                  "exercise_uuid": "ex-1", "position": 1,
                                  "updated_at": iso(NOW)}],
            "set": [{"uuid": "set-1", "session_exercise_uuid": "se-1",
                     "set_number": 1, "weight_kg": 80.0, "reps": 8,
                     "is_warmup": False, "is_completed": True,
                     "updated_at": iso(NOW)}],
        })
        assert r.status_code == 200
        counts = r.json()["counts"]
        for table in ("exercise", "session", "session_exercise", "set"):
            assert counts[table]["inserted"] == 1, table

        db = TestingSession()
        st = db.query(Set).first()
        assert st.weight_kg == 80.0
        # FK chain resolved to local integer ids
        assert st.session_exercise.session.name == "Push day"
        assert st.session_exercise.exercise.name == "Bench Press"
        db.close()

    def test_lww_newer_wins_older_skipped(self, auth_client):
        push(auth_client, {"exercise": [{"uuid": "ex-1", "name": "Row", "is_custom": False,
                                         "updated_at": iso(NOW)}]})
        # Older edit → skipped
        r_old = push(auth_client, {"exercise": [{"uuid": "ex-1", "name": "Old Row", "is_custom": False,
                                                 "updated_at": iso(NOW - timedelta(days=1))}]})
        assert r_old.json()["counts"]["exercise"]["skipped_older"] == 1
        # Newer edit → applied
        r_new = push(auth_client, {"exercise": [{"uuid": "ex-1", "name": "Cable Row", "is_custom": False,
                                                 "updated_at": iso(NOW + timedelta(days=1))}]})
        assert r_new.json()["counts"]["exercise"]["updated"] == 1

        db = TestingSession()
        ex = db.query(Exercise).one()
        assert ex.name == "Cable Row"
        # Incoming timestamp preserved verbatim — no local re-stamping
        assert ex.updated_at == NOW + timedelta(days=1)
        db.close()

    def test_missing_required_parent_skips_with_warning(self, auth_client):
        r = push(auth_client, {"set": [{"uuid": "set-9", "session_exercise_uuid": "nope",
                                        "set_number": 1, "weight_kg": 50.0, "reps": 5,
                                        "is_warmup": False, "is_completed": True,
                                        "updated_at": iso(NOW)}]})
        body = r.json()
        assert body["counts"]["set"]["skipped_missing_parent"] == 1
        assert any("parent not found" in w for w in body["warnings"])

    def test_natural_key_merge_same_exercise_name(self, auth_client):
        # Local device already has "Deadlift" under its own uuid
        push(auth_client, {"exercise": [{"uuid": "local-dl", "name": "Deadlift", "is_custom": False,
                                         "updated_at": iso(NOW)}]})
        # Other device created the same exercise independently (different uuid)
        # and logged a session against it
        r = push(auth_client, {
            "exercise": [{"uuid": "remote-dl", "name": "Deadlift", "is_custom": False,
                          "notes": "cue: brace", "updated_at": iso(NOW + timedelta(hours=1))}],
            "session": [{"uuid": "s-2", "name": "Pull day", "routine_uuid": None,
                         "started_at": iso(NOW), "updated_at": iso(NOW)}],
            "session_exercise": [{"uuid": "se-2", "session_uuid": "s-2",
                                  "exercise_uuid": "remote-dl", "position": 1,
                                  "updated_at": iso(NOW)}],
        })
        assert r.status_code == 200
        db = TestingSession()
        exercises = db.query(Exercise).all()
        assert len(exercises) == 1                     # merged, not duplicated
        assert exercises[0].uuid == "local-dl"         # local identity kept
        assert exercises[0].notes == "cue: brace"      # newer fields merged
        sess = db.query(Session).one()
        assert sess.exercises[0].exercise.uuid == "local-dl"   # child remapped
        db.close()


class TestPushHealth:
    def test_manual_not_buried_even_by_newer_sync(self, auth_client):
        auth_client.post("/api/health/weight",
                         json={"date": "2026-06-01", "weight_kg": 83.0})
        # Even a strictly newer timestamp must not bury a manual correction
        r = push(auth_client, {"weight_log": [{"date": "2026-06-01", "weight_kg": 90.0,
                                               "source": "apple_health",
                                               "updated_at": iso(datetime.utcnow() + timedelta(days=1))}]})
        assert r.json()["counts"]["weight_log"]["skipped_blocked"] == 1
        db = TestingSession()
        row = db.query(WeightLog).one()
        assert row.weight_kg == 83.0
        assert row.source == "manual"
        db.close()

    def test_health_lww_by_date(self, auth_client):
        push(auth_client, {"weight_log": [{"date": "2026-06-01", "weight_kg": 84.0,
                                           "source": "apple_health", "updated_at": iso(NOW)}]})
        r = push(auth_client, {"weight_log": [{"date": "2026-06-01", "weight_kg": 83.5,
                                               "source": "apple_health",
                                               "updated_at": iso(NOW + timedelta(hours=2))}]})
        assert r.json()["counts"]["weight_log"]["updated"] == 1
        db = TestingSession()
        assert db.query(WeightLog).one().weight_kg == 83.5
        db.close()


class TestRoundtrip:
    def test_pull_then_push_back_is_noop(self, auth_client):
        """Pushing a device's own pull back must not create or update anything."""
        auth_client.post("/api/health/weight",
                         json={"date": "2026-06-01", "weight_kg": 84})
        push(auth_client, {
            "exercise": [{"uuid": "ex-1", "name": "Squat", "is_custom": False,
                          "updated_at": iso(NOW)}],
            "tracker": [{"uuid": "t-1", "name": "Mood", "kind": "scale",
                         "position": 0, "is_archived": False,
                         "created_at": iso(NOW), "updated_at": iso(NOW)}],
            "tracker_log": [{"uuid": "tl-1", "tracker_uuid": "t-1",
                             "date": "2026-06-01", "value_num": 4,
                             "updated_at": iso(NOW)}],
        })
        pulled = auth_client.get("/api/sync/pull").json()["tables"]
        r = push(auth_client, pulled)
        for table, c in r.json()["counts"].items():
            assert c["inserted"] == 0, table
            assert c["updated"] == 0, table
