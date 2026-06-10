"""
Phase 3 tests — full Apple Health ingest:
  - Nutrition metrics from Health Auto Export (macros → columns,
    micros → JSON, kJ → kcal conversion, partial-day merges)
  - Manual-beats-apple_health source precedence
  - export.xml / export.zip history backfill (multi-source dedup,
    lb → kg, night attribution, dietary unit normalization)
  - health_last_ingest timestamp
"""
import io
import os
import zipfile
from datetime import date

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
from app.models import NutritionDay, SleepLog, StepsLog, WeightLog

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
    """Fresh tables per test; claim the get_db override, then hand it back."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


def ingest(metrics):
    return client.post(
        "/api/ingest/health",
        json={"data": {"metrics": metrics, "workouts": []}},
        headers=AUTH,
    )


# ---------------------------------------------------------------------------
# Nutrition via the live push
# ---------------------------------------------------------------------------

class TestNutritionIngest:
    def test_macros_and_micros_land_canonically(self):
        r = ingest([
            {"name": "dietary_energy", "units": "kcal",
             "data": [{"date": "2026-06-01", "qty": 2400}]},
            {"name": "protein", "units": "g",
             "data": [{"date": "2026-06-01", "qty": 180}]},
            {"name": "sodium", "units": "mg",
             "data": [{"date": "2026-06-01", "qty": 2300}]},
            {"name": "vitamin_d", "units": "mcg",
             "data": [{"date": "2026-06-01", "qty": 12}]},
        ])
        assert r.status_code == 200
        assert r.json()["rows_upserted"] == 1

        db = TestingSession()
        row = db.query(NutritionDay).first()
        db.close()
        assert row.calories == 2400
        assert row.protein_g == 180
        assert row.source == "apple_health"
        assert row.micros["sodium_mg"] == 2300
        assert row.micros["vitamin_d_ug"] == 12

    def test_kilojoule_conversion(self):
        ingest([{"name": "dietary_energy", "units": "kJ",
                 "data": [{"date": "2026-06-01", "qty": 8368}]}])
        db = TestingSession()
        row = db.query(NutritionDay).first()
        db.close()
        # 8368 kJ × 0.239 ≈ 2000 kcal
        assert row.calories == pytest.approx(2000, abs=2)

    def test_partial_payload_merges_not_zeroes(self):
        ingest([
            {"name": "protein", "units": "g", "data": [{"date": "2026-06-01", "qty": 170}]},
            {"name": "fiber", "units": "g", "data": [{"date": "2026-06-01", "qty": 30}]},
        ])
        # Later push for the same day carries only sodium
        ingest([
            {"name": "sodium", "units": "mg", "data": [{"date": "2026-06-01", "qty": 2500}]},
        ])
        db = TestingSession()
        row = db.query(NutritionDay).first()
        db.close()
        assert row.protein_g == 170            # untouched
        assert row.micros["fiber_g"] == 30     # merged, not replaced
        assert row.micros["sodium_mg"] == 2500

    def test_multiple_points_same_day_sum(self):
        ingest([{"name": "dietary_energy", "units": "kcal",
                 "data": [{"date": "2026-06-01 09:00:00 +0000", "qty": 600},
                          {"date": "2026-06-01 19:00:00 +0000", "qty": 1500}]}])
        db = TestingSession()
        row = db.query(NutritionDay).first()
        db.close()
        assert row.calories == 2100


# ---------------------------------------------------------------------------
# Source precedence: manual corrections survive syncs
# ---------------------------------------------------------------------------

class TestManualWins:
    def test_apple_health_does_not_overwrite_manual_weight(self):
        client.post("/api/health/weight",
                    json={"date": "2026-06-01", "weight_kg": 83.0}, headers=AUTH)
        ingest([{"name": "weight_body_mass", "units": "kg",
                 "data": [{"date": "2026-06-01", "qty": 85.5}]}])
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        assert row.weight_kg == 83.0
        assert row.source == "manual"

    def test_apple_health_does_not_overwrite_manual_nutrition(self):
        client.post("/api/nutrition",
                    json={"date": "2026-06-01", "calories": 2000,
                          "protein_g": 150, "carbs_g": 200, "fat_g": 70},
                    headers=AUTH)
        ingest([{"name": "dietary_energy", "units": "kcal",
                 "data": [{"date": "2026-06-01", "qty": 9999}]}])
        db = TestingSession()
        row = db.query(NutritionDay).first()
        db.close()
        assert row.calories == 2000
        assert row.source == "manual"

    def test_manual_overwrites_apple_health(self):
        ingest([{"name": "weight_body_mass", "units": "kg",
                 "data": [{"date": "2026-06-01", "qty": 85.5}]}])
        client.post("/api/health/weight",
                    json={"date": "2026-06-01", "weight_kg": 83.0}, headers=AUTH)
        db = TestingSession()
        row = db.query(WeightLog).first()
        db.close()
        assert row.weight_kg == 83.0
        assert row.source == "manual"

    def test_last_ingest_timestamp_set(self):
        before = client.get("/api/settings", headers=AUTH).json()
        assert before["health_last_ingest"] is None
        ingest([{"name": "step_count", "units": "count",
                 "data": [{"date": "2026-06-01", "qty": 5000}]}])
        after = client.get("/api/settings", headers=AUTH).json()
        assert after["health_last_ingest"] is not None


# ---------------------------------------------------------------------------
# export.xml backfill
# ---------------------------------------------------------------------------

EXPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="en_US">
 <ExportDate value="2026-06-10 12:00:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" value="8000" startDate="2026-06-01 09:00:00 +0000" endDate="2026-06-01 09:30:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Watch" unit="count" value="6000" startDate="2026-06-01 09:00:00 +0000" endDate="2026-06-01 09:30:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Watch" unit="count" value="3500" startDate="2026-06-01 15:00:00 +0000" endDate="2026-06-01 15:30:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Scale" unit="lb" value="185" startDate="2026-06-01 07:00:00 +0000" endDate="2026-06-01 07:00:00 +0000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisInBed" startDate="2026-06-01 23:05:00 +0000" endDate="2026-06-02 07:00:00 +0000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisAsleepCore" startDate="2026-06-01 23:10:00 +0000" endDate="2026-06-02 03:00:00 +0000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisAsleepREM" startDate="2026-06-02 03:00:00 +0000" endDate="2026-06-02 04:30:00 +0000"/>
 <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisAsleepDeep" startDate="2026-06-02 04:30:00 +0000" endDate="2026-06-02 06:50:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierDietaryEnergyConsumed" sourceName="YAZIO" unit="Cal" value="500" startDate="2026-06-01 09:00:00 +0000" endDate="2026-06-01 09:00:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierDietaryEnergyConsumed" sourceName="YAZIO" unit="Cal" value="1500" startDate="2026-06-01 19:00:00 +0000" endDate="2026-06-01 19:00:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierDietaryProtein" sourceName="YAZIO" unit="g" value="170" startDate="2026-06-01 19:00:00 +0000" endDate="2026-06-01 19:00:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierDietarySodium" sourceName="YAZIO" unit="g" value="2.4" startDate="2026-06-01 19:00:00 +0000" endDate="2026-06-01 19:00:00 +0000"/>
 <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min" value="62" startDate="2026-06-01 09:00:00 +0000" endDate="2026-06-01 09:00:00 +0000"/>
</HealthData>
"""


