"""
Phase 4 tests — calendar markers and day detail.
"""
from datetime import date


class TestCalendar:
    def test_empty_month(self, auth_client):
        r = auth_client.get("/api/calendar/2026/06")
        assert r.status_code == 200
        assert r.json() == {"year": 2026, "month": 6, "days": []}

    def test_invalid_month_rejected(self, auth_client):
        assert auth_client.get("/api/calendar/2026/13").status_code == 422

    def test_markers_for_health_and_workouts(self, auth_client):
        auth_client.post("/api/health/weight",
                         json={"date": "2026-06-03", "weight_kg": 84})
        auth_client.post("/api/health/steps",
                         json={"date": "2026-06-03", "steps": 9000})
        auth_client.post("/api/sessions", json={"name": "Push day"})  # today

        june = auth_client.get("/api/calendar/2026/06").json()["days"]
        by_date = {d["date"]: d for d in june}
        assert by_date["2026-06-03"]["has_weight"] is True
        assert by_date["2026-06-03"]["steps"] == 9000
        assert by_date["2026-06-03"]["sessions"] == 0

        # The session lands "today", which may be a different month than the
        # fixed data above — query today's own month so this isn't June-only.
        today = date.today()
        this_month = auth_client.get(
            f"/api/calendar/{today.year}/{today.month}"
        ).json()["days"]
        by_today = {d["date"]: d for d in this_month}
        assert by_today[today.isoformat()]["sessions"] == 1


class TestDayDetail:
    def test_empty_day(self, auth_client):
        r = auth_client.get("/api/day/2026-06-03")
        assert r.status_code == 200
        data = r.json()
        assert data["sessions"] == []
        assert data["weight_kg"] is None
        assert data["nutrition"] is None

    def test_full_day_aggregation(self, auth_client):
        d = "2026-06-03"
        auth_client.post("/api/health/weight", json={"date": d, "weight_kg": 83.5})
        auth_client.post("/api/health/sleep",
                         json={"date": d, "asleep_minutes": 430, "in_bed_minutes": 465})
        auth_client.post("/api/nutrition",
                         json={"date": d, "calories": 2300, "protein_g": 175,
                               "carbs_g": 230, "fat_g": 78})

        # A workout with one completed set — lands on today, not 2026-06-03
        ex = auth_client.post("/api/exercises",
                              json={"name": "Row", "primary_muscle": "back", "is_custom": True}).json()
        session = auth_client.post("/api/sessions", json={"name": "Pull"}).json()
        se = auth_client.post(f"/api/sessions/{session['id']}/exercises",
                              json={"exercise_id": ex["id"], "position": 0,
                                    "sets": [{"set_number": 1, "weight_kg": 60, "reps": 10}]}).json()
        auth_client.patch(
            f"/api/sessions/{session['id']}/exercises/{se['id']}/sets/{se['sets'][0]['id']}",
            json={"is_completed": True})

        day = auth_client.get(f"/api/day/{d}").json()
        assert day["weight_kg"] == 83.5
        assert day["sleep"]["asleep_minutes"] == 430
        assert day["nutrition"]["calories"] == 2300
        assert day["sessions"] == []  # workout was today, not on d

        today = auth_client.get(f"/api/day/{date.today().isoformat()}").json()
        assert len(today["sessions"]) == 1
        assert today["sessions"][0]["total_volume_kg"] == 600.0
