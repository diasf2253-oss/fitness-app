"""
Phase 2 tests:
  - Manual upsert-by-date idempotency (weight/steps/sleep/nutrition)
  - 7-day moving-average calculation
  - /api/dashboard aggregation, both with empty tables and with data
  - Sample-data seeder: idempotent load, surgical clear
"""
from datetime import date, timedelta

from app.models import NutritionDay, WeightLog
from app.routers.dashboard import moving_average_7d

from tests.conftest import TestingSession


# ---------------------------------------------------------------------------
# Manual upsert idempotency
# ---------------------------------------------------------------------------

class TestManualUpserts:
    def test_weight_upsert_updates_not_duplicates(self, auth_client):
        d = "2026-06-01"
        r1 = auth_client.post("/api/health/weight", json={"date": d, "weight_kg": 84.0})
        r2 = auth_client.post("/api/health/weight", json={"date": d, "weight_kg": 83.4})
        assert r1.status_code == 201 and r2.status_code == 201
        assert r2.json()["weight_kg"] == 83.4
        assert r2.json()["source"] == "manual"

        db = TestingSession()
        rows = db.query(WeightLog).all()
        db.close()
        assert len(rows) == 1
        assert rows[0].weight_kg == 83.4

    def test_steps_sleep_nutrition_upserts(self, auth_client):
        d = "2026-06-01"
        auth_client.post("/api/health/steps", json={"date": d, "steps": 9000})
        r = auth_client.post("/api/health/steps", json={"date": d, "steps": 10500})
        assert r.json()["steps"] == 10500

        sleep_body = {"date": d, "asleep_minutes": 420, "in_bed_minutes": 460}
        auth_client.post("/api/health/sleep", json=sleep_body)
        r = auth_client.post("/api/health/sleep", json={**sleep_body, "asleep_minutes": 430})
        assert r.json()["asleep_minutes"] == 430

        nut = {"date": d, "calories": 2200, "protein_g": 170, "carbs_g": 220, "fat_g": 80}
        auth_client.post("/api/nutrition", json=nut)
        r = auth_client.post("/api/nutrition", json={**nut, "calories": 2350})
        assert r.json()["calories"] == 2350

        db = TestingSession()
        assert db.query(NutritionDay).count() == 1
        db.close()

    def test_requires_auth(self, client):
        r = client.post("/api/health/weight", json={"date": "2026-06-01", "weight_kg": 84})
        assert r.status_code == 401
        r = client.get("/api/dashboard")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Moving average
# ---------------------------------------------------------------------------

class TestMovingAverage:
    def test_dense_series(self):
        start = date(2026, 6, 1)
        series = [(start + timedelta(days=i), 80.0 + i) for i in range(10)]
        out = moving_average_7d(series)
        assert len(out) == 10
        # First point: window of one
        assert out[0][1] == 80.0
        # Third point: mean of 80, 81, 82
        assert out[2][1] == 81.0
        # Last point (idx 9): trailing 7 values 83..89 → mean 86
        assert out[9][1] == 86.0

    def test_series_with_gaps_only_averages_window(self):
        d = date(2026, 6, 1)
        series = [
            (d, 80.0),
            (d + timedelta(days=10), 90.0),   # previous reading far outside window
            (d + timedelta(days=12), 94.0),   # window includes day 10 + day 12
        ]
        out = moving_average_7d(series)
        assert out[1][1] == 90.0
        assert out[2][1] == 92.0

    def test_empty_series(self):
        assert moving_average_7d([]) == []


