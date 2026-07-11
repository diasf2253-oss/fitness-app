"""Rank ladder — Tiers → Divisions → LP, computed from estimated 1RM relative
to bodyweight against configurable strength standards.

9 tiers ascending (Wood → Olympian), each with 3 divisions (III entry → I top)
and an LP readout (0–100) of where strength sits within the current division.
LP is a direct position readout, not earned through games.

All thresholds, the recent window, and the female multiplier are configurable
(see app.routers.ranks, which merges AppSettings overrides) — nothing here is
immutable.
"""
from __future__ import annotations

TIERS = ["Wood", "Bronze", "Silver", "Gold", "Platinum", "Diamond", "Champion", "Titan", "Olympian"]
DIVISIONS = ["III", "II", "I"]            # III = entry (lowest) → I = top
LEVELS = ["Beginner", "Novice", "Intermediate", "Advanced", "Elite"]

# Wood → Olympian palette (ascending), for the body map + tier badges.
TIER_COLORS = {
    "Wood": "#7c6a52", "Bronze": "#b06b2c", "Silver": "#b8c0c8", "Gold": "#e3b341",
    "Platinum": "#45c2b1", "Diamond": "#54a8e8", "Champion": "#a85cd6",
    "Titan": "#e2556a", "Olympian": "#f4d35e",
}
UNRANKED_COLOR = "#3a423c"

# Legacy MALE strength standards: 1RM ÷ bodyweight at the 5 classic levels.
# Kept because per-user rank_config overrides are keyed by these lifts; the
# body-map ranks themselves use the per-exercise benchmarks below.
STANDARDS: dict[str, list[float]] = {
    "squat": [1.25, 1.50, 1.75, 2.25, 2.75],
    "bench": [0.85, 1.00, 1.25, 1.50, 2.00],
    "deadlift": [1.50, 1.75, 2.00, 2.50, 3.00],
    "ohp": [0.55, 0.65, 0.80, 1.00, 1.30],
}
# Extra body-map regions shown on the anatomy map but not part of the core
# MUSCLE_GROUPS taxonomy (so training analytics/generator are unaffected).
# No exercise is ever tagged with them, so they render as untracked anatomy.
BODY_MAP_EXTRA = ("Forearms", "Adductors")

# --- Per-exercise benchmarks (the body-map rank engine) --------------------
# A body part's rank is the AVERAGE of its exercises' scores, where each score is
# the user's all-time best 1RM ÷ bodyweight measured against THAT exercise's own
# benchmark below. This lets every logged movement count (a heavy row and a heavy
# deadlift both feed Back), instead of one calibrating lift per muscle.
#
# Each benchmark is a reference 1RM ÷ bodyweight for a solid "intermediate" lift.
# Dumbbell / unilateral movements assume the logged weight is PER HAND. Values are
# best-estimate references and are meant to be tuned.
COMMON_ANCHORS = [0.55, 0.78, 1.05, 1.45, 1.95]  # score 1.0 = at the benchmark → high Gold
DEFAULT_BENCHMARK = 1.0

EXERCISE_BENCHMARK: dict[str, float] = {
    # Chest
    "Barbell Bench Press": 1.25, "Incline Barbell Press": 1.05, "Dumbbell Bench Press": 0.48,
    "Incline Dumbbell Press": 0.42, "Cable Fly": 0.42, "Dumbbell Fly": 0.28,
    # Back — machine/cable rows extrapolate heavy, so their references sit higher
    "Barbell Row": 1.20, "Pull-Up": 1.05, "Lat Pulldown": 1.20, "Seated Cable Row": 1.20,
    "Dumbbell Row": 0.55, "Deadlift": 2.00, "T-Bar Row": 1.20,
    # Shoulders
    "Overhead Press (Barbell)": 0.80, "Dumbbell Shoulder Press": 0.34, "Lateral Raise": 0.20,
    "Cable Lateral Raise": 0.18, "Face Pull": 0.45, "Rear Delt Fly": 0.20,
    # Biceps
    "Barbell Curl": 0.55, "Dumbbell Curl": 0.24, "Hammer Curl": 0.26, "Cable Curl": 0.55,
    "Incline Dumbbell Curl": 0.22,
    # Triceps
    "Tricep Pushdown": 0.70, "Overhead Tricep Extension": 0.52, "Close-Grip Bench Press": 1.05,
    "Skull Crusher": 0.58,
    # Quads
    "Barbell Squat": 1.75, "Leg Press": 4.00, "Bulgarian Split Squat": 0.55,
    "Leg Extension": 1.30, "Hack Squat": 2.80,
    # Hamstrings / Glutes
    "Romanian Deadlift": 1.60, "Leg Curl (Lying)": 1.00, "Hip Thrust": 2.50,
    "Cable Pull-Through": 1.10,
    # Calves
    "Standing Calf Raise": 3.50, "Seated Calf Raise": 3.00,
    # Core
    "Cable Crunch": 1.00,
}
# Fallback benchmark per primary muscle group for custom / untabulated
# exercises, expressed for a bilateral BARBELL movement; the equipment factor
# and unilateral halving below adapt it to how the exercise is actually loaded.
GROUP_BENCHMARK: dict[str, float] = {
    "Chest": 1.00, "Back": 1.20, "Shoulders": 0.60, "Biceps": 0.50, "Triceps": 0.65,
    "Quads": 1.75, "Hamstrings": 1.40, "Glutes": 2.20, "Calves": 3.20, "Abs": 0.90,
    "Forearms": 0.55, "Adductors": 1.10,
}
# How the loggable weight compares to a barbell for the same muscle: dumbbells
# are logged per hand, cables read low on the stack, machines extrapolate high.
EQUIPMENT_FACTOR: dict[str, float] = {
    "barbell": 1.00, "machine": 1.20, "cable": 0.75, "dumbbell": 0.42,
    "kettlebell": 0.42, "bodyweight": 1.00,
}
# One limb at a time ⇒ roughly half the bilateral load, minus a stability tax.
UNILATERAL_FACTOR = 0.55
_UNILATERAL_HINTS = (
    "single-arm", "single arm", "one-arm", "one arm", "single-leg", "single leg",
    "one-leg", "one leg", "unilateral", "bulgarian", "split squat", "lunge",
    "step-up", "step up", "pistol",
)


