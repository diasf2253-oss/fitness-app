"""Weekly (ISO-week) weight averaging.

The single source of truth for the weekly-average chart (Part 2) and the
adaptive calorie engine (Part 3) — both consume :func:`weekly_averages`.

An ISO week starts on Monday. Only weeks that contain at least one weight
entry are emitted; missing weeks are gaps and are never interpolated. The
week containing ``today`` is flagged provisional, since it is still
accumulating entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def iso_week_start(d: date) -> date:
    """Monday of the ISO week containing ``d``."""
    return d - timedelta(days=d.weekday())


@dataclass(frozen=True)
class WeeklyAverage:
    week_start: date        # Monday of the week
    avg_kg: float           # mean of that week's weigh-ins
    n_entries: int          # how many daily entries fed the mean
    is_current_week: bool   # the in-progress week (provisional)


def weekly_averages(
    weight_by_date: dict[date, float], today: date | None = None
) -> list[WeeklyAverage]:
    """Mean bodyweight per ISO week (Monday start), ascending by week.

    Weeks with no entry are omitted (gaps preserved, never interpolated).
    The week containing ``today`` is marked ``is_current_week`` so callers can
    render it provisionally or exclude it from completed-week comparisons.
    """
    if today is None:
        today = date.today()
    current_week = iso_week_start(today)

    buckets: dict[date, list[float]] = {}
    for d, kg in weight_by_date.items():
        buckets.setdefault(iso_week_start(d), []).append(kg)

    return [
        WeeklyAverage(
            week_start=week_start,
            avg_kg=round(sum(vals) / len(vals), 2),
            n_entries=len(vals),
            is_current_week=(week_start == current_week),
        )
        for week_start, vals in sorted(buckets.items())
    ]
