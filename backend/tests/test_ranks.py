"""Rank ladder — tier/division/LP mapping, config, and the endpoint."""
from datetime import date, datetime, time, timedelta

import pytest

from app.models import Exercise, Session, SessionExercise, Set, WeightLog
from app.ranks import (
    COMMON_ANCHORS, STANDARDS, compute_rank, effective_anchors, epley_1rm,
    exercise_benchmark, resolve_config, tier_lowers,
)

from tests.conftest import TestingSession

SQUAT = STANDARDS["squat"]                    # [1.25, 1.50, 1.75, 2.25, 2.75]


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------

def test_epley():
    assert epley_1rm(100, 1) == 100
    assert epley_1rm(100, 5) == pytest.approx(100 * (1 + 5 / 30))
    # Reps cap at 12 — same convention as the PR system, so ranks == PRs.
    assert epley_1rm(100, 20) == epley_1rm(100, 12)


def test_exercise_benchmark_equipment_and_unilateral():
    cfg = resolve_config(None)
    # Tabulated exercises use their own value untouched by equipment factors.
    assert exercise_benchmark("Barbell Squat", "Quads", "male", cfg, "barbell") == 1.75
    # Custom exercises: group fallback × equipment factor (× unilateral factor).
    bb = exercise_benchmark("My Custom Press", "Chest", "male", cfg, "barbell")
    db_ = exercise_benchmark("My Custom DB Press", "Chest", "male", cfg, "dumbbell")
    uni = exercise_benchmark("Single-Arm DB Press", "Chest", "male", cfg, "dumbbell")
    assert db_ == pytest.approx(bb * 0.42)
    assert uni == pytest.approx(db_ * 0.55)
    # Female multiplier scales the reference down.
    f = exercise_benchmark("Barbell Squat", "Quads", "female", cfg, "barbell")
    assert f == pytest.approx(1.75 * cfg["female_multiplier"])


def test_tier_mapping_at_anchors():
    # Each tier starts exactly at its mapped boundary in division III, 0 LP.
    lowers = tier_lowers(SQUAT)
    expected_tiers = ["Wood", "Bronze", "Silver", "Gold", "Platinum",
                      "Diamond", "Champion", "Titan", "Olympian"]
    for i, low in enumerate(lowers):
        r = compute_rank(low + 1e-9, SQUAT)
        assert r["tier"] == expected_tiers[i]
        if i > 0:                              # Wood lower bound is 0 (below beginner)
            assert r["division"] == "III" and r["lp"] == 0


def test_below_beginner_is_wood():
    assert compute_rank(1.0, SQUAT)["tier"] == "Wood"
    assert compute_rank(1.24, SQUAT)["tier"] == "Wood"
    assert compute_rank(1.25, SQUAT)["tier"] == "Bronze"


def test_divisions_climb_within_tier():
    # Bronze band is [1.25, 1.50); thirds → III, II, I
    assert compute_rank(1.25, SQUAT)["division"] == "III"
    assert compute_rank(1.25 + 0.0834, SQUAT)["division"] == "II"
    assert compute_rank(1.25 + 0.1667, SQUAT)["division"] == "I"


def test_lp_is_percent_within_division():
    sub = (1.50 - 1.25) / 3                     # Bronze tier band / 3
    div_I_lo = 1.25 + 2 * sub
    # Midpoint of Bronze division I → ~50 LP
    mid = compute_rank(div_I_lo + sub / 2, SQUAT)
    assert mid["tier"] == "Bronze" and mid["division"] == "I" and abs(mid["lp"] - 50) <= 1
    # Approaching the top of the division → ~100 LP
    assert compute_rank(1.4999, SQUAT)["lp"] >= 99


def test_olympian_is_open_ended():
    assert compute_rank(2.75, SQUAT)["tier"] == "Olympian"
    top = compute_rank(5.0, SQUAT)
    assert top["tier"] == "Olympian" and top["division"] == "I" and top["lp"] == 100


def test_female_standards_scaled_down():
    cfg = resolve_config(None)
    male = effective_anchors("squat", "male", cfg)
    female = effective_anchors("squat", "female", cfg)
    assert female == [a * cfg["female_multiplier"] for a in male]
    # A lift that's Wood for a male can be a higher tier for a female
    assert compute_rank(1.0, female)["tier_index"] > compute_rank(1.0, male)["tier_index"]


