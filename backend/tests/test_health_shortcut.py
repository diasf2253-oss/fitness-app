"""
iOS Shortcut ingest — POST /api/ingest/health/shortcut.

The Shortcut posts the day's weight/steps/sleep as a small JSON payload; the
endpoint must route it through the *same* validated pipeline as the
export.xml backfill: kg normalisation, wake-date sleep bucketing, latest
weight of the day, manual-precedence, and idempotent upserts. The report it
returns is the trust gate — a posted sample must show up there and in the
read endpoints.

Ingest authenticates via the per-user bearer `ingest_token`; manual
corrections use the normal cookie-authenticated endpoints.
"""
import json
import os
from datetime import date, timedelta

import pytest

from app.models import SleepLog, StepsLog, WeightLog

from tests.conftest import TestingSession

SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "shortcut_sample_payload.json")


def ingest_headers(client):
    """Bearer header carrying the logged-in user's ingest_token."""
    me = client.get("/api/auth/me").json()
    return {"Authorization": f"Bearer {me['ingest_token']}"}


def post(client, payload):
    return client.post("/api/ingest/health/shortcut", json=payload,
                       headers=ingest_headers(client))


def post_sample(client):
    with open(SAMPLE_PATH) as f:
        return post(client, json.load(f))


# ---------------------------------------------------------------------------
# The acceptance path: sample payload lands, and the report proves it
# ---------------------------------------------------------------------------

class TestSamplePayload:
    def test_requires_auth(self, client):
        assert client.post("/api/ingest/health/shortcut", json={}).status_code == 401

    def test_report_shape(self, auth_client):
        r = post_sample(auth_client)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["days"] == {"weight": 2, "steps": 2, "sleep": 1, "nutrition": 0}
        assert data["rows_created"] == 5
        assert data["date_range"] == {"from": "2026-07-17", "to": "2026-07-18"}
        assert data["sections_handled"] == ["sleep", "steps", "weight"]
        assert data["ignored"] == []
        assert data["warnings"] == []

    def test_rows_land_in_the_app(self, auth_client):
        post_sample(auth_client)
        db = TestingSession()
        weights = db.query(WeightLog).order_by(WeightLog.date).all()
        steps = db.query(StepsLog).order_by(StepsLog.date).all()
        sleep = db.query(SleepLog).order_by(SleepLog.date).all()
        db.close()

        assert [w.weight_kg for w in weights] == [82.6, 82.4]
        assert all(w.source == "apple_health" for w in weights)
        assert [s.steps for s in steps] == [9210, 11205]
        assert len(sleep) == 1
        assert sleep[0].date == date(2026, 7, 18)
        assert sleep[0].asleep_minutes == 427
        assert sleep[0].in_bed_minutes == 465
        assert sleep[0].deep_minutes == 68
        assert sleep[0].rem_minutes == 95
        assert sleep[0].core_minutes == 264

    def test_visible_via_read_endpoints(self, auth_client):
        post_sample(auth_client)
        w = auth_client.get("/api/health/weight", params={"days": 365}).json()
        assert {"date": "2026-07-18", "weight_kg": 82.4, "source": "apple_health"}.items() <= \
            next(r for r in w if r["date"] == "2026-07-18").items()

    def test_touches_last_ingest_timestamp(self, auth_client):
        assert auth_client.get("/api/settings").json()["health_last_ingest"] is None
        post_sample(auth_client)
        assert auth_client.get("/api/settings").json()["health_last_ingest"] is not None

    def test_idempotent_repost(self, auth_client):
        assert post_sample(auth_client).json()["rows_created"] == 5
        assert post_sample(auth_client).json()["rows_created"] == 0
        db = TestingSession()
        assert db.query(WeightLog).count() == 2
        assert db.query(StepsLog).count() == 2
        assert db.query(SleepLog).count() == 1
        db.close()


# ---------------------------------------------------------------------------
# The shared-pipeline guarantees: units, dedup, manual-precedence
# ---------------------------------------------------------------------------

class TestPipelineReuse:
    def test_lb_to_kg(self, auth_client):
        post(auth_client, {"weight": [{"date": "2026-07-18", "value": 185, "unit": "lb"}]})
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        assert row.weight_kg == pytest.approx(83.91, abs=0.05)

    def test_comma_decimal_from_ptbr_shortcut(self, auth_client):
        # A pt-BR phone emits "82,5" for 82.5 — must not be read as 825 or fail.
        post(auth_client, {"weight": [{"date": "2026-07-18", "kg": "82,5"}]})
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        assert row.weight_kg == pytest.approx(82.5, abs=0.001)

    def test_latest_weight_of_day_wins(self, auth_client):
        post(auth_client, {"weight": [
            {"date": "2026-07-18T06:00:00-03:00", "kg": 83.0},
            {"date": "2026-07-18T21:00:00-03:00", "kg": 82.0},
        ]})
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 7, 18)).first()
        db.close()
        assert row.weight_kg == 82.0  # the later reading

    def test_sleep_keyed_to_the_posted_wake_date(self, auth_client):
        post(auth_client, {"sleep": [{"date": "2026-07-18", "asleep_minutes": 400}]})
        db = TestingSession()
        row = db.query(SleepLog).first()
        db.close()
        assert row.date == date(2026, 7, 18)

    def test_manual_correction_survives(self, auth_client):
        auth_client.post("/api/health/weight",
                         json={"date": "2026-07-18", "weight_kg": 80.0})
        post(auth_client, {"weight": [{"date": "2026-07-18", "kg": 82.4}]})
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        assert row.weight_kg == 80.0
        assert row.source == "manual"


