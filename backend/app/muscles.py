"""Muscle-group taxonomy, name-based auto-tagging, and the shared weekly
volume-target table.

Single source of truth for the primary muscle groups and the default weekly
working-set targets that BOTH the sets-per-week analytics (Part 2) and the
workout generator (Part 3) read from.

Global rule: only PRIMARY muscle groups count. Secondary involvement is never
counted in any analytic, set total, or volume calculation.
"""
from __future__ import annotations

# The canonical primary muscle groups. Shoulders is kept as a single group for
# now; splitting it into front / side / rear delts would give finer delt
# volume tracking but is deliberately not done yet.
MUSCLE_GROUPS: list[str] = [
    "Chest", "Back", "Shoulders", "Biceps", "Triceps",
    "Quads", "Hamstrings", "Glutes", "Calves", "Abs",
]

# Default weekly working-set target ranges (working sets / muscle / week).
# Lower bound ≈ minimum effective volume; upper ≈ approaching maximum
# recoverable volume. Editable per-user via AppSettings.volume_targets — this
# table is the fallback/default that the resolver merges overrides onto.
DEFAULT_VOLUME_TARGETS: dict[str, tuple[int, int]] = {
    "Chest": (10, 20),
    "Back": (10, 22),
    "Shoulders": (8, 20),
    "Biceps": (8, 20),
    "Triceps": (8, 18),
    "Quads": (8, 18),
    "Hamstrings": (6, 16),
    "Glutes": (8, 16),
    "Calves": (8, 16),
    "Abs": (6, 20),
}

# Ordered (specific → general) keyword rules for auto-tagging by exercise name.
# The first matching rule wins, so more specific movements are listed first
# (e.g. "leg curl" → Hamstrings is checked before "curl" → Biceps).
_NAME_RULES: list[tuple[tuple[str, ...], str]] = [
    (("calf", "calve"), "Calves"),
    (("hamstring", "leg curl", "lying curl", "romanian", "rdl", "good morning", "nordic"), "Hamstrings"),
    (("glute", "hip thrust", "pull-through", "pull through", "kickback"), "Glutes"),
    (("quad", "squat", "leg press", "leg extension", "lunge", "split squat", "hack", "sissy", "step-up", "step up"), "Quads"),
    (("tricep", "pushdown", "push-down", "skull", "close-grip", "close grip", "jm press", "overhead extension", "dip"), "Triceps"),
    (("bicep", "curl", "chin-up", "chin up", "chinup", "preacher"), "Biceps"),
    (("lateral raise", "side raise", "rear delt", "reverse fly", "reverse flye", "face pull", "overhead press", "shoulder press", "military press", "arnold", "upright row", "delt"), "Shoulders"),
    (("row", "pulldown", "pull-down", "pull-up", "pull up", "pullup", "pullover", "deadlift", "lat ", "back extension", "shrug"), "Back"),
    (("bench", "chest", "fly", "flye", "pec", "push-up", "push up", "pushup", "incline", "decline"), "Chest"),
    (("abs", "ab ", "crunch", "plank", "leg raise", "knee raise", "sit-up", "sit up", "rollout", "hollow", "russian twist", "core", "oblique"), "Abs"),
]

# Fallback mapping from the legacy free-text Exercise.primary_muscle values.
_LEGACY_MAP: dict[str, str] = {
    "chest": "Chest", "back": "Back", "shoulders": "Shoulders",
    "biceps": "Biceps", "triceps": "Triceps", "quads": "Quads",
    "hamstrings": "Hamstrings", "glutes": "Glutes", "calves": "Calves",
    "core": "Abs", "abs": "Abs",
}


def suggest_muscle_group(name: str, legacy_primary: str | None = None) -> str | None:
    """Best-guess primary muscle group from an exercise name, falling back to
    the legacy free-text primary_muscle. Returns None when nothing matches
    (the user can then set it by hand)."""
    n = (name or "").lower()
    for keywords, group in _NAME_RULES:
        if any(k in n for k in keywords):
            return group
    if legacy_primary:
        return _LEGACY_MAP.get(legacy_primary.strip().lower())
    return None


def resolved_volume_targets(overrides: dict | None) -> dict[str, tuple[int, int]]:
    """Default ranges with any per-user overrides merged on top. Unknown
    muscles and malformed ranges in the overrides are ignored."""
    out: dict[str, tuple[int, int]] = dict(DEFAULT_VOLUME_TARGETS)
    if overrides:
        for muscle, rng in overrides.items():
            if muscle in out and isinstance(rng, (list, tuple)) and len(rng) == 2:
                try:
                    out[muscle] = (int(rng[0]), int(rng[1]))
                except (TypeError, ValueError):
                    continue
    return out
