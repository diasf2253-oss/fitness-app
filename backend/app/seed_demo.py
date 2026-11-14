"""
Demo-data seeder — fills a SEPARATE demo account so every screen has something
to look at while the app is being designed.

    cd backend
    ENABLE_DEV_SEED=true python -m app.seed_demo           # (re)create + fill
    ENABLE_DEV_SEED=true python -m app.seed_demo --reset   # delete the demo account only

Then log in as  demo@example.com  /  demo-password-123  (a local-only throwaway).

Safety rules (they follow CLAUDE.md's "never let invented data render as real"):
  * It only ever touches the demo account. Your real/admin account is never
    read or written — the data lives under its own `user_id`, so deleting the
    demo user removes every trace of it.
  * It refuses to run unless ENABLE_DEV_SEED=true (the same switch the old dev
    endpoint used, off by default) AND the database is local (SQLite or a
    localhost Postgres). It will not run against Railway / production.
  * Re-running first wipes the demo account, so the result is always the same
    (the random generator is seeded) and never piles up duplicates.
"""
import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import delete

from app.auth import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Activity, AppSettings, Base, Exercise, NutritionDay, Routine, RoutineExercise,
    Session, SessionExercise, Set, SleepLog, StepsLog, Tracker, TrackerLog, User,
    WeightLog,
)
from app.muscles import suggest_muscle_group
from app.seed import EXERCISES, ROUTINES

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-123"
DEMO_WEEKS = 12

# Starting working weights (kg) for the lifts the Ranks ladder understands;
# anything else falls back to a modest default.
START_KG = {
    "Barbell Bench Press": 70, "Incline Barbell Press": 55, "Barbell Row": 65,
    "Overhead Press (Barbell)": 42.5, "Barbell Squat": 90, "Romanian Deadlift": 85,
    "Conventional Deadlift": 110, "Pull-Up": 0, "Lat Pulldown": 55,
    "Incline Dumbbell Press": 24, "Dumbbell Bench Press": 28, "Seated Cable Row": 50,
    "Dumbbell Shoulder Press": 20, "Cable Fly": 15, "Rear Delt Fly": 10,
}


