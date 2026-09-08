"""
Weight interpolation for untracked days.

Covers the estimate endpoint (interpolation / carry-forward / real reading),
the 'estimated' source precedence (a guess never buries a real reading, and a
real reading overwrites a guess), and the estimated fill surfaced by the
dashboard series and the day-detail endpoint.
"""
from datetime import date, timedelta

import pytest

from app.models import WeightLog

from tests.conftest import TestingSession


def log_weight(client, day: str, kg: float, source: str = "manual"):
    return client.post(
        "/api/health/weight",
        json={"date": day, "weight_kg": kg, "source": source},
    )


def estimate(client, day: str):
    return client.get(f"/api/health/weight/estimate?date={day}").json()


class TestEstimateEndpoint:
    def test_midpoint_is_linear_interpolation(self, auth_client):
        log_weight(auth_client, "2026-06-01", 84.0)
        log_weight(auth_client, "2026-06-11", 82.0)          # 10-day span, -2 kg
        r = estimate(auth_client, "2026-06-06")              # halfway → 83.0
        assert r["estimated"] is True
        assert r["method"] == "interpolated"
        assert r["weight_kg"] == pytest.approx(83.0, abs=0.05)

    def test_interpolation_is_distance_weighted(self, auth_client):
        log_weight(auth_client, "2026-06-01", 90.0)
        log_weight(auth_client, "2026-06-11", 80.0)          # -1 kg/day
        r = estimate(auth_client, "2026-06-03")              # 2 days in → 88.0
        assert r["weight_kg"] == pytest.approx(88.0, abs=0.05)

    def test_after_last_reading_carries_forward(self, auth_client):
        log_weight(auth_client, "2026-06-01", 84.0)
        log_weight(auth_client, "2026-06-05", 83.4)
        r = estimate(auth_client, "2026-06-20")              # past the last reading
        assert r["estimated"] is True
        assert r["method"] == "carried_forward"
        assert r["weight_kg"] == pytest.approx(83.4, abs=0.05)

    def test_real_reading_is_returned_as_actual(self, auth_client):
        log_weight(auth_client, "2026-06-01", 84.0)
        r = estimate(auth_client, "2026-06-01")
        assert r["estimated"] is False
        assert r["weight_kg"] == 84.0
        assert r["source"] == "manual"

    def test_no_data_yields_null(self, auth_client):
        r = estimate(auth_client, "2026-06-01")
        assert r["weight_kg"] is None
        assert r["estimated"] is False

    def test_estimates_never_compound(self, auth_client):
        """An estimate must be drawn from real readings, not other estimates."""
        log_weight(auth_client, "2026-06-01", 84.0)
        log_weight(auth_client, "2026-06-11", 82.0)
        # Save an (off) estimate in the middle, then estimate a neighbouring day.
        log_weight(auth_client, "2026-06-06", 99.0, source="estimated")
        r = estimate(auth_client, "2026-06-07")              # ignores the 99.0 estimate
        assert r["weight_kg"] == pytest.approx(82.8, abs=0.1)  # on the 84→82 line


class TestEstimatedSourcePrecedence:
    def test_estimate_does_not_overwrite_manual(self, auth_client):
        log_weight(auth_client, "2026-06-01", 83.0, source="manual")
        log_weight(auth_client, "2026-06-01", 88.0, source="estimated")   # blocked
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 6, 1)).first()
        db.close()
        assert row.weight_kg == 83.0
        assert row.source == "manual"

    def test_real_reading_overwrites_estimate(self, auth_client):
        log_weight(auth_client, "2026-06-01", 88.0, source="estimated")
        log_weight(auth_client, "2026-06-01", 84.0, source="apple_health")   # allowed
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 6, 1)).first()
        db.close()
        assert row.weight_kg == 84.0
        assert row.source == "apple_health"


