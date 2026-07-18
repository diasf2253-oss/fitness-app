"""Training streak — survives rest days, breaks past the allowed gap."""
import os
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.streak import compute_streak

TEST_DB_URL = "sqlite:///:memory:"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_TOKEN"] = "testtoken"

from app.db import Base, get_db
from app.main import app
from app.models import Activity, Exercise, Session, SessionExercise, Set, StepsLog

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


# ---------------------------------------------------------------------------
# Pure function
# ---------------------------------------------------------------------------

def D(*days):
    return [date(2026, 6, d) for d in days]


def test_empty():
    r = compute_streak([], rest_gap=1, today=date(2026, 6, 26))
    assert r.current == 0 and r.longest == 0 and r.last_workout_date is None


def test_rest_day_keeps_streak():
    # Train every other day — one rest day each gap, gap=1 → all chained
    r = compute_streak(D(20, 22, 24, 26), rest_gap=1, today=date(2026, 6, 26))
    assert r.current == 4 and r.longest == 4 and r.alive and not r.at_risk


def test_two_rest_days_breaks():
    # Jun 20 then Jun 23 = 2 rest days (21, 22) → breaks; current chain is just Jun 23..26
    r = compute_streak(D(20, 23, 24), rest_gap=1, today=date(2026, 6, 25))
    assert r.longest == 2          # 23→24
    assert r.current == 2          # 23,24 with today 25 (1 rest day) still alive
    assert r.alive


def test_broken_when_gap_exceeded_since_last():
    # last workout Jun 23, today Jun 26 → 2 rest days elapsed (24,25) > gap 1 → broken
    r = compute_streak(D(21, 22, 23), rest_gap=1, today=date(2026, 6, 26))
    assert r.alive is False and r.current == 0
    assert r.longest == 3          # the chain still counts toward longest-ever


def test_at_risk_on_last_allowed_day():
    # last workout 2 days ago with gap 1 → 1 rest day elapsed, one more breaks it
    r = compute_streak(D(22, 24), rest_gap=1, today=date(2026, 6, 26))
    assert r.alive and r.at_risk and r.current == 2


def test_configurable_gap_allows_more_rest():
    # 3 days apart needs gap >= 2 to chain
    assert compute_streak(D(20, 23, 26), rest_gap=1, today=date(2026, 6, 26)).longest == 1
    assert compute_streak(D(20, 23, 26), rest_gap=2, today=date(2026, 6, 26)).current == 3


# ---------------------------------------------------------------------------
# Endpoint — counts completed working sets, persists longest, honours config
# ---------------------------------------------------------------------------

def _log_workout(db, d, completed=True, warmup=False):
    ex = db.query(Exercise).first()
    if not ex:
        ex = Exercise(name="Squat", primary_muscle_group="Quads", is_custom=True)
        db.add(ex); db.flush()
    s = Session(name="W", started_at=datetime.combine(d, time(10)))
    db.add(s); db.flush()
    se = SessionExercise(session_id=s.id, exercise_id=ex.id, position=0)
    db.add(se); db.flush()
    db.add(Set(session_exercise_id=se.id, set_number=1, weight_kg=100, reps=5,
               is_completed=completed, is_warmup=warmup))
    db.commit()


def test_endpoint_counts_only_real_workouts():
    db = TestingSession()
    today = date.today()
    # two consecutive workout days (today, yesterday) -> streak 2
    _log_workout(db, today)
    _log_workout(db, today - timedelta(days=1))
    # a session with only a warm-up set must NOT count as a workout day
    _log_workout(db, today - timedelta(days=2), completed=True, warmup=True)
    db.close()

    r = client.get("/api/streak", headers=AUTH).json()
    assert r["current"] == 2 and r["alive"] is True
    assert r["last_workout_date"] == today.isoformat()


def test_longest_is_persisted_monotonic():
    db = TestingSession()
    today = date.today()
    for i in range(4):                       # a 4-long current streak
        _log_workout(db, today - timedelta(days=i))
    db.close()
    assert client.get("/api/streak", headers=AUTH).json()["longest"] == 4

    # Raising the rest-gap config doesn't lower the stored longest-ever
    client.put("/api/settings", json={"streak_rest_gap": 0}, headers=AUTH)
    assert client.get("/api/streak", headers=AUTH).json()["longest"] == 4


# ---------------------------------------------------------------------------
# Active days (T6a): sport sessions and 10k-step days keep the streak alive
# ---------------------------------------------------------------------------

def test_sport_session_keeps_streak_alive():
    db = TestingSession()
    today = date.today()
    _log_workout(db, today)
    _log_workout(db, today - timedelta(days=4))
    # The 2-rest-day hole (days 1-3 back) is bridged by football on days 2 and 3
    db.add(Activity(date=today - timedelta(days=2), type="football", duration_min=90))
    db.add(Activity(date=today - timedelta(days=3), type="judo", duration_min=60))
    db.commit(); db.close()

    r = client.get("/api/streak", headers=AUTH).json()
    assert r["current"] == 4 and r["alive"] is True


def test_10k_step_day_keeps_streak_alive_but_less_does_not():
    db = TestingSession()
    today = date.today()
    _log_workout(db, today)
    _log_workout(db, today - timedelta(days=4))
    db.add(StepsLog(date=today - timedelta(days=2), steps=11500))
    db.add(StepsLog(date=today - timedelta(days=3), steps=4000))   # not active
    db.commit(); db.close()

    r = client.get("/api/streak", headers=AUTH).json()
    # Active: today, -2 (11.5k steps), -4. The 4k day (-3) is NOT active, but
    # each remaining hole is a single rest day, so the chain of 3 holds.
    assert r["current"] == 3


def test_sample_rows_never_count_as_active():
    db = TestingSession()
    today = date.today()
    _log_workout(db, today)
    db.add(Activity(date=today - timedelta(days=2), type="padel",
                    duration_min=60, source="sample"))
    db.add(StepsLog(date=today - timedelta(days=3), steps=20000, source="sample"))
    db.commit(); db.close()

    r = client.get("/api/streak", headers=AUTH).json()
    assert r["current"] == 1
