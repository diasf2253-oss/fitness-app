"""Workout generator — split arrangement, volume/priority logic, and apply."""
import os
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_DB_URL = "sqlite:///:memory:"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["APP_TOKEN"] = "testtoken"

from app.db import Base, get_db
from app.generator import arrange, generate, is_compound
from app.main import app
from app.models import Exercise, Routine
from app.muscles import DEFAULT_VOLUME_TARGETS

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


def ex(i, name):
    return SimpleNamespace(id=i, name=name)


# A pool with a couple of exercises per group (compound + isolation).
POOLS = {
    "Chest": [ex(1, "Barbell Bench Press"), ex(2, "Cable Fly"), ex(3, "Incline Dumbbell Press")],
    "Back": [ex(4, "Barbell Row"), ex(5, "Lat Pulldown"), ex(6, "Deadlift")],
    "Shoulders": [ex(7, "Overhead Press"), ex(8, "Lateral Raise")],
    "Biceps": [ex(9, "Barbell Curl"), ex(10, "Cable Curl")],
    "Triceps": [ex(11, "Tricep Pushdown"), ex(12, "Close-Grip Bench Press")],
    "Quads": [ex(13, "Barbell Squat"), ex(14, "Leg Extension")],
    "Hamstrings": [ex(15, "Romanian Deadlift"), ex(16, "Leg Curl")],
    "Glutes": [ex(17, "Hip Thrust"), ex(18, "Cable Pull-Through")],
    "Calves": [ex(19, "Standing Calf Raise"), ex(20, "Seated Calf Raise")],
    "Abs": [ex(21, "Cable Crunch"), ex(22, "Hanging Leg Raise")],
}


def gen(priority, days, split):
    return generate(
        priority=priority, days_per_week=days, split_type=split,
        targets=DEFAULT_VOLUME_TARGETS, exercises_by_group=POOLS,
    )


# ---------------------------------------------------------------------------
# Split arrangement
# ---------------------------------------------------------------------------

def test_arrange_from_frequency_and_split():
    assert arrange("ppl", 6) == ["Push", "Pull", "Legs", "Push", "Pull", "Legs"]
    assert arrange("upper_lower", 4) == ["Upper", "Lower", "Upper", "Lower"]
    assert arrange("full_body", 3) == ["Full Body"] * 3
    assert arrange("bro", 3) == ["Chest", "Back", "Shoulders"]


def test_is_compound():
    assert is_compound("Barbell Bench Press")
    assert is_compound("Romanian Deadlift")
    assert not is_compound("Cable Fly")
    assert not is_compound("Lateral Raise")


# ---------------------------------------------------------------------------
# Volume + priority logic
# ---------------------------------------------------------------------------

def test_priority_tops_range_and_leads_day():
    prog = gen(["Chest", "Back"], 6, "ppl")
    assert prog.weekly_sets["Chest"] == DEFAULT_VOLUME_TARGETS["Chest"][1]   # 20
    assert prog.weekly_sets["Back"] == DEFAULT_VOLUME_TARGETS["Back"][1]     # 22
    push = next(r for r in prog.routines if r.day_type == "Push")
    pull = next(r for r in prog.routines if r.day_type == "Pull")
    assert push.exercises[0].muscle_group == "Chest"     # priority placed first
    assert pull.exercises[0].muscle_group == "Back"


def test_non_priority_uses_middle_never_below_min():
    prog = gen([], 6, "ppl")
    for m, sets in prog.weekly_sets.items():
        low, high = DEFAULT_VOLUME_TARGETS[m]
        assert sets >= low                       # never below minimum effective volume
        assert abs(sets - round((low + high) / 2)) <= 2   # ~middle of the range


def test_compounds_first_with_sensible_reps():
    prog = gen(["Chest"], 4, "ppl")
    push = next(r for r in prog.routines if r.day_type == "Push")
    chest = [e for e in push.exercises if e.muscle_group == "Chest"]
    assert chest[0].is_compound and (chest[0].rep_low, chest[0].rep_high) == (6, 10)
    fly = next((e for e in chest if e.name == "Cable Fly"), None)
    if fly:
        assert (fly.rep_low, fly.rep_high) == (10, 15)


def test_priority_not_in_split_is_flagged():
    prog = gen(["Quads"], 3, "bro")          # legs day not reached at 3 days
    assert prog.weekly_sets.get("Quads", 0) == 0
    assert any("Quads" in n and "priority" in n for n in prog.notes)


def test_too_few_tagged_exercises_flagged():
    prog = generate(
        priority=["Chest"], days_per_week=1, split_type="bro",
        targets=DEFAULT_VOLUME_TARGETS, exercises_by_group={"Chest": [ex(1, "Bench Press")]},
    )
    assert prog.weekly_sets["Chest"] == 20
    assert any("Only 1 exercise" in n and "Chest" in n for n in prog.notes)


def test_weekly_sets_match_distributed_routine_sets():
    prog = gen(["Chest"], 6, "ppl")
    # Chest is trained on the 2 Push days; summing its per-day sets across the
    # week (2 Push sessions) must equal the reported weekly total.
    push = next(r for r in prog.routines if r.day_type == "Push")
    per_day = sum(e.sets for e in push.exercises if e.muscle_group == "Chest")
    assert per_day * prog.arrangement.count("Push") == prog.weekly_sets["Chest"]


# ---------------------------------------------------------------------------
# Apply — persists, replacing only generated routines
# ---------------------------------------------------------------------------

@pytest.fixture
def db_with_exercises():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSession()
    for grp, items in POOLS.items():
        for e in items:
            db.add(Exercise(name=e.name, primary_muscle_group=grp, is_custom=True))
    db.add(Routine(name="My Upper", source="manual"))   # hand-made, must survive
    db.commit()
    db.close()
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


def test_apply_creates_and_replaces_only_generated(db_with_exercises):
    body = {"priority_muscles": ["Chest"], "days_per_week": 3, "split_type": "ppl"}

    first = client.post("/api/generator/apply", json=body, headers=AUTH).json()
    assert first["replaced"] == 0
    assert len(first["routines"]) == 3                  # Push / Pull / Legs

    routines = client.get("/api/routines", headers=AUTH).json()
    assert "My Upper" in [r["name"] for r in routines]
    assert sum(1 for r in routines if r["source"] == "generated") == 3

    # Re-applying replaces the generated set, never the manual routine
    second = client.post("/api/generator/apply", json=body, headers=AUTH).json()
    assert second["replaced"] == 3
    routines2 = client.get("/api/routines", headers=AUTH).json()
    assert sum(1 for r in routines2 if r["source"] == "generated") == 3
    assert "My Upper" in [r["name"] for r in routines2]


def test_apply_rejects_bad_split(db_with_exercises):
    r = client.post("/api/generator/apply",
                    json={"priority_muscles": [], "days_per_week": 3, "split_type": "nope"},
                    headers=AUTH)
    assert r.status_code == 422