def is_unilateral(name: str) -> bool:
    """Name-based guess that an exercise loads one limb at a time."""
    n = (name or "").lower()
    return any(h in n for h in _UNILATERAL_HINTS)


DEFAULT_FEMALE_MULTIPLIER = 0.65
DEFAULT_WINDOW_WEEKS = 10


def epley_1rm(weight_kg: float, reps: int) -> float:
    """1RM = weight × (1 + reps/30), reps capped at 12 — the same convention as
    the PR system (app.stats), so ranks and PRs never disagree on a 1RM."""
    capped = min(reps, 12)
    if capped <= 1:
        return weight_kg
    return weight_kg * (1 + capped / 30.0)


def tier_lowers(anchors: list[float]) -> list[float]:
    """Lower bound of each of the 9 tiers, mapping the 5 anchors per the spec:
    Wood<Beginner, Bronze=Beginner, Silver=Novice, Gold=mid(Nov,Int),
    Platinum=Intermediate, Diamond=mid(Int,Adv), Champion=Advanced,
    Titan=mid(Adv,Elite), Olympian=Elite."""
    beg, nov, inter, adv, eli = anchors
    return [
        0.0, beg, nov, (nov + inter) / 2, inter,
        (inter + adv) / 2, adv, (adv + eli) / 2, eli,
    ]


def compute_rank(relative_strength: float, anchors: list[float]) -> dict:
    """Map a relative-strength value to tier / division / LP using the anchors."""
    lowers = tier_lowers(anchors)
    ti = 0
    for i, low in enumerate(lowers):
        if relative_strength >= low:
            ti = i

    if ti < 8:
        lo, hi = lowers[ti], lowers[ti + 1]
    else:                                  # Olympian is open-ended: synthetic
        width = lowers[8] - lowers[7]      # band = width of the Titan tier
        lo, hi = lowers[8], lowers[8] + width

    sub = (hi - lo) / 3 if hi > lo else 0.0
    if ti == 8 and relative_strength >= hi:
        div_idx, lp = 2, 100.0             # beyond the top → Olympian I, 100 LP
    elif sub <= 0:
        div_idx, lp = 0, 0.0
    else:
        div_idx = min(2, int((relative_strength - lo) / sub))
        div_lo = lo + div_idx * sub
        lp = max(0.0, min(100.0, (relative_strength - div_lo) / sub * 100))

    tier = TIERS[ti]
    return {
        "tier": tier,
        "tier_index": ti,
        "division": DIVISIONS[div_idx],
        "lp": round(lp),
        "relative_strength": round(relative_strength, 2),
        "color": TIER_COLORS[tier],
    }


def resolve_config(overrides: dict | None) -> dict:
    """Default standards + female multiplier with any per-user overrides merged."""
    cfg = {
        "standards": {k: list(v) for k, v in STANDARDS.items()},
        "female_multiplier": DEFAULT_FEMALE_MULTIPLIER,
        "body_part_agg": "best",            # 'best' | 'average'
    }
    if overrides:
        for lift, vals in (overrides.get("standards") or {}).items():
            if lift in cfg["standards"] and isinstance(vals, (list, tuple)) and len(vals) == 5:
                cfg["standards"][lift] = [float(v) for v in vals]
        if isinstance(overrides.get("female_multiplier"), (int, float)):
            cfg["female_multiplier"] = float(overrides["female_multiplier"])
        if overrides.get("body_part_agg") in ("best", "average"):
            cfg["body_part_agg"] = overrides["body_part_agg"]
    return cfg


def effective_anchors(lift: str, sex: str, cfg: dict) -> list[float]:
    """Standards for a lift, scaled by the female multiplier for sex='female'."""
    base = cfg["standards"][lift]
    if (sex or "male").lower() == "female":
        m = cfg["female_multiplier"]
        return [a * m for a in base]
    return list(base)


def exercise_benchmark(
    name: str, group: str | None, sex: str, cfg: dict, equipment: str | None = None,
) -> float:
    """Reference 1RM ÷ bodyweight for an exercise. Tabulated exercises use their
    own value (already equipment-aware). Unknown/custom exercises start from the
    muscle group's barbell reference, adapted by how they're loaded: the
    equipment factor (dumbbells are per-hand, cables read low, machines high)
    and a unilateral factor when the name says one limb at a time. Scaled by the
    female multiplier so female lifters compare against female references."""
    base = EXERCISE_BENCHMARK.get(name)
    if base is None:
        base = GROUP_BENCHMARK.get(group or "", DEFAULT_BENCHMARK)
        base *= EQUIPMENT_FACTOR.get((equipment or "").lower(), 1.0)
        if is_unilateral(name):
            base *= UNILATERAL_FACTOR
    if (sex or "male").lower() == "female":
        base *= cfg["female_multiplier"]
    return base
