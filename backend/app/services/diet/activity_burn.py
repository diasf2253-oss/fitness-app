"""Informational activity-burn estimate (METs × bodyweight × hours).

This is shown for context only. It deliberately does NOT feed the calorie
target — the adaptive engine already captures activity through the weight
trend, so adding it on top would double-count.
"""
from __future__ import annotations

# METs for the informational burn estimate.
ACTIVITY_METS = {"football": 8.0, "judo": 10.0, "padel": 7.0}
DEFAULT_MET = 6.0


def activity_kcal(activity_type: str, duration_min: int, weight_kg: float) -> float:
    """Informational burn estimate: MET × bodyweight(kg) × hours."""
    met = ACTIVITY_METS.get((activity_type or "").lower(), DEFAULT_MET)
    return round(met * max(weight_kg, 1.0) * (duration_min / 60.0))
