"""Weekly / biweekly report — section assembly, PR detection, graceful gaps."""
from datetime import date, datetime, time, timedelta

from app.models import Exercise, NutritionDay, Session, SessionExercise, Set, SleepLog, WeightLog
from app.report import build_report, report_markdown
from app.weight_trend import iso_week_start

from tests.conftest import TestingSession

TODAY = date.today()


def log_set(db, user_id, ex, when, weight, reps):
    s = Session(user_id=user_id, name="W", started_at=datetime.combine(when, time(10)))
    db.add(s); db.flush()
    se = SessionExercise(user_id=user_id, session_id=s.id, exercise_id=ex.id, position=0)
    db.add(se); db.flush()
    db.add(Set(user_id=user_id, session_exercise_id=se.id, set_number=1, weight_kg=weight, reps=reps,
               is_completed=True, is_warmup=False))
    db.commit()


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------

def test_empty_report_does_not_break(auth_client):
    r = auth_client.get("/api/report?period=weekly").json()
    assert r["prs"]["count"] == 0
    assert r["bodyweight"] is None
    assert r["diet"] is None
    assert r["sleep"] is None
    assert r["streak"]["current"] == 0
    assert r["plan"]["calorie_target"]            # plan always present
    md = auth_client.get("/api/report/markdown?period=weekly")
    assert md.headers["content-type"].startswith("text/markdown")
    assert "No data for this period" in md.text


def test_invalid_period_rejected(auth_client):
    assert auth_client.get("/api/report?period=monthly").status_code == 422


# ---------------------------------------------------------------------------
# PR detection
# ---------------------------------------------------------------------------

def test_pr_detected_only_when_beating_prior(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    bench = Exercise(user_id=uid, name="Bench", primary_muscle_group="Chest", is_custom=True)
    row = Exercise(user_id=uid, name="Row", primary_muscle_group="Back", is_custom=True)
    db.add_all([bench, row]); db.flush()
    # Bench: prior 100x5, in-period 110x5 -> PR
    log_set(db, uid, bench, TODAY - timedelta(days=20), 100, 5)
    log_set(db, uid, bench, TODAY - timedelta(days=2), 110, 5)
    # Row: prior 100x5, in-period 90x5 -> NOT a PR
    log_set(db, uid, row, TODAY - timedelta(days=20), 100, 5)
    log_set(db, uid, row, TODAY - timedelta(days=2), 90, 5)
    db.close()

    items = auth_client.get("/api/report?period=weekly").json()["prs"]["items"]
    names = [p["exercise"] for p in items]
    assert "Bench" in names and "Row" not in names
    bench_pr = next(p for p in items if p["exercise"] == "Bench")
    assert bench_pr["previous_best"] is not None and bench_pr["best_set"] == "110 kg × 5"


def test_first_record_is_a_pr(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    ex = Exercise(user_id=uid, name="Squat", primary_muscle_group="Quads", is_custom=True)
    db.add(ex); db.flush()
    log_set(db, uid, ex, TODAY - timedelta(days=1), 140, 3)   # no prior history
    db.close()
    items = auth_client.get("/api/report?period=weekly").json()["prs"]["items"]
    assert items[0]["exercise"] == "Squat" and items[0]["previous_best"] is None


# ---------------------------------------------------------------------------
# Diet adherence + bodyweight + sleep
# ---------------------------------------------------------------------------

def test_diet_adherence_pct(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    # fresh settings: calorie_target 2300, protein 180
    for i, (cal, prot) in enumerate([(2300, 180), (2300, 100), (3000, 200)]):
        db.add(NutritionDay(user_id=uid, date=TODAY - timedelta(days=i), calories=cal, protein_g=prot,
                            carbs_g=200, fat_g=70, source="manual"))
    db.commit(); db.close()

    diet = auth_client.get("/api/report?period=weekly").json()["diet"]
    assert diet["logged_days"] == 3
    assert diet["calorie_on_target"] == 2      # 2300, 2300 within 10%; 3000 not
    assert diet["protein_on_target"] == 2      # 180, 200 >= 162; 100 not


def test_bodyweight_trend_from_weekly_average(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    this_mon = iso_week_start(TODAY)
    last_mon = this_mon - timedelta(days=7)
    # last week avg 80.0, this week avg 79.5 -> down 0.5
    for d in (last_mon, last_mon + timedelta(days=1)):
        db.add(WeightLog(user_id=uid, date=d, weight_kg=80.0, source="manual"))
    for d in (this_mon, this_mon + timedelta(days=1)):
        db.add(WeightLog(user_id=uid, date=d, weight_kg=79.5, source="manual"))
    db.commit(); db.close()

    bw = auth_client.get("/api/report?period=weekly").json()["bodyweight"]
    assert bw and bw["change_kg"] == -0.5 and bw["direction"] == "down"


def test_sleep_avg_and_trend(auth_client):
    uid = auth_client.test_user_id
    db = TestingSession()
    db.add(SleepLog(user_id=uid, date=TODAY, asleep_minutes=480, in_bed_minutes=500, source="manual"))   # 8h
    db.add(SleepLog(user_id=uid, date=TODAY - timedelta(days=10), asleep_minutes=420, in_bed_minutes=440, source="manual"))  # prior 7h
    db.commit(); db.close()
    sleep = auth_client.get("/api/report?period=weekly").json()["sleep"]
    assert sleep["avg_hours"] == 8.0 and sleep["nights"] == 1
    assert sleep["change_h"] == 1.0


def test_markdown_contains_sections(auth_client):
    md = report_markdown(build_report(TestingSession(), auth_client.test_user_id, "biweekly"))
    for heading in ["# Biweekly report", "## New PRs", "## Streak", "## Bodyweight trend",
                    "## Diet adherence", "## Sleep", "## Plan for next week"]:
        assert heading in md