def upload_export(content: bytes, filename: str):
    return client.post(
        "/api/ingest/health-export",
        files={"file": (filename, io.BytesIO(content), "application/octet-stream")},
        headers=AUTH,
    )


class TestExportBackfill:
    def test_bare_xml_import(self):
        r = upload_export(EXPORT_XML.encode(), "export.xml")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["days"]["steps"] == 1
        assert data["days"]["weight"] == 1
        assert data["days"]["sleep"] == 1
        assert data["days"]["nutrition"] == 1
        assert "HKQuantityTypeIdentifierHeartRate" in data["ignored_types"]

        db = TestingSession()
        steps = db.query(StepsLog).first()
        weight = db.query(WeightLog).first()
        sleep = db.query(SleepLog).first()
        nut = db.query(NutritionDay).first()
        db.close()

        # Watch total (6000+3500=9500) beats iPhone (8000) — no summing across sources
        assert steps.steps == 9500
        # 185 lb → 83.91 kg
        assert weight.weight_kg == pytest.approx(83.91, abs=0.05)
        # Night attributed to the wake date (Jun 2); stages sum correctly
        assert sleep.date == date(2026, 6, 2)
        assert sleep.asleep_minutes == 230 + 90 + 140
        assert sleep.in_bed_minutes == 475
        assert sleep.rem_minutes == 90
        # Dietary: energy summed, sodium g → mg
        assert nut.calories == 2000
        assert nut.protein_g == 170
        assert nut.micros["sodium_mg"] == 2400

    def test_zip_import_and_idempotency(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("apple_health_export/export.xml", EXPORT_XML)
        r1 = upload_export(buf.getvalue(), "export.zip")
        assert r1.status_code == 200
        assert r1.json()["rows_created"] == 4

        r2 = upload_export(buf.getvalue(), "export.zip")
        assert r2.json()["rows_created"] == 0  # idempotent

        db = TestingSession()
        assert db.query(StepsLog).count() == 1
        assert db.query(NutritionDay).count() == 1
        db.close()

    def test_backfill_respects_manual_rows(self):
        client.post("/api/health/weight",
                    json={"date": "2026-06-01", "weight_kg": 80.0}, headers=AUTH)
        upload_export(EXPORT_XML.encode(), "export.xml")
        db = TestingSession()
        row = db.query(WeightLog).filter(WeightLog.date == date(2026, 6, 1)).first()
        db.close()
        assert row.weight_kg == 80.0
        assert row.source == "manual"
