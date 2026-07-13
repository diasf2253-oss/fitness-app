"""Sets-per-week analytics: completed working sets per primary muscle group,
ISO-week grouping, and the volume-target table."""
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
from app.models import Exercise, Session, SessionExercise, Set
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


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


def make_exercise(db, name, group):
    ex = Exercise(name=name, primary_muscle_group=group, is_custom=True)
    db.add(ex)
    db.flush()
    return ex


def log_session(db, started_at, blocks):
    """blocks: list of (exercise, [(is_warmup, is_completed), ...])."""
    s = Session(name="W", started_at=started_at)
    db.add(s)
    db.flush()
    for pos, (ex, sets) in enumerate(blocks):
        se = SessionExercise(session_id=s.id, exercise_id=ex.id, position=pos)
        db.add(se)
        db.flush()
        for i, (warm, comp) in enumerate(sets, 1):
            db.add(Set(
                session_exercise_id=se.id, set_number=i,
                weight_kg=50.0, reps=8, is_warmup=warm, is_completed=comp,
            ))
    db.commit()


def current_week():
    return [w for w in client.get("/api/stats/sets-per-week?weeks=3", headers=AUTH).json()["weeks"] if w["is_current"]][0]


def test_counts_only_completed_working_sets():
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    bench = make_exercise(db, "My Bench", "Chest")
    row = make_exercise(db, "My Row", "Back")    # secondary biceps must NOT count
    log_session(
        db, datetime.combine(cur_mon, time(10)),
        [
            # warm-up + uncompleted are excluded; 3 real working sets remain
            (bench, [(True, True), (False, True), (False, True), (False, True), (False, False)]),
            (row, [(False, True), (False, True)]),
        ],
    )
    db.close()

    counts = current_week()["counts"]
    assert counts["Chest"] == 3      # warm-up & uncompleted set excluded
    assert counts["Back"] == 2
    assert counts["Biceps"] == 0     # "Row" only counts to its primary (Back)


def test_untagged_exercise_does_not_count():
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    mystery = make_exercise(db, "Mystery", None)
    log_session(db, datetime.combine(cur_mon, time(10)), [(mystery, [(False, True), (False, True)])])
    db.close()
    assert sum(current_week()["counts"].values()) == 0


def test_sets_land_in_their_iso_week():
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    last_mon = cur_mon - timedelta(days=7)
    bench = make_exercise(db, "My Bench", "Chest")
    log_session(db, datetime.combine(last_mon, time(10)), [(bench, [(False, True), (False, True)])])
    db.close()

    weeks = client.get("/api/stats/sets-per-week?weeks=3", headers=AUTH).json()["weeks"]
    by_start = {w["week_start"]: w for w in weeks}
    assert by_start[last_mon.isoformat()]["counts"]["Chest"] == 2
    assert by_start[cur_mon.isoformat()]["counts"]["Chest"] == 0


def test_volume_targets_defaults_and_override():
    base = client.get("/api/stats/volume-targets", headers=AUTH).json()
    assert base["Chest"] == {"low": 10, "high": 20}

    client.put("/api/settings", json={"volume_targets": {"Chest": [12, 24]}}, headers=AUTH)
    after = client.get("/api/stats/volume-targets", headers=AUTH).json()
    assert after["Chest"] == {"low": 12, "high": 24}
    assert after["Back"] == {"low": 10, "high": 22}   # untouched muscles keep defaults
    # and the sets-per-week view reflects the override
    targets = client.get("/api/stats/sets-per-week?weeks=1", headers=AUTH).json()["targets"]
    assert targets["Chest"] == {"low": 12, "high": 24}