class TestSurfaced:
    def test_dashboard_fills_gaps_with_flagged_estimates(self, auth_client):
        today = date.today()
        log_weight(auth_client, (today - timedelta(days=4)).isoformat(), 84.0)
        log_weight(auth_client, today.isoformat(), 83.0)
        series = auth_client.get("/api/dashboard").json()["weight"]["series"]
        by_date = {p["date"]: p for p in series}
        # Real readings are not flagged; the days between are filled + flagged.
        assert by_date[today.isoformat()]["estimated"] is False
        gap = (today - timedelta(days=2)).isoformat()
        assert by_date[gap]["estimated"] is True
        assert by_date[gap]["weight_kg"] == pytest.approx(83.5, abs=0.05)

    def test_day_detail_reports_estimate_for_untracked_day(self, auth_client):
        log_weight(auth_client, "2026-06-01", 84.0)
        log_weight(auth_client, "2026-06-05", 83.0)
        r = auth_client.get("/api/day/2026-06-03").json()
        assert r["weight_estimated"] is True
        assert r["weight_kg"] == pytest.approx(83.5, abs=0.05)

    def test_day_detail_real_reading_not_flagged(self, auth_client):
        log_weight(auth_client, "2026-06-03", 84.0)
        r = auth_client.get("/api/day/2026-06-03").json()
        assert r["weight_estimated"] is False
        assert r["weight_kg"] == 84.0


class TestSampleTreatedAsInterpolation:
    """Demo 'sample' data is non-authoritative: it never buries a real reading,
    and where real weigh-ins exist it is replaced by an interpolation of them."""

    def test_sample_day_shows_interpolation_not_its_value(self, auth_client):
        log_weight(auth_client, "2026-06-01", 78.0, source="apple_health")
        log_weight(auth_client, "2026-06-11", 77.0, source="apple_health")
        log_weight(auth_client, "2026-06-06", 84.0, source="sample")   # pollution, empty day
        r = estimate(auth_client, "2026-06-06")
        assert r["estimated"] is True
        assert r["method"] == "interpolated"
        assert r["weight_kg"] == pytest.approx(77.5, abs=0.1)   # midway, not 84

    def test_sample_cannot_overwrite_real_reading(self, auth_client):
        log_weight(auth_client, "2026-06-01", 78.0, source="apple_health")
        log_weight(auth_client, "2026-06-01", 84.0, source="sample")         # blocked
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 6, 1)).first()
        db.close()
        assert row.weight_kg == 78.0
        assert row.source == "apple_health"

    def test_real_reading_overwrites_sample(self, auth_client):
        log_weight(auth_client, "2026-06-01", 84.0, source="sample")
        log_weight(auth_client, "2026-06-01", 78.0, source="apple_health")   # allowed
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 6, 1)).first()
        db.close()
        assert row.weight_kg == 78.0
        assert row.source == "apple_health"

    def test_dashboard_replaces_sample_with_estimate(self, auth_client):
        today = date.today()
        log_weight(auth_client, (today - timedelta(days=4)).isoformat(), 78.0, source="apple_health")
        log_weight(auth_client, today.isoformat(), 77.0, source="apple_health")
        log_weight(auth_client, (today - timedelta(days=2)).isoformat(), 84.0, source="sample")
        series = auth_client.get("/api/dashboard").json()["weight"]["series"]
        by_date = {p["date"]: p for p in series}
        mid = (today - timedelta(days=2)).isoformat()
        assert by_date[mid]["estimated"] is True
        assert by_date[mid]["weight_kg"] == pytest.approx(77.5, abs=0.1)   # not 84

    def test_pure_demo_database_still_shows_sample(self, auth_client):
        """With no real readings at all (seed-only DB), sample must still show
        so the seeder's preview isn't blanked."""
        # Relative dates: the dashboard series is a trailing window, so fixed
        # calendar dates fall out of range as time passes (same reason the
        # sibling dashboard test above uses date.today()).
        today = date.today()
        first = (today - timedelta(days=1)).isoformat()
        log_weight(auth_client, first, 84.0, source="sample")
        log_weight(auth_client, today.isoformat(), 83.6, source="sample")
        r = estimate(auth_client, first)
        assert r["weight_kg"] == 84.0
        assert r["estimated"] is False
        assert r["source"] == "sample"
        series = auth_client.get("/api/dashboard").json()["weight"]["series"]
        assert any(p["weight_kg"] == 84.0 and p["estimated"] is False for p in series)
