"""Weekly (ISO-week) weight averaging — the shared function behind Chart B
and the adaptive calorie engine."""
from datetime import date

from app.weight_trend import iso_week_start, weekly_averages


def test_iso_week_start_is_monday():
    # 2026-06-23 is a Tuesday → week starts Monday 2026-06-22
    assert iso_week_start(date(2026, 6, 23)) == date(2026, 6, 22)
    # A Monday maps to itself
    assert iso_week_start(date(2026, 6, 22)) == date(2026, 6, 22)
    # A Sunday belongs to the week that started the previous Monday
    assert iso_week_start(date(2026, 6, 28)) == date(2026, 6, 22)


def test_groups_by_week_and_means():
    # Two entries in week of Jun 8 (Mon), one in week of Jun 15
    weights = {
        date(2026, 6, 9): 80.0,
        date(2026, 6, 11): 80.4,
        date(2026, 6, 16): 79.0,
    }
    out = weekly_averages(weights, today=date(2026, 6, 16))
    assert [w.week_start for w in out] == [date(2026, 6, 8), date(2026, 6, 15)]
    assert out[0].avg_kg == 80.2 and out[0].n_entries == 2
    assert out[1].avg_kg == 79.0 and out[1].n_entries == 1


def test_only_weeks_with_entries_no_interpolation():
    # Gap: week of Jun 8 then week of Jun 22 — the empty Jun 15 week is omitted
    weights = {date(2026, 6, 9): 80.0, date(2026, 6, 23): 78.0}
    out = weekly_averages(weights, today=date(2026, 6, 23))
    assert [w.week_start for w in out] == [date(2026, 6, 8), date(2026, 6, 22)]


def test_current_week_flagged_provisional():
    weights = {date(2026, 6, 15): 80.0, date(2026, 6, 23): 79.0}
    out = weekly_averages(weights, today=date(2026, 6, 23))
    assert out[0].is_current_week is False   # week of Jun 15 is complete
    assert out[-1].is_current_week is True    # week of Jun 22 contains today


def test_empty_input():
    assert weekly_averages({}, today=date(2026, 6, 23)) == []
