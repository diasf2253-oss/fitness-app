"""
Ready-made training splits.

Each template names its days and the exercises on them, referenced BY NAME and
resolved against whatever the user can actually see (the shared seeded library
plus their own custom exercises). A name that doesn't resolve is skipped rather
than failing the whole build, so a trimmed library still produces a usable split.

Mirrored in frontend/src/local/api/splits.js — the phone builds these offline.
Set counts only; the per-set plan (weight/reps/RIR) is the lifter's to fill in.
"""

# template key -> {name, days: [{name, exercises: [(exercise_name, sets), ...]}]}
SPLIT_TEMPLATES: dict[str, dict] = {
    "ppl": {
        "name": "Push / Pull / Legs",
        "days": [
            {"name": "Push", "exercises": [
                ("Barbell Bench Press", 4), ("Overhead Press (Barbell)", 3),
                ("Incline Dumbbell Press", 3), ("Lateral Raise", 3),
                ("Tricep Pushdown", 3),
            ]},
            {"name": "Pull", "exercises": [
                ("Deadlift", 3), ("Pull-Up", 3), ("Seated Cable Row", 3),
                ("Face Pull", 3), ("Barbell Curl", 3),
            ]},
            {"name": "Legs", "exercises": [
                ("Barbell Squat", 4), ("Romanian Deadlift", 3), ("Leg Press", 3),
                ("Leg Curl (Lying)", 3), ("Standing Calf Raise", 4),
            ]},
        ],
    },
    "bro": {
        "name": "Bro Split",
        "days": [
            {"name": "Chest", "exercises": [
                ("Barbell Bench Press", 4), ("Incline Dumbbell Press", 3),
                ("Cable Fly", 3), ("Dumbbell Fly", 3),
            ]},
            {"name": "Back", "exercises": [
                ("Deadlift", 3), ("Pull-Up", 3), ("Barbell Row", 3),
                ("Lat Pulldown", 3), ("Seated Cable Row", 3),
            ]},
            {"name": "Shoulders", "exercises": [
                ("Overhead Press (Barbell)", 4), ("Lateral Raise", 4),
                ("Rear Delt Fly", 3), ("Face Pull", 3),
            ]},
            {"name": "Arms", "exercises": [
                ("Barbell Curl", 3), ("Incline Dumbbell Curl", 3),
                ("Skull Crusher", 3), ("Tricep Pushdown", 3), ("Hammer Curl", 3),
            ]},
            {"name": "Legs", "exercises": [
                ("Barbell Squat", 4), ("Romanian Deadlift", 3), ("Leg Press", 3),
                ("Leg Extension", 3), ("Standing Calf Raise", 4),
            ]},
        ],
    },
    "legs_glutes": {
        "name": "Legs & Glutes",
        "days": [
            {"name": "Legs & Glutes A", "exercises": [
                ("Barbell Squat", 4), ("Hip Thrust", 4), ("Romanian Deadlift", 3),
                ("Leg Curl (Lying)", 3), ("Standing Calf Raise", 4),
            ]},
            {"name": "Legs & Glutes B", "exercises": [
                ("Hack Squat", 4), ("Cable Pull-Through", 3),
                ("Bulgarian Split Squat", 3), ("Leg Extension", 3),
                ("Seated Calf Raise", 4),
            ]},
        ],
    },
}
