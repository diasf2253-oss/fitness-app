"""Workout generator — build a structured training program from a split type,
a training frequency, and a set of priority muscles, respecting the shared
per-muscle weekly volume targets.

Pure logic (no DB): the router supplies the resolved volume targets and the
tagged-exercise pools, and persists the result. Only PRIMARY muscle groups
count — secondary involvement is never used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.muscles import MUSCLE_GROUPS

# Which primary muscle groups each split's day-type trains.
SPLITS: dict[str, list[tuple[str, list[str]]]] = {
    "full_body": [("Full Body", list(MUSCLE_GROUPS))],
    "upper_lower": [
        ("Upper", ["Chest", "Back", "Shoulders", "Biceps", "Triceps"]),
        ("Lower", ["Quads", "Hamstrings", "Glutes", "Calves", "Abs"]),
    ],
    "ppl": [
        ("Push", ["Chest", "Shoulders", "Triceps"]),
        ("Pull", ["Back", "Biceps"]),
        ("Legs", ["Quads", "Hamstrings", "Glutes", "Calves", "Abs"]),
    ],
    "bro": [
        ("Chest", ["Chest"]),
        ("Back", ["Back"]),
        ("Shoulders", ["Shoulders"]),
        ("Legs", ["Quads", "Hamstrings", "Glutes", "Calves", "Abs"]),
        ("Arms", ["Biceps", "Triceps"]),
    ],
}
SPLIT_LABELS = {
    "full_body": "Full Body", "upper_lower": "Upper/Lower", "ppl": "PPL", "bro": "Bro split",
}

# Sensible default rep ranges.
COMPOUND_REPS = (6, 10)
ISOLATION_REPS = (10, 15)

MAX_SETS_PER_EXERCISE = 4
MAX_EXERCISES_PER_MUSCLE_PER_DAY = 3

_COMPOUND_KEYWORDS = (
    "squat", "press", "bench", "row", "deadlift", "pulldown", "pull-up", "pull up",
    "pullup", "chin", "dip", "lunge", "thrust", "hack", "leg press", "split squat",
    "push-up", "pushup", "clean", "overhead",
)


def is_compound(name: str) -> bool:
    """Heuristic: multi-joint movements by name keyword; everything else is
    treated as isolation."""
    return any(k in (name or "").lower() for k in _COMPOUND_KEYWORDS)


@dataclass
class GenExercise:
    exercise_id: int
    name: str
    muscle_group: str
    sets: int
    rep_low: int
    rep_high: int
    is_compound: bool


@dataclass
class GenRoutine:
    name: str
    day_type: str
    exercises: list[GenExercise] = field(default_factory=list)


@dataclass
class GenProgram:
    split_type: str
    split_label: str
    days_per_week: int
    arrangement: list[str]                 # weekly sequence of day-type names
    routines: list[GenRoutine]             # one per distinct day-type
    weekly_sets: dict[str, int]            # effective weekly working sets / muscle
    targets: dict[str, tuple[int, int]]
    notes: list[str] = field(default_factory=list)


def arrange(split_type: str, days_per_week: int) -> list[str]:
    """Weekly sequence of day-types, cycling the split to the requested
    frequency (e.g. 6 days + PPL → Push/Pull/Legs/Push/Pull/Legs)."""
    cycle = [name for name, _ in SPLITS[split_type]]
    return [cycle[i % len(cycle)] for i in range(days_per_week)]


def _target_sets(muscle: str, priority: list[str], targets: dict[str, tuple[int, int]]) -> int:
    low, high = targets[muscle]
    if muscle in priority:
        return high                         # priority → top of range (capped at max)
    return max(low, round((low + high) / 2))  # others → middle, never below min


def _split_sets(total: int, n: int) -> list[int]:
    base, rem = divmod(total, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def generate(
    *,
    priority: list[str],
    days_per_week: int,
    split_type: str,
    targets: dict[str, tuple[int, int]],
    exercises_by_group: dict[str, list],   # {muscle: [exercise ORM/obj with .id/.name]}
) -> GenProgram:
    if split_type not in SPLITS:
        raise ValueError(f"unknown split_type {split_type!r}")

    day_specs = dict(SPLITS[split_type])             # day_type -> muscles
    arrangement = arrange(split_type, days_per_week)
    distinct_days = list(dict.fromkeys(arrangement))  # first-appearance order
    day_count = {d: arrangement.count(d) for d in distinct_days}

    # Muscles actually trained given the day-types present in the arrangement.
    trained: list[str] = []
    for d in distinct_days:
        for m in day_specs[d]:
            if m not in trained:
                trained.append(m)

    notes: list[str] = []

    # Priority muscles the split/frequency can't reach at all.
    for m in priority:
        if m not in trained:
            notes.append(
                f"{m} is a priority but isn't trained by a {days_per_week}-day "
                f"{SPLIT_LABELS[split_type]} — add a day or pick another split."
            )

    # Sessions/week each muscle is trained, and its per-session set count.
    sessions_for = {
        m: sum(day_count[d] for d in distinct_days if m in day_specs[d])
        for m in trained
    }
    per_session: dict[str, int] = {}
    weekly_sets: dict[str, int] = {}
    for m in trained:
        s = sessions_for[m]
        per_session[m] = max(1, round(_target_sets(m, priority, targets) / s)) if s else 0
        weekly_sets[m] = per_session[m] * s

    if any(m in priority for m in trained):
        notes.append("Priority muscles set to the top of their target range (capped at the maximum).")

    # Build one routine per distinct day-type.
    routines: list[GenRoutine] = []
    for d in distinct_days:
        # Order muscles: priority (by rank) first, then the rest in split order.
        muscles = day_specs[d]
        ordered = [m for m in priority if m in muscles] + [m for m in muscles if m not in priority]

        routine = GenRoutine(name=f"{SPLIT_LABELS[split_type]} · {d}", day_type=d)
        for m in ordered:
            total = per_session.get(m, 0)
            if total <= 0:
                continue
            pool = exercises_by_group.get(m, [])
            if not pool:
                if f"no-ex-{m}" not in notes:
                    notes.append(f"No exercises tagged for {m} — add some in the library.")
                    notes.append(f"no-ex-{m}")   # de-dupe marker, stripped below
                continue

            want = max(1, math.ceil(total / MAX_SETS_PER_EXERCISE))
            n_ex = min(want, MAX_EXERCISES_PER_MUSCLE_PER_DAY, len(pool))
            if len(pool) < want:
                notes.append(
                    f"Only {len(pool)} exercise(s) tagged for {m}; add more for variety."
                )

            # Compounds first, then isolation; stable by name for determinism.
            pool_sorted = sorted(pool, key=lambda e: (not is_compound(e.name), e.name))
            chosen = pool_sorted[:n_ex]
            for ex, sets in zip(chosen, _split_sets(total, n_ex)):
                comp = is_compound(ex.name)
                lo, hi = COMPOUND_REPS if comp else ISOLATION_REPS
                routine.exercises.append(GenExercise(
                    exercise_id=ex.id, name=ex.name, muscle_group=m,
                    sets=sets, rep_low=lo, rep_high=hi, is_compound=comp,
                ))
        routines.append(routine)

    notes = [n for n in notes if not n.startswith("no-ex-")]   # strip de-dupe markers

    return GenProgram(
        split_type=split_type,
        split_label=SPLIT_LABELS[split_type],
        days_per_week=days_per_week,
        arrangement=arrangement,
        routines=routines,
        weekly_sets=weekly_sets,
        targets=targets,
        notes=notes,
    )
