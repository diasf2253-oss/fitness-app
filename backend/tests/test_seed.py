"""
Seeding: a fresh database must come out ranked-ready.

primary_muscle_group (what Ranks and per-muscle volume group by) used to be
filled only by the phase-10 migration's backfill. On a fresh database that
migration runs *before* `python -m app.seed` inserts the library, so every
seeded exercise stayed untagged and Ranks stayed empty forever.
"""
from datetime import date

from app import seed as seed_module
from app.models import Exercise, Session, SessionExercise, Set, WeightLog
from tests.conftest import TestingSession, _make_user


def _run_seed(monkeypatch):
    monkeypatch.setattr(seed_module, "SessionLocal", TestingSession)
    seed_module.seed()


def test_fresh_seed_tags_every_library_exercise(monkeypatch):
    _make_user("admin@example.com", "testpassword123", role="admin")
    _run_seed(monkeypatch)

    db = TestingSession()
    try:
        exercises = db.query(Exercise).all()
        assert len(exercises) == len(seed_module.EXERCISES)
        assert [e.name for e in exercises if e.primary_muscle_group is None] == []
    finally:
        db.close()


def test_seed_repairs_untagged_library_but_leaves_custom_alone(monkeypatch):
    admin_id = _make_user("admin@example.com", "testpassword123", role="admin")
    db = TestingSession()
    db.add(Exercise(name="Barbell Bench Press", primary_muscle="chest", is_custom=False))
    db.add(Exercise(name="My Curl Variation", primary_muscle="biceps",
                    is_custom=True, user_id=admin_id))
    db.commit()
    db.close()

    _run_seed(monkeypatch)

    db = TestingSession()
    try:
        bench = db.query(Exercise).filter_by(name="Barbell Bench Press").one()
        custom = db.query(Exercise).filter_by(name="My Curl Variation").one()
        assert bench.primary_muscle_group == "Chest"
        assert custom.primary_muscle_group is None   # the user's own call
    finally:
        db.close()


def test_logged_lift_ranks_after_fresh_seed(monkeypatch, admin_client):
    _run_seed(monkeypatch)

    uid = admin_client.test_user_id
    db = TestingSession()
    bench = db.query(Exercise).filter_by(name="Barbell Bench Press").one()
    session = Session(user_id=uid, name="Push")
    db.add(session)
    db.flush()
    se = SessionExercise(user_id=uid, session_id=session.id, exercise_id=bench.id, position=0)
    db.add(se)
    db.flush()
    db.add(Set(user_id=uid, session_exercise_id=se.id, set_number=1,
               weight_kg=100, reps=5, is_completed=True))
    db.add(WeightLog(user_id=uid, date=date.today(), weight_kg=80, source="manual"))
    db.commit()
    db.close()

    parts = admin_client.get("/api/ranks").json()["body_parts"]
    chest = next(bp for bp in parts if bp["muscle"] == "Chest")
    assert chest["ranked"] is True
    assert chest["n_exercises"] == 1
