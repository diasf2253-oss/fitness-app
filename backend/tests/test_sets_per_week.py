"""Sets-per-week analytics: completed working sets per primary muscle group,
ISO-week grouping, and the volume-target table."""
from datetime import date, datetime, time, timedelta

from app.models import Exercise, Session, SessionExercise, Set
from app.weight_trend import iso_week_start

from tests.conftest import TestingSession


def make_exercise(db, user_id, name, group):
    ex = Exercise(user_id=user_id, name=name, primary_muscle_group=group, is_custom=True)
    db.add(ex)
    db.flush()
    return ex


def log_session(db, user_id, started_at, blocks):
    """blocks: list of (exercise, [(is_warmup, is_completed), ...])."""
    s = Session(user_id=user_id, name="W", started_at=started_at)
    db.add(s)
    db.flush()
    for pos, (ex, sets) in enumerate(blocks):
        se = SessionExercise(user_id=user_id, session_id=s.id, exercise_id=ex.id, position=pos)
        db.add(se)
        db.flush()
        for i, (warm, comp) in enumerate(sets, 1):
            db.add(Set(
                user_id=user_id, session_exercise_id=se.id, set_number=i,
                weight_kg=50.0, reps=8, is_warmup=warm, is_completed=comp,
            ))
    db.commit()


def current_week(client):
    return [w for w in client.get("/api/stats/sets-per-week?weeks=3").json()["weeks"] if w["is_current"]][0]


def test_counts_only_completed_working_sets(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    bench = make_exercise(db, uid, "My Bench", "Chest")
    row = make_exercise(db, uid, "My Row", "Back")    # secondary biceps must NOT count
    log_session(
        db, uid, datetime.combine(cur_mon, time(10)),
        [
            # warm-up + uncompleted are excluded; 3 real working sets remain
            (bench, [(True, True), (False, True), (False, True), (False, True), (False, False)]),
            (row, [(False, True), (False, True)]),
        ],
    )
    db.close()

    counts = current_week(auth_client)["counts"]
    assert counts["Chest"] == 3      # warm-up & uncompleted set excluded
    assert counts["Back"] == 2
    assert counts["Biceps"] == 0     # "Row" only counts to its primary (Back)


def test_untagged_exercise_does_not_count(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    mystery = make_exercise(db, uid, "Mystery", None)
    log_session(db, uid, datetime.combine(cur_mon, time(10)), [(mystery, [(False, True), (False, True)])])
    db.close()
    assert sum(current_week(auth_client)["counts"].values()) == 0


def test_sets_land_in_their_iso_week(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    cur_mon = iso_week_start(date.today())
    last_mon = cur_mon - timedelta(days=7)
    bench = make_exercise(db, uid, "My Bench", "Chest")
    log_session(db, uid, datetime.combine(last_mon, time(10)), [(bench, [(False, True), (False, True)])])
    db.close()

    weeks = auth_client.get("/api/stats/sets-per-week?weeks=3").json()["weeks"]
    by_start = {w["week_start"]: w for w in weeks}
    assert by_start[last_mon.isoformat()]["counts"]["Chest"] == 2
    assert by_start[cur_mon.isoformat()]["counts"]["Chest"] == 0


def test_volume_targets_defaults_and_override(auth_client):
    base = auth_client.get("/api/stats/volume-targets").json()
    assert base["Chest"] == {"low": 10, "high": 20}

    auth_client.put("/api/settings", json={"volume_targets": {"Chest": [12, 24]}})
    after = auth_client.get("/api/stats/volume-targets").json()
    assert after["Chest"] == {"low": 12, "high": 24}
    assert after["Back"] == {"low": 10, "high": 22}   # untouched muscles keep defaults
    # and the sets-per-week view reflects the override
    targets = auth_client.get("/api/stats/sets-per-week?weeks=1").json()["targets"]
    assert targets["Chest"] == {"low": 12, "high": 24}
