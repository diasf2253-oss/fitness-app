"""Adaptive calorie engine — anchored weekly-trend step model (pure functions)."""
from datetime import date, timedelta

from app.calorie_adapt import (
    adapt_target, carbs_from_target, estimate_maintenance, iso_week_start,
)

# Mondays. TODAY is a Tuesday, so its week (Jun 22) is the in-progress one;
# Jun 8 and Jun 15 are completed weeks.
JUN1, JUN8, JUN15 = date(2026, 6, 1), date(2026, 6, 8), date(2026, 6, 15)
TODAY = date(2026, 6, 23)


def wk(monday, *weights):
    """Daily entries for consecutive days from the given Monday."""
    return {monday + timedelta(days=i): w for i, w in enumerate(weights)}


def run(weight_by_date, *, current=2300, last_week=None, target_loss=0.5,
        step=100, tol=0.15, floor=1800, ceiling=None, today=TODAY):
    return adapt_target(
        current_target=current, target_loss_kg_per_week=target_loss,
        step_kcal=step, tolerance_kg=tol, floor=floor, ceiling=ceiling,
        weight_by_date=weight_by_date, today=today, last_adapted_week=last_week,
    )


def test_losing_faster_than_target_increases():
    # Jun 8 avg 80.0 → Jun 15 avg 79.2 = −0.8 kg/wk, faster than −0.5 target
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.1, 79.2, 79.3)}
    r = run(w)
    assert r.due and r.reason == "increase"
    assert r.target == 2400 and r.changed
    assert r.actual_change_kg == -0.8


def test_losing_slower_decreases():
    # −0.2 kg/wk, slower than target (and outside the band) → eat less
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.7, 79.8, 79.9)}
    r = run(w)
    assert r.reason == "decrease" and r.target == 2200


def test_gaining_decreases():
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 80.4, 80.5, 80.6)}
    r = run(w)
    assert r.reason == "decrease" and r.target == 2200


def test_within_tolerance_holds():
    # −0.5 kg/wk, exactly on target → hold
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.4, 79.5, 79.6)}
    r = run(w)
    assert r.due and r.reason == "hold"
    assert r.target == 2300 and not r.changed


def test_fewer_than_three_entries_holds():
    # Big loss, but only two weigh-ins in the completed week → must not move
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.0, 79.1)}
    r = run(w)
    assert r.reason == "insufficient_data"
    assert r.target == 2300 and not r.changed
    assert r.entries_completed_week == 2


def test_needs_two_consecutive_completed_weeks():
    # Only one completed week of data
    r = run({**wk(JUN15, 79.1, 79.2, 79.3)})
    assert r.reason == "insufficient_data" and not r.changed
    # Non-consecutive completed weeks (Jun 8 week missing) also can't compare
    w = {**wk(JUN1, 80.4, 80.5, 80.6), **wk(JUN15, 79.1, 79.2, 79.3)}
    assert run(w).reason == "insufficient_data"


def test_floor_is_respected():
    # A decrease that would dip under the floor is clamped to it
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.7, 79.8, 79.9)}
    r = run(w, current=1850, floor=1800)
    assert r.target == 1800            # 1850 − 100 = 1750 → clamped up to floor


def test_ceiling_is_respected():
    # An increase that would exceed estimated maintenance is clamped to it
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.1, 79.2, 79.3)}
    r = run(w, current=2900, ceiling=2950)
    assert r.target == 2950            # 2900 + 100 = 3000 → clamped to ceiling


def test_once_per_week_guard():
    w = {**wk(JUN8, 79.9, 80.0, 80.1), **wk(JUN15, 79.1, 79.2, 79.3)}
    r = run(w, last_week=iso_week_start(TODAY))   # already adapted this week
    assert r.reason == "not_due" and not r.due and not r.changed


def test_estimate_maintenance_from_intake_and_trend():
    # Losing 0.02 kg/day at a flat 2500 kcal → maintenance ≈ 2500 + 154
    weights = {TODAY - timedelta(days=i): 80.0 + 0.02 * i for i in range(21)}
    intake = {TODAY - timedelta(days=i): 2500.0 for i in range(21)}
    m = estimate_maintenance(weights, intake, TODAY)
    assert m is not None and abs(m - 2654) < 15


def test_estimate_maintenance_needs_enough_data():
    weights = {TODAY - timedelta(days=i): 80.0 for i in range(5)}
    intake = {TODAY - timedelta(days=i): 2500.0 for i in range(5)}
    assert estimate_maintenance(weights, intake, TODAY) is None


def test_carbs_flex_to_fill_remaining_calories():
    # 2300 − 180·4 − 100·9 = 680 kcal → 170 g carbs
    assert carbs_from_target(2300, 180, 100) == 170
    # Protein + fat already exceed the target → carbs floored at 0, never negative
    assert carbs_from_target(1000, 180, 100) == 0