def test_config_overrides_standards():
    cfg = resolve_config({"standards": {"squat": [1, 2, 3, 4, 5]}, "female_multiplier": 0.7})
    assert cfg["standards"]["squat"] == [1, 2, 3, 4, 5]
    assert cfg["female_multiplier"] == 0.7
    assert cfg["standards"]["bench"] == STANDARDS["bench"]   # untouched lift keeps default


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def _log(db, user_id, ex, weight, reps, days_ago=1):
    s = Session(user_id=user_id, name="W", started_at=datetime.combine(date.today() - timedelta(days=days_ago), time(10)))
    db.add(s); db.flush()
    se = SessionExercise(user_id=user_id, session_id=s.id, exercise_id=ex.id, position=0)
    db.add(se); db.flush()
    db.add(Set(user_id=user_id, session_exercise_id=se.id, set_number=1, weight_kg=weight, reps=reps,
               is_completed=True, is_warmup=False))
    db.commit()


def test_endpoint_ranks_body_part_from_benchmark(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    squat = Exercise(user_id=uid, name="Barbell Squat", primary_muscle_group="Quads", is_custom=True)
    db.add(squat); db.flush()
    db.add(WeightLog(user_id=uid, date=date.today(), weight_kg=80.0, source="manual"))
    db.commit()
    _log(db, uid, squat, 160, 1)        # 1RM 160, rel 2.0
    db.close()

    r = auth_client.get("/api/ranks").json()
    assert r["bodyweight"] == 80.0
    # Body part = average of its exercises' scores vs each exercise's benchmark.
    # Squat 160 / 80 bw = 2.0×; benchmark 1.75 → score 1.14 → Platinum.
    quads = next(b for b in r["body_parts"] if b["muscle"] == "Quads")
    assert quads["ranked"] and quads["tier"] == "Platinum"
    assert quads["tracked"] is True
    assert quads["n_exercises"] == 1
    assert quads["exercises"][0]["exercise_name"] == "Barbell Squat"
    assert quads["exercises"][0]["best_1rm"] == 160.0
    # A body part with no logged exercise stays unranked (never faked)
    biceps = next(b for b in r["body_parts"] if b["muscle"] == "Biceps")
    assert biceps["ranked"] is False and biceps["n_exercises"] == 0
    # Anatomy-only regions are flagged untracked and can never rank.
    forearms = next(b for b in r["body_parts"] if b["muscle"] == "Forearms")
    assert forearms["tracked"] is False and forearms["ranked"] is False


def test_endpoint_muscle_rank_is_average_of_exercise_scores(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    squat = Exercise(user_id=uid, name="Barbell Squat", primary_muscle_group="Quads", is_custom=True)
    legext = Exercise(user_id=uid, name="Leg Extension", primary_muscle_group="Quads", is_custom=True)
    db.add_all([squat, legext]); db.flush()
    db.add(WeightLog(user_id=uid, date=date.today(), weight_kg=80.0, source="manual"))
    db.commit()
    _log(db, uid, squat, 160, 1)        # score (160/80)/1.75 = 1.1429
    _log(db, uid, legext, 52, 1)        # score (52/80)/1.30  = 0.5000
    db.close()

    r = auth_client.get("/api/ranks").json()
    quads = next(b for b in r["body_parts"] if b["muscle"] == "Quads")
    assert quads["n_exercises"] == 2
    mean = (160 / 80 / 1.75 + 52 / 80 / 1.30) / 2
    assert quads["score"] == pytest.approx(round(mean, 2))
    assert quads["tier"] == compute_rank(mean, COMMON_ANCHORS)["tier"]
    # Exercises are sorted best-first for the drill-down.
    assert quads["exercises"][0]["exercise_name"] == "Barbell Squat"


def test_unranked_without_bodyweight(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    squat = Exercise(user_id=uid, name="Barbell Squat", primary_muscle_group="Quads", is_custom=True)
    db.add(squat); db.flush()
    db.close()
    _logdb = TestingSession()
    _log(_logdb, uid, squat, 160, 1)
    _logdb.close()

    r = auth_client.get("/api/ranks").json()
    assert r["bodyweight"] is None and r["note"]
    assert all(not b["ranked"] for b in r["body_parts"])


def test_bodyweight_ignores_derived_sources(auth_client):
    """Demo ('sample') and interpolated ('estimated') rows must never set the
    bodyweight every rank divides by — only real readings count, even when a
    derived row is more recent."""
    uid = auth_client.test_user_id
    db = TestingSession()
    db.add(WeightLog(user_id=uid, date=date.today() - timedelta(days=3), weight_kg=80.0, source="apple_health"))
    db.add(WeightLog(user_id=uid, date=date.today() - timedelta(days=1), weight_kg=90.0, source="sample"))
    db.add(WeightLog(user_id=uid, date=date.today(), weight_kg=95.0, source="estimated"))
    db.commit()
    db.close()

    r = auth_client.get("/api/ranks").json()
    assert r["bodyweight"] == 80.0

    # With ONLY derived rows there is no bodyweight at all → unranked, honest.
    db = TestingSession()
    db.query(WeightLog).filter(WeightLog.source == "apple_health").delete()
    db.commit()
    db.close()
    r = auth_client.get("/api/ranks").json()
    assert r["bodyweight"] is None
