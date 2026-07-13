"""Diet endpoints — adaptive energy, activities CRUD, goal recompute."""
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
from app.models import Activity, NutritionDay, WeightLog

engine = create_engine(
    TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
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


def seed_weight_intake(days=24, intake=2500, micros=None):
    """Weight + nutrition history for the micronutrient / activity tests."""
    db = TestingSession()
    today = date.today()
    for i in range(days):
        d = today - timedelta(days=i)
        db.add(WeightLog(date=d, weight_kg=80.0 + 0.02 * i, source="manual"))
        db.add(NutritionDay(
            date=d, calories=intake, protein_g=180, carbs_g=250, fat_g=80,
            micros=micros or {}, source="manual",
        ))
    db.commit()
    db.close()


def seed_two_weeks(last_avg, prev_avg, entries=4):
    """Two consecutive completed ISO weeks of weigh-ins (weight only, so the
    maintenance-ceiling estimate stays out of the way)."""
    db = TestingSession()
    today = date.today()
    cur_mon = today - timedelta(days=today.weekday())     # this week's Monday
    last_mon, prev_mon = cur_mon - timedelta(days=7), cur_mon - timedelta(days=14)
    for mon, avg in ((prev_mon, prev_avg), (last_mon, last_avg)):
        for i in range(entries):
            db.add(WeightLog(date=mon + timedelta(days=i), weight_kg=avg, source="manual"))
    db.commit()
    db.close()


class TestAdaptiveEnergy:
    def test_gathering_state_uses_anchor(self):
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["adaptive_ready"] is False
        assert e["calorie_target"] == 2300     # the seeded anchor
        assert e["target_loss_kg_per_week"] == 0.5
        assert e["note"]                       # explains it's gathering data
        assert e["carb_target_g"] == 170       # 2300 − 180·4 − 100·9 = 680 → 170 g

    def test_increases_when_losing_too_fast(self):
        seed_two_weeks(last_avg=79.6, prev_avg=80.5)   # −0.9 kg/wk, faster than −0.5
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["adaptive_ready"] is True
        assert e["calorie_target"] == 2400             # +1 step from the anchor
        assert e["weekly_change_kg"] == -0.9
        assert e["entries_last_week"] == 4

    def test_decreases_when_losing_too_slowly(self):
        seed_two_weeks(last_avg=79.8, prev_avg=80.0)   # −0.2 kg/wk, slower than target
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == 2200             # −1 step

    def test_holds_within_tolerance(self):
        seed_two_weeks(last_avg=79.5, prev_avg=80.0)   # −0.5 kg/wk, on target
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == 2300             # unchanged

    def test_holds_when_under_three_entries(self):
        seed_two_weeks(last_avg=79.0, prev_avg=80.5, entries=2)  # big loss, too few
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == 2300             # a noisy week must not move it
        assert e["adaptive_ready"] is False
        assert "Holding" in e["note"]

    def test_never_below_floor(self):
        client.put("/api/settings", json={"calorie_target": 1850}, headers=AUTH)
        seed_two_weeks(last_avg=79.8, prev_avg=80.0)   # decrease would dip under floor
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == e["floor"] == 1800

    def test_adapts_only_once_per_week(self):
        seed_two_weeks(last_avg=79.6, prev_avg=80.5)
        first = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert first["calorie_target"] == 2400
        # a second read the same week must not step again
        second = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert second["calorie_target"] == 2400

    def test_force_recalc_reevaluates(self):
        seed_two_weeks(last_avg=79.6, prev_avg=80.5)
        client.get("/api/diet", headers=AUTH)          # adapts to 2400, marks the week
        e = client.post("/api/diet/recalc", headers=AUTH).json()["energy"]
        assert e["calorie_target"] == 2500             # force ignores the weekly guard

    def test_protein_and_fat_fixed_carbs_flex(self):
        client.put("/api/settings", json={"calorie_target": 2500, "protein_target_g": 200, "fat_max_g": 90}, headers=AUTH)
        e = client.get("/api/diet", headers=AUTH).json()["energy"]
        assert e["protein_target_g"] == 200 and e["fat_target_g"] == 90
        # carbs absorb the remainder: (2500 − 800 − 810)/4 = 222 g
        assert e["carb_target_g"] == 222


class TestNutrientAnalysis:
    def test_breakdown_classifies(self):
        seed_weight_intake(micros={"vitamin_c_mg": 180, "iron_mg": 12, "vitamin_d_mcg": 7.5})
        body = client.get("/api/diet", headers=AUTH).json()
        by = {n["name"]: n for n in body["nutrients"]}
        assert by["vitamin_c"]["status"] == "above"
        assert by["iron"]["status"] == "meets"
        assert by["vitamin_d"]["status"] == "low"
        assert body["nutrient_days"] >= 1


class TestActivities:
    def test_create_list_delete(self):
        seed_weight_intake()  # gives a recent bodyweight for the burn estimate
        today = date.today().isoformat()
        r = client.post("/api/activities", json={"date": today, "type": "Football", "duration_min": 90}, headers=AUTH)
        assert r.status_code == 201
        a = r.json()
        assert a["type"] == "football"          # normalised lower-case
        assert a["calories_est"] > 0

        listing = client.get("/api/activities", headers=AUTH).json()
        assert len(listing) == 1

        assert client.delete(f"/api/activities/{a['id']}", headers=AUTH).status_code == 204
        assert client.get("/api/activities", headers=AUTH).json() == []

    def test_validation_rejects_bad_duration(self):
        r = client.post("/api/activities", json={"date": date.today().isoformat(), "type": "padel", "duration_min": 0}, headers=AUTH)
        assert r.status_code == 422

    def test_delete_missing_404(self):
        assert client.delete("/api/activities/999", headers=AUTH).status_code == 404

    def test_activities_appear_in_diet(self):
        seed_weight_intake()
        client.post("/api/activities", json={"date": date.today().isoformat(), "type": "judo", "duration_min": 60}, headers=AUTH)
        body = client.get("/api/diet", headers=AUTH).json()
        assert len(body["activities"]) == 1
        assert body["activities"][0]["type"] == "judo"