# ---------------------------------------------------------------------------
# Dashboard aggregation
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_empty_tables_render_sensibly(self, auth_client):
        r = auth_client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert data["weight"]["series"] == []
        assert data["weight"]["moving_avg_7d"] == []
        assert data["steps"] == []
        assert data["sleep"] == []
        assert data["nutrition_today"]["logged"] is False
        assert data["nutrition_today"]["calories"] == 0
        # Targets come from the auto-created settings row defaults
        assert data["targets"]["calorie_target"] == 2300
        assert data["targets"]["protein_target_g"] == 180
        assert data["targets"]["fat_max_g"] == 100
        assert data["training"]["week_volume_kg"] == 0
        assert data["training"]["sessions_this_week"] == 0
        assert data["training"]["recent_prs"] == []

    def test_with_data(self, auth_client):
        # Weight series across 10 days + today's nutrition
        today = date.today()
        for i in range(10):
            d = (today - timedelta(days=9 - i)).isoformat()
            auth_client.post("/api/health/weight", json={"date": d, "weight_kg": 84.0 - i * 0.1})
        auth_client.post("/api/health/steps", json={"date": today.isoformat(), "steps": 12000})
        auth_client.post(
            "/api/nutrition",
            json={"date": today.isoformat(), "calories": 2500, "protein_g": 190, "carbs_g": 240, "fat_g": 90},
        )

        data = auth_client.get("/api/dashboard").json()
        assert len(data["weight"]["series"]) == 10
        assert len(data["weight"]["moving_avg_7d"]) == 10
        # Moving average lags the raw series on a downward trend
        assert data["weight"]["moving_avg_7d"][-1]["avg_kg"] > data["weight"]["series"][-1]["weight_kg"]
        assert data["steps"][-1]["steps"] == 12000
        assert data["nutrition_today"]["logged"] is True
        assert data["nutrition_today"]["calories"] == 2500

    def test_training_section_reuses_session_stats(self, auth_client):
        # Build a tiny finished session through the real API
        ex = auth_client.post(
            "/api/exercises",
            json={"name": "Test Press", "primary_muscle": "chest", "is_custom": True},
        ).json()
        session = auth_client.post("/api/sessions", json={"name": "Quick"}).json()
        se = auth_client.post(
            f"/api/sessions/{session['id']}/exercises",
            json={"exercise_id": ex["id"], "position": 0,
                  "sets": [{"set_number": 1, "weight_kg": 100, "reps": 5}]},
        ).json()
        auth_client.patch(
            f"/api/sessions/{session['id']}/exercises/{se['id']}/sets/{se['sets'][0]['id']}",
            json={"is_completed": True},
        )

        data = auth_client.get("/api/dashboard").json()
        assert data["training"]["sessions_this_week"] == 1
        assert data["training"]["week_volume_kg"] == 500.0  # 100 kg × 5
        kinds = {pr["kind"] for pr in data["training"]["recent_prs"]}
        assert "heaviest" in kinds  # first-ever set is automatically a PR


# ---------------------------------------------------------------------------
# Sample-data seeder
# ---------------------------------------------------------------------------

class TestSampleSeeder:
    def test_seed_is_idempotent(self, auth_client):
        r1 = auth_client.post("/api/dev/seed-sample-health")
        assert r1.status_code == 200
        assert r1.json()["days_seeded"] == 30

        db = TestingSession()
        count_after_first = db.query(WeightLog).count()
        db.close()

        auth_client.post("/api/dev/seed-sample-health")
        db = TestingSession()
        count_after_second = db.query(WeightLog).count()
        db.close()
        assert count_after_first == count_after_second == 30

    def test_clear_removes_only_sample_rows(self, auth_client):
        auth_client.post("/api/dev/seed-sample-health")
        # A manual correction on a date inside the seeded range must survive
        manual_date = date.today().isoformat()
        auth_client.post("/api/health/weight", json={"date": manual_date, "weight_kg": 99.9})

        r = auth_client.delete("/api/dev/seed-sample-health")
        assert r.status_code == 200

        db = TestingSession()
        remaining = db.query(WeightLog).all()
        nutrition_left = db.query(NutritionDay).count()
        db.close()
        # Weight: today's row became 'manual' via the correction, so it stays
        assert len(remaining) == 1
        assert remaining[0].weight_kg == 99.9
        assert nutrition_left == 0
