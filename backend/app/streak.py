"""Training streak — rewards consistent training without punishing rest days.

The streak counts logged workouts; it survives up to ``rest_gap`` rest days
between workouts and only breaks when more than that many consecutive days
pass with no logged workout (default gap 1 → a normal rest day is fine, 2+
empty days in a row breaks it).

Pure logic — the router persists the snapshot onto StreakState, which is
structured so a future points/gamification layer can hook on without
reshaping this computation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class StreakResult:
    current: int                       # length of the live chain (0 if broken)
    longest: int                       # longest chain ever
    last_workout_date: date | None
    alive: bool                        # is the current streak still going?
    at_risk: bool                      # alive, but one more rest day breaks it


def compute_streak(workout_dates, rest_gap: int = 1, today: date | None = None) -> StreakResult:
    """Current and longest streak from the set of dates that had a logged
    workout. Consecutive workouts up to ``rest_gap + 1`` days apart keep the
    chain; a larger gap breaks it."""
    if today is None:
        today = date.today()
    days = sorted(set(workout_dates))
    if not days:
        return StreakResult(0, 0, None, False, False)

    max_apart = rest_gap + 1   # consecutive workouts this many days apart still chain

    # Longest chain anywhere in history.
    longest = chain = 1
    for prev, cur in zip(days, days[1:]):
        chain = chain + 1 if (cur - prev).days <= max_apart else 1
        longest = max(longest, chain)

    # Chain ending at the most recent workout.
    current_chain = 1
    i = len(days) - 1
    while i > 0 and (days[i] - days[i - 1]).days <= max_apart:
        current_chain += 1
        i -= 1

    last = days[-1]
    elapsed = (today - last).days
    alive = elapsed <= max_apart
    return StreakResult(
        current=current_chain if alive else 0,
        longest=longest,
        last_workout_date=last,
        alive=alive,
        at_risk=alive and elapsed == max_apart,
    )
