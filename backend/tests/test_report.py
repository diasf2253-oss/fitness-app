"""Weekly / biweekly report — section assembly, PR detection, graceful gaps."""
import os
from datetime import date, datetime, time, timedelta

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
from app.models import Exercise, NutritionDay, Session, SessionExercise, Set, SleepLog, WeightLog
from app.report import build_report, report_markdown
from app.weight_trend import iso_week_start

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
TODAY = date.today()


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


def log_set(db, ex, when, weight, reps):
    s = Session(name="W", started_at=datetime.combine(when, time(10)))
    db.add(s); db.flush()
    se = SessionExercise(session_id=s.id, exercise_id=ex.id, position=0)
    db.add(se); db.flush()
    db.add(Set(session_exercise_id=se.id, set_number=1, weight_kg=weight, reps=reps,
               is_completed=True, is_warmup=False))
    db.commit()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

def test_empty_report_does_not_break():
    r = client.get("/api/report?period=weekly", headers=AUTH).json()
    assert r["prs"]["count"] == 0
    assert r["bodyweight"] is None
    assert r["diet"] is None
    assert r["sleep"] is None
    assert r["streak"]["current"] == 0
    assert r["plan"]["calorie_target"]            # plan always present
    md = client.get("/api/report/markdown?period=weekly", headers=AUTH)
    assert md.headers["content-type"].startswith("text/markdown")
    assert "No data for this period" in md.text


def test_invalid_period_rejected():
    assert client.get("/api/report?period=monthly", headers=AUTH).status_code == 422


# ---------------------------------------------------------------------------
# PR detection
# ---------------------------------------------------------------------------

def test_pr_detected_only_when_beating_prior():
    db = TestingSession()
    bench = Exercise(name="Bench", primary_muscle_group="Chest", is_custom=True)
    row = Exercise(name="Row", primary_muscle_group="Back", is_custom=True)
    db.add_all([bench, row]); db.flush()
    # Bench: prior 100x5, in-period 110x5 -> PR
    log_set(db, bench, TODAY - timedelta(days=20), 100, 5)
    log_set(db, bench, TODAY - timedelta(days=2), 110, 5)
    # Row: prior 100x5, in-period 90x5 -> NOT a PR
    log_set(db, row, TODAY - timedelta(days=20), 100, 5)
    log_set(db, row, TODAY - timedelta(days=2), 90, 5)
    db.close()

    items = client.get("/api/report?period=weekly", headers=AUTH).json()["prs"]["items"]
    names = [p["exercise"] for p in items]
    assert "Bench" in names and "Row" not in names
    bench_pr = next(p for p in items if p["exercise"] == "Bench")
    assert bench_pr["previous_best"] is not None and bench_pr["best_set"] == "110 kg × 5"


def test_first_record_is_a_pr():
    db = TestingSession()
    ex = Exercise(name="Squat", primary_muscle_group="Quads", is_custom=True)
    db.add(ex); db.flush()
    log_set(db, ex, TODAY - timedelta(days=1), 140, 3)   # no prior history
    db.close()
    items = client.get("/api/report?period=weekly", headers=AUTH).json()["prs"]["items"]
    assert items[0]["exercise"] == "Squat" and items[0]["previous_best"] is None


# ---------------------------------------------------------------------------
# Diet adherence + bodyweight + sleep
# ---------------------------------------------------------------------------

def test_diet_adherence_pct():
    db = TestingSession()
    # fresh settings: calorie_target 2300, protein 180
    for i, (cal, prot) in enumerate([(2300, 180), (2300, 100), (3000, 200)]):
        db.add(NutritionDay(date=TODAY - timedelta(days=i), calories=cal, protein_g=prot,
                            carbs_g=200, fat_g=70, source="manual"))
    db.commit(); db.close()

    diet = client.get("/api/report?period=weekly", headers=AUTH).json()["diet"]
    assert diet["logged_days"] == 3
    assert diet["calorie_on_target"] == 2      # 2300, 2300 within 10%; 3000 not
    assert diet["protein_on_target"] == 2      # 180, 200 >= 162; 100 not


def test_bodyweight_trend_from_weekly_average():
    db = TestingSession()
    this_mon = iso_week_start(TODAY)
    last_mon = this_mon - timedelta(days=7)
    # last week avg 80.0, this week avg 79.5 -> down 0.5
    for d in (last_mon, last_mon + timedelta(days=1)):
        db.add(WeightLog(date=d, weight_kg=80.0, source="manual"))
    for d in (this_mon, this_mon + timedelta(days=1)):
        db.add(WeightLog(date=d, weight_kg=79.5, source="manual"))
    db.commit(); db.close()

    bw = client.get("/api/report?period=weekly", headers=AUTH).json()["bodyweight"]
    assert bw and bw["change_kg"] == -0.5 and bw["direction"] == "down"


def test_sleep_avg_and_trend():
    db = TestingSession()
    db.add(SleepLog(date=TODAY, asleep_minutes=480, in_bed_minutes=500, source="manual"))   # 8h
    db.add(SleepLog(date=TODAY - timedelta(days=10), asleep_minutes=420, in_bed_minutes=440, source="manual"))  # prior 7h
    db.commit(); db.close()
    sleep = client.get("/api/report?period=weekly", headers=AUTH).json()["sleep"]
    assert sleep["avg_hours"] == 8.0 and sleep["nights"] == 1
    assert sleep["change_h"] == 1.0


def test_markdown_contains_sections():
    md = report_markdown(build_report(TestingSession(), "biweekly"))
    for heading in ["# Biweekly report", "## New PRs", "## Streak", "## Bodyweight trend",
                    "## Diet adherence", "## Sleep", "## Plan for next week"]:
        assert heading in md