def _guard_local_database() -> None:
    """Refuse unless dev-seeding is switched on and the DB is on this machine."""
    if not settings.enable_dev_seed:
        sys.exit("Refusing: set ENABLE_DEV_SEED=true to run the demo seeder "
                 "(it is off by default so it can't run by accident).")
    url = settings.database_url
    if url.startswith("sqlite"):
        return
    host = (urlparse(url).hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        sys.exit(f"Refusing: the database host is '{host}', not this machine. "
                 "The demo seeder only runs against a local database.")


def _wipe_demo_user(db) -> bool:
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if not user:
        return False
    # tracker_log has no user_id of its own — reach it through its trackers
    tracker_ids = [t.id for t in db.query(Tracker.id).filter(Tracker.user_id == user.id)]
    if tracker_ids:
        db.execute(delete(TrackerLog).where(TrackerLog.tracker_id.in_(tracker_ids)))
    # Every other data table carries user_id; delete children before parents.
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in ("users", "tracker_log") or "user_id" not in table.c:
            continue
        db.execute(delete(table).where(table.c.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    return True


def _ensure_library(db) -> dict:
    """Shared exercise library (user_id NULL) — same rows app.seed creates."""
    have = {e.name for e in db.query(Exercise.name).all()}
    for data in EXERCISES:
        if data["name"] not in have:
            group = suggest_muscle_group(data["name"], data["primary_muscle"])
            db.add(Exercise(is_custom=False, primary_muscle_group=group, **data))
    db.flush()
    return {e.name: e.id for e in db.query(Exercise).filter(Exercise.user_id.is_(None))}


def seed_demo() -> None:
    _guard_local_database()
    db = SessionLocal()
    try:
        if _wipe_demo_user(db):
            print("Removed the previous demo account.")
        rng = random.Random(7)  # fixed seed → identical demo every run
        today = date.today()

        user = User(
            email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD),
            name="Demo Lifter", role="user", status="active",
        )
        db.add(user)
        db.flush()
        uid = user.id

        db.add(AppSettings(
            user_id=uid, calorie_target=2300, protein_target_g=170, fat_max_g=80,
            unit_system="metric", sex="male", age=27, height_cm=180.0,
            onboarded=True, goal_kg_per_week=-0.25,
        ))

        # ---- Routines (same templates as app.seed) ----
        ex_id = _ensure_library(db)
        routines = []
        for rname, slots in ROUTINES:
            if rname not in ("Upper A", "Lower A", "Upper B", "Lower B"):
                continue
            r = Routine(name=rname, user_id=uid)
            db.add(r)
            db.flush()
            built = []
            for pos, (ename, sets, lo, hi, rest) in enumerate(slots):
                if ename not in ex_id:
                    continue
                db.add(RoutineExercise(
                    user_id=uid, routine_id=r.id, exercise_id=ex_id[ename], position=pos,
                    target_sets=sets, target_rep_low=lo, target_rep_high=hi, rest_seconds=rest,
                ))
                built.append((ename, sets, lo, hi))
            routines.append((r, built))
        db.flush()

        # ---- Workouts: 12 weeks, ~4 a week, slow progressive overload ----
        # Mon Upper A · Tue Lower A · Thu Upper B · Fri Lower B (some skipped).
        order = {0: 0, 1: 1, 3: 2, 4: 3}
        start = today - timedelta(weeks=DEMO_WEEKS)
        n_sessions = 0
        for offset in range((today - start).days + 1):
            d = start + timedelta(days=offset)
            if d.weekday() not in order or d > today:
                continue
            idx = order[d.weekday()] % len(routines)
            routine, slots = routines[idx]
            if rng.random() < 0.12:        # a missed day, like real life
                continue
            weeks_in = (d - start).days / 7
            begin = datetime(d.year, d.month, d.day, 17, 30) + timedelta(minutes=rng.randint(0, 60))
            sess = Session(
                user_id=uid, name=routine.name, routine_id=routine.id, started_at=begin,
                ended_at=begin + timedelta(minutes=rng.randint(52, 78)),
            )
            db.add(sess)
            db.flush()
            for pos, (ename, n_sets, lo, hi) in enumerate(slots):
                se = SessionExercise(user_id=uid, session_id=sess.id, exercise_id=ex_id[ename], position=pos)
                db.add(se)
                db.flush()
                base = START_KG.get(ename, 30)
                # ~1.3% a week, snapped to the nearest 2.5 kg plate step
                kg = round(base * (1 + 0.013 * weeks_in) / 2.5) * 2.5 if base else 0
                t = begin
                for s in range(n_sets):
                    t += timedelta(minutes=rng.randint(2, 4))
                    reps = max(lo - 1, min(hi, rng.randint(lo, hi) - (1 if s == n_sets - 1 else 0)))
                    db.add(Set(
                        user_id=uid, session_exercise_id=se.id, set_number=s + 1,
                        weight_kg=kg, reps=reps, rir=rng.choice([1, 2, 2, 3]),
                        is_warmup=False, is_completed=True, completed_at=t,
                    ))
            n_sessions += 1

        # ---- Daily health: weight (slow cut), steps, sleep, nutrition ----
        weight = 84.0
        for offset in range(DEMO_WEEKS * 7, -1, -1):
            d = today - timedelta(days=offset)
            weight += rng.uniform(-0.28, 0.18)
            db.add(WeightLog(user_id=uid, date=d, weight_kg=round(weight, 1), source="manual"))
            db.add(StepsLog(
                user_id=uid, date=d, source="manual",
                steps=(10500 if d.weekday() < 5 else 7000) + rng.randint(-3000, 3500),
            ))
            asleep = rng.randint(380, 510)
            deep, rem = int(asleep * rng.uniform(0.13, 0.2)), int(asleep * rng.uniform(0.18, 0.25))
            db.add(SleepLog(
                user_id=uid, date=d, source="manual", asleep_minutes=asleep,
                in_bed_minutes=asleep + rng.randint(15, 50), deep_minutes=deep,
                rem_minutes=rem, core_minutes=asleep - deep - rem,
            ))
            protein = rng.randint(150, 185)
            fat = rng.randint(55, 85)
            carbs = rng.randint(190, 270)
            db.add(NutritionDay(
                user_id=uid, date=d, source="manual", protein_g=protein, fat_g=fat,
                carbs_g=carbs, calories=protein * 4 + carbs * 4 + fat * 9, micros={},
            ))

        # ---- A few sport activities (streak counts these) ----
        for weeks_ago in (1, 3, 5, 8):
            d = today - timedelta(weeks=weeks_ago, days=-rng.randint(1, 2))
            db.add(Activity(user_id=uid, date=d, type="football", duration_min=70, source="manual"))

        # ---- Trackers with a month of entries ----
        mood = Tracker(user_id=uid, name="Mood", kind="scale", position=0)
        meditate = Tracker(user_id=uid, name="Meditate", kind="habit", position=1)
        journal = Tracker(user_id=uid, name="Journal", kind="text", position=2)
        db.add_all([mood, meditate, journal])
        db.flush()
        for offset in range(30):
            d = today - timedelta(days=offset)
            db.add(TrackerLog(tracker_id=mood.id, date=d, value_num=rng.choice([3, 3, 4, 4, 5, 2])))
            if rng.random() < 0.7:
                db.add(TrackerLog(tracker_id=meditate.id, date=d, value_num=1))
        db.add(TrackerLog(tracker_id=journal.id, date=today, value_text="Felt strong on bench today."))

        db.commit()
        print(f"Demo account ready: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  {n_sessions} workouts over {DEMO_WEEKS} weeks, {DEMO_WEEKS * 7 + 1} days of "
              "weight/steps/sleep/nutrition, 4 football sessions, 3 trackers.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill (or remove) the demo account.")
    parser.add_argument("--reset", action="store_true", help="delete the demo account and stop")
    args = parser.parse_args()
    if args.reset:
        _guard_local_database()
        db = SessionLocal()
        try:
            print("Demo account removed." if _wipe_demo_user(db) else "No demo account found.")
        finally:
            db.close()
    else:
        seed_demo()


if __name__ == "__main__":
    main()