# ---------------------------------------------------------------------------
# Robustness: partial payloads, loose shapes, bad items
# ---------------------------------------------------------------------------

class TestRobustness:
    def test_single_object_sections_allowed(self, auth_client):
        # Not everyone builds arrays in Shortcuts — a lone object must work too.
        r = post(auth_client, {"steps": {"date": "2026-07-18", "count": 8000}})
        assert r.json()["days"]["steps"] == 1

    def test_partial_payload_only_steps(self, auth_client):
        data = post(auth_client, {"steps": [{"date": "2026-07-18", "count": 8000}]}).json()
        assert data["days"] == {"weight": 0, "steps": 1, "sleep": 0, "nutrition": 0}
        assert data["sections_handled"] == ["steps"]

    def test_unknown_sections_reported_not_fatal(self, auth_client):
        data = post(auth_client, {
            "steps": [{"date": "2026-07-18", "count": 8000}],
            "heart_rate": [{"date": "2026-07-18", "bpm": 60}],
        }).json()
        assert data["ignored"] == ["heart_rate"]
        assert data["days"]["steps"] == 1

    def test_bad_item_warns_and_skips_rest(self, auth_client):
        data = post(auth_client, {"weight": [
            {"date": "2026-07-18"},              # no value → warn + skip
            {"date": "2026-07-19", "kg": 82.0},  # good → kept
        ]}).json()
        assert data["days"]["weight"] == 1
        assert len(data["warnings"]) == 1
        db = TestingSession()
        assert db.query(WeightLog).count() == 1
        db.close()


class TestSyncStatus:
    """
    GET /api/health/sync-status — the honesty check on the whole pipeline.

    A PWA can't read HealthKit, so the app can only tell the user whether
    their phone is actually pushing by reporting how old each metric is.
    Two things must hold: it reports per-metric (not one opaque flag), and
    freshness counts real readings only.
    """

    def test_never_synced_shape(self, auth_client):
        s = auth_client.get("/api/health/sync-status").json()
        assert s["last_ingest"] is None
        assert s["has_any_data"] is False
        assert s["stalest_days"] is None
        for metric in ("weight", "steps", "sleep", "nutrition"):
            assert s[metric] == {"last_date": None, "days_stale": None}

    def test_requires_auth(self, client):
        assert client.get("/api/health/sync-status").status_code == 401

    def test_reflects_a_shortcut_push(self, auth_client):
        today = date.today().isoformat()
        post(auth_client, {
            "weight": [{"date": today, "kg": 82.4}],
            "steps": [{"date": today, "count": 11205}],
        })
        s = auth_client.get("/api/health/sync-status").json()
        assert s["weight"] == {"last_date": today, "days_stale": 0}
        assert s["steps"] == {"last_date": today, "days_stale": 0}
        # Nothing posted sleep or nutrition — they stay unknown, not "fresh"
        assert s["sleep"]["last_date"] is None
        assert s["has_any_data"] is True
        assert s["last_ingest"] is not None

    def test_stalest_days_is_the_worst_metric(self, auth_client):
        today = date.today()
        post(auth_client, {
            "weight": [{"date": today.isoformat(), "kg": 82.4}],
            "steps": [{"date": (today - timedelta(days=4)).isoformat(), "count": 9000}],
        })
        s = auth_client.get("/api/health/sync-status").json()
        assert s["weight"]["days_stale"] == 0
        assert s["steps"]["days_stale"] == 4
        assert s["stalest_days"] == 4

    def test_derived_rows_do_not_count_as_fresh(self, auth_client):
        """
        An interpolated or demo row must never make the app claim the data is
        current — that is exactly the "it looks synced but it's made up"
        failure this endpoint exists to prevent.
        """
        today = date.today().isoformat()
        auth_client.post("/api/health/weight",
                         json={"date": today, "weight_kg": 80.0, "source": "estimated"})
        s = auth_client.get("/api/health/sync-status").json()
        assert s["weight"] == {"last_date": None, "days_stale": None}
        assert s["has_any_data"] is False

    def test_manual_entries_count_as_real(self, auth_client):
        today = date.today().isoformat()
        auth_client.post("/api/health/weight", json={"date": today, "weight_kg": 80.0})
        s = auth_client.get("/api/health/sync-status").json()
        assert s["weight"] == {"last_date": today, "days_stale": 0}


class TestIngestTokenRotation:
    """
    The ingest token is a long-lived bearer credential pasted into a Shortcut,
    so it travels further than a session does. Rotation is the only way to
    revoke one without disabling the account.
    """

    def test_rotation_issues_a_new_token(self, auth_client):
        before = auth_client.get("/api/auth/me").json()["ingest_token"]
        rotated = auth_client.post("/api/auth/ingest-token/rotate").json()["ingest_token"]
        assert rotated != before
        assert auth_client.get("/api/auth/me").json()["ingest_token"] == rotated

    def test_old_token_stops_working(self, auth_client):
        stale = ingest_headers(auth_client)
        auth_client.post("/api/auth/ingest-token/rotate")

        body = {"steps": [{"date": date.today().isoformat(), "count": 8000}]}
        assert auth_client.post("/api/ingest/health/shortcut",
                                json=body, headers=stale).status_code == 401
        # ...and the fresh one does
        assert auth_client.post("/api/ingest/health/shortcut",
                                json=body,
                                headers=ingest_headers(auth_client)).status_code == 200

    def test_requires_auth(self, client):
        assert client.post("/api/auth/ingest-token/rotate").status_code == 401
