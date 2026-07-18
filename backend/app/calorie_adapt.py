"""Adaptive calorie target — an anchored, weekly-trend step model.

This intentionally replaces the old from-scratch TDEE inference (which
over-inflated the target). The target is a user-set *anchor* (seeded at
2,300 kcal) that only ever moves by one step from where it currently is —
it is never recomputed from scratch.

Once per completed ISO week (Monday onward) we compare the change in the
weekly-average weight against the signed weekly goal (negative = cut,
0 = maintain, positive = bulk — the Diet goal slider, workbook H1a):

  actual_change = avg(last completed week) − avg(previous completed week)

  • changing faster-downward than goal (beyond the band) → +1 step  (eat more)
  • changing slower / opposite direction (beyond the band) → −1 step  (eat less)
  • within the tolerance band                              → hold

Guardrails: at least ``MIN_ENTRIES_FOR_ADAPT`` weigh-ins in the completed
week (else hold — a single noisy reading must never move the target); a hard
floor; and a ceiling at estimated maintenance. We adapt off the weekly
average only, never single-day weights.

The weekly means come from :func:`weight_trend.weekly_averages` — the single
source of truth shared with the weekly-average chart.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.weight_trend import iso_week_start, weekly_averages

KCAL_PER_KG = 7700.0          # energy density of body-weight change
MIN_ENTRIES_FOR_ADAPT = 3     # weigh-ins required in the completed week
_MAINTENANCE_WINDOW = 21      # days the maintenance estimate is fit over
_MAINTENANCE_MIN_POINTS = 10  # min weight AND intake days for an estimate


@dataclass
class AdaptResult:
    target: int                       # the (possibly unchanged) target
    changed: bool                     # did the target value move?
    due: bool                         # was this a new week we evaluated?
    # 'increase' | 'decrease' | 'hold' | 'insufficient_data' | 'not_due'
    reason: str
    actual_change_kg: float | None    # last completed week − previous week
    entries_completed_week: int | None


def _linreg_slope(points: list[tuple[float, float]]) -> float | None:
    n = len(points)
    if n < 2:
        return None
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    den = sum((x - mx) ** 2 for x, _ in points)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / den


def estimate_maintenance(
    weight_by_date: dict[date, float],
    intake_by_date: dict[date, float],
    today: date,
) -> float | None:
    """Rough maintenance (kcal/day) from intake minus the weight-trend energy,
    used ONLY as the adaptive ceiling — never to set the target. Returns None
    when data is too thin or the fit is implausible."""
    start = today - timedelta(days=_MAINTENANCE_WINDOW)
    intakes = [k for d, k in intake_by_date.items() if start <= d <= today and k and k > 0]
    if len(intakes) < _MAINTENANCE_MIN_POINTS:
        return None
    pts = [((d - start).days, kg) for d, kg in weight_by_date.items() if start <= d <= today]
    if len(pts) < _MAINTENANCE_MIN_POINTS:
        return None
    slope = _linreg_slope(pts)                      # kg/day
    if slope is None:
        return None
    maintenance = sum(intakes) / len(intakes) - slope * KCAL_PER_KG
    if not (1200.0 <= maintenance <= 6000.0):       # reject implausible fits
        return None
    return maintenance


def adapt_target(
    *,
    current_target: int,
    goal_kg_per_week: float,
    step_kcal: int,
    tolerance_kg: float,
    floor: int,
    ceiling: int | None,
    weight_by_date: dict[date, float],
    today: date,
    last_adapted_week: date | None,
) -> AdaptResult:
    """Evaluate the once-per-week adaptation. Pure function — the caller
    persists ``target``/``last_adapted_week`` when ``due``."""
    this_week = iso_week_start(today)

    # Once per ISO week only.
    if last_adapted_week is not None and last_adapted_week >= this_week:
        return AdaptResult(current_target, False, False, "not_due", None, None)

    weeks = weekly_averages(weight_by_date, today)
    completed = [w for w in weeks if not w.is_current_week]

    # insufficient_data does NOT consume the weekly slot (due=False): keep
    # re-checking until there's enough data. A genuine evaluation (increase/
    # decrease/hold) is due=True and marks the week processed.
    def gathering(entries=None) -> AdaptResult:
        return AdaptResult(current_target, False, False, "insufficient_data", None, entries)

    # Need two calendar-consecutive completed weeks to measure a change.
    if len(completed) < 2:
        return gathering()
    last, prev = completed[-1], completed[-2]
    if last.week_start - prev.week_start != timedelta(days=7):
        return gathering(entries=last.n_entries)

    # A single noisy weigh-in must never move the target.
    if last.n_entries < MIN_ENTRIES_FOR_ADAPT:
        return gathering(entries=last.n_entries)

    actual_change = round(last.avg_kg - prev.avg_kg, 3)   # negative = losing
    desired = goal_kg_per_week                            # signed: − cut · 0 maintain · + bulk
    lower, upper = desired - tolerance_kg, desired + tolerance_kg

    if actual_change < lower:           # dropping faster than the goal → eat more
        proposed, reason = current_target + step_kcal, "increase"
    elif actual_change > upper:         # dropping slower / gaining beyond goal → eat less
        proposed, reason = current_target - step_kcal, "decrease"
    else:                               # within band → hold
        proposed, reason = current_target, "hold"

    # Guardrails: never below the floor. The maintenance ceiling only applies
    # when cutting/maintaining — a bulk must be allowed to exceed maintenance.
    proposed = max(floor, proposed)
    if ceiling is not None and goal_kg_per_week <= 0:
        proposed = max(floor, min(ceiling, proposed))
    proposed = int(round(proposed / 10.0) * 10)

    return AdaptResult(
        target=proposed,
        changed=proposed != current_target,
        due=True,
        reason=reason,
        actual_change_kg=actual_change,
        entries_completed_week=last.n_entries,
    )


def carbs_from_target(calorie_target: int, protein_g: int, fat_g: int) -> int:
    """Carbohydrates flex to fill the calories left after fixed protein & fat."""
    grams = (calorie_target - protein_g * 4 - fat_g * 9) / 4
    return max(0, int(round(grams)))
