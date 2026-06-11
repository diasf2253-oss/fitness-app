"""
Seed script — run once after `alembic upgrade head` to populate:
  - ~40 common exercises across all major muscle groups
  - The default settings row (targets: 2400 kcal, 180g protein, 100g fat)
  - 6 routine templates: Upper A/B, Lower A/B, Shoulders & Arms, Custom

Run with:
    cd backend
    source .venv/bin/activate
    python -m app.seed
"""
import sys
import os

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import SessionLocal
from app.models import AppSettings, Exercise, Routine, RoutineExercise


# ---------------------------------------------------------------------------
# Exercise definitions
# ---------------------------------------------------------------------------

EXERCISES = [
    # Chest
    {"name": "Barbell Bench Press",        "primary_muscle": "chest",       "secondary_muscles": ["triceps", "front delts"], "equipment": "barbell"},
    {"name": "Incline Barbell Press",       "primary_muscle": "chest",       "secondary_muscles": ["triceps", "front delts"], "equipment": "barbell"},
    {"name": "Dumbbell Bench Press",        "primary_muscle": "chest",       "secondary_muscles": ["triceps", "front delts"], "equipment": "dumbbell"},
    {"name": "Incline Dumbbell Press",      "primary_muscle": "chest",       "secondary_muscles": ["triceps", "front delts"], "equipment": "dumbbell"},
    {"name": "Cable Fly",                   "primary_muscle": "chest",       "secondary_muscles": [],                         "equipment": "cable"},
    {"name": "Dumbbell Fly",                "primary_muscle": "chest",       "secondary_muscles": [],                         "equipment": "dumbbell"},

    # Back
    {"name": "Barbell Row",                 "primary_muscle": "back",        "secondary_muscles": ["biceps", "rear delts"],   "equipment": "barbell"},
    {"name": "Pull-Up",                     "primary_muscle": "back",        "secondary_muscles": ["biceps"],                 "equipment": "bodyweight"},
    {"name": "Lat Pulldown",                "primary_muscle": "back",        "secondary_muscles": ["biceps"],                 "equipment": "cable"},
    {"name": "Seated Cable Row",            "primary_muscle": "back",        "secondary_muscles": ["biceps"],                 "equipment": "cable"},
    {"name": "Dumbbell Row",                "primary_muscle": "back",        "secondary_muscles": ["biceps"],                 "equipment": "dumbbell"},
    {"name": "Deadlift",                    "primary_muscle": "back",        "secondary_muscles": ["hamstrings", "glutes"],   "equipment": "barbell"},
    {"name": "T-Bar Row",                   "primary_muscle": "back",        "secondary_muscles": ["biceps"],                 "equipment": "machine"},

    # Shoulders
    {"name": "Overhead Press (Barbell)",    "primary_muscle": "shoulders",   "secondary_muscles": ["triceps"],               "equipment": "barbell"},
    {"name": "Dumbbell Shoulder Press",     "primary_muscle": "shoulders",   "secondary_muscles": ["triceps"],               "equipment": "dumbbell"},
    {"name": "Lateral Raise",               "primary_muscle": "shoulders",   "secondary_muscles": [],                        "equipment": "dumbbell"},
    {"name": "Cable Lateral Raise",         "primary_muscle": "shoulders",   "secondary_muscles": [],                        "equipment": "cable"},
    {"name": "Face Pull",                   "primary_muscle": "shoulders",   "secondary_muscles": ["rear delts", "traps"],   "equipment": "cable"},
    {"name": "Rear Delt Fly",               "primary_muscle": "shoulders",   "secondary_muscles": [],                        "equipment": "dumbbell"},

    # Biceps
    {"name": "Barbell Curl",                "primary_muscle": "biceps",      "secondary_muscles": [],                        "equipment": "barbell"},
    {"name": "Dumbbell Curl",               "primary_muscle": "biceps",      "secondary_muscles": [],                        "equipment": "dumbbell"},
    {"name": "Hammer Curl",                 "primary_muscle": "biceps",      "secondary_muscles": ["brachialis"],            "equipment": "dumbbell"},
    {"name": "Cable Curl",                  "primary_muscle": "biceps",      "secondary_muscles": [],                        "equipment": "cable"},
    {"name": "Incline Dumbbell Curl",       "primary_muscle": "biceps",      "secondary_muscles": [],                        "equipment": "dumbbell"},

    # Triceps
    {"name": "Tricep Pushdown",             "primary_muscle": "triceps",     "secondary_muscles": [],                        "equipment": "cable"},
    {"name": "Overhead Tricep Extension",   "primary_muscle": "triceps",     "secondary_muscles": [],                        "equipment": "cable"},
    {"name": "Close-Grip Bench Press",      "primary_muscle": "triceps",     "secondary_muscles": ["chest"],                 "equipment": "barbell"},
    {"name": "Skull Crusher",               "primary_muscle": "triceps",     "secondary_muscles": [],                        "equipment": "barbell"},

    # Quads
    {"name": "Barbell Squat",               "primary_muscle": "quads",       "secondary_muscles": ["glutes", "hamstrings"],  "equipment": "barbell"},
    {"name": "Leg Press",                   "primary_muscle": "quads",       "secondary_muscles": ["glutes"],                "equipment": "machine"},
    {"name": "Bulgarian Split Squat",       "primary_muscle": "quads",       "secondary_muscles": ["glutes"],                "equipment": "dumbbell"},
    {"name": "Leg Extension",               "primary_muscle": "quads",       "secondary_muscles": [],                        "equipment": "machine"},
    {"name": "Hack Squat",                  "primary_muscle": "quads",       "secondary_muscles": ["glutes"],                "equipment": "machine"},

    # Hamstrings / Glutes
    {"name": "Romanian Deadlift",           "primary_muscle": "hamstrings",  "secondary_muscles": ["glutes", "back"],        "equipment": "barbell"},
    {"name": "Leg Curl (Lying)",            "primary_muscle": "hamstrings",  "secondary_muscles": [],                        "equipment": "machine"},
    {"name": "Hip Thrust",                  "primary_muscle": "glutes",      "secondary_muscles": ["hamstrings"],            "equipment": "barbell"},
    {"name": "Cable Pull-Through",          "primary_muscle": "glutes",      "secondary_muscles": ["hamstrings"],            "equipment": "cable"},

    # Calves
    {"name": "Standing Calf Raise",         "primary_muscle": "calves",      "secondary_muscles": [],                        "equipment": "machine"},
    {"name": "Seated Calf Raise",           "primary_muscle": "calves",      "secondary_muscles": [],                        "equipment": "machine"},

    # Core
    {"name": "Plank",                       "primary_muscle": "core",        "secondary_muscles": [],                        "equipment": "bodyweight"},
    {"name": "Cable Crunch",                "primary_muscle": "core",        "secondary_muscles": [],                        "equipment": "cable"},
    {"name": "Hanging Leg Raise",           "primary_muscle": "core",        "secondary_muscles": [],                        "equipment": "bodyweight"},
]


# ---------------------------------------------------------------------------
# Routine templates
# Each entry: (routine_name, [(exercise_name, sets, rep_low, rep_high, rest_s)])
# ---------------------------------------------------------------------------

ROUTINES = [
    ("Upper A", [
        ("Barbell Bench Press",     4, 4,  6,  180),
        ("Barbell Row",             4, 4,  6,  180),
        ("Incline Dumbbell Press",  3, 8,  12, 120),
        ("Lat Pulldown",            3, 8,  12, 120),
        ("Overhead Press (Barbell)",3, 8,  12, 120),
        ("Cable Fly",               3, 12, 15, 90),
    ]),
    ("Upper B", [
        ("Incline Barbell Press",   4, 6,  10, 150),
        ("Pull-Up",                 4, 6,  10, 150),
        ("Dumbbell Bench Press",    3, 10, 15, 90),
        ("Seated Cable Row",        3, 10, 15, 90),
        ("Dumbbell Shoulder Press", 3, 10, 15, 90),
        ("Rear Delt Fly",           3, 15, 20, 60),
    ]),
    ("Lower A", [
        ("Barbell Squat",           4, 4,  6,  180),
        ("Romanian Deadlift",       3, 8,  12, 120),
        ("Leg Press",               3, 10, 15, 90),
        ("Leg Curl (Lying)",        3, 10, 15, 90),
        ("Standing Calf Raise",     4, 12, 20, 60),
    ]),
    ("Lower B", [
        ("Deadlift",                4, 3,  5,  240),
        ("Bulgarian Split Squat",   3, 8,  12, 120),
        ("Hack Squat",              3, 10, 15, 90),
        ("Hip Thrust",              3, 10, 15, 90),
        ("Seated Calf Raise",       4, 12, 20, 60),
    ]),
    ("Shoulders & Arms", [
        ("Overhead Press (Barbell)", 4, 6,  10, 150),
        ("Lateral Raise",            4, 12, 20, 60),
        ("Face Pull",                3, 15, 20, 60),
        ("Barbell Curl",             3, 8,  12, 90),
        ("Hammer Curl",              3, 10, 15, 90),
        ("Tricep Pushdown",          3, 10, 15, 90),
        ("Skull Crusher",            3, 8,  12, 90),
    ]),
    ("Custom", []),  # Empty — user fills this in
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def seed():
    db = SessionLocal()
    try:
        # ---- Settings ----
        if not db.get(AppSettings, 1):
            db.add(AppSettings(
                id=1,
                calorie_target=2400,
                protein_target_g=180,
                fat_max_g=100,
                unit_system="metric",
            ))
            print("Created default settings row")
        else:
            print("Settings row already exists — skipping")

        # ---- Exercises ----
        existing_names = {e.name for e in db.query(Exercise.name).all()}
        new_exercises = []
        for ex_data in EXERCISES:
            if ex_data["name"] not in existing_names:
                new_exercises.append(Exercise(is_custom=False, **ex_data))

        if new_exercises:
            db.add_all(new_exercises)
            db.flush()
            print(f"Seeded {len(new_exercises)} exercises")
        else:
            print("Exercises already seeded — skipping")

        # ---- Routines ----
        # Build a name → Exercise id map for quick lookup
        ex_by_name = {e.name: e.id for e in db.query(Exercise).all()}

        existing_routine_names = {r.name for r in db.query(Routine.name).all()}

        for routine_name, exercise_list in ROUTINES:
            if routine_name in existing_routine_names:
                print(f"Routine '{routine_name}' already exists — skipping")
                continue

            routine = Routine(name=routine_name)
            db.add(routine)
            db.flush()

            for pos, (ex_name, sets, rep_low, rep_high, rest) in enumerate(exercise_list):
                ex_id = ex_by_name.get(ex_name)
                if not ex_id:
                    print(f"  WARNING: exercise '{ex_name}' not found — skipping")
                    continue
                db.add(RoutineExercise(
                    routine_id=routine.id,
                    exercise_id=ex_id,
                    position=pos,
                    target_sets=sets,
                    target_rep_low=rep_low,
                    target_rep_high=rep_high,
                    rest_seconds=rest,
                ))
            print(f"Seeded routine '{routine_name}' with {len(exercise_list)} exercises")

        # ---- Default trackers (Phase 6) ----
        # Only when the table is empty — renames/archives must stick.
        from app.models import Tracker
        if db.query(Tracker).count() == 0:
            db.add(Tracker(name="Mood", kind="scale", position=0))
            db.add(Tracker(name="Journal", kind="text", position=1))
            print("Seeded default trackers: Mood, Journal")
        else:
            print("Trackers already exist — skipping")

        db.commit()
        print("\nSeed complete.")
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
