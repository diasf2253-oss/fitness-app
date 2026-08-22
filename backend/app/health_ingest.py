"""
Shared Apple Health ingest core.

Both authoritative ingest paths funnel through the one aggregator in this
module so they apply *identical* rules — the "validated pipeline":

  * units       — weight normalised to kg (lb/g), nutrition via
                  ``health_metrics.convert_amount``.
  * timezone    — a reading is bucketed by its own calendar date; a sleep
                  interval is attributed to the morning you woke up
                  (``_night_of``), not the evening you lay down.
  * dedup       — Apple keeps overlapping samples from several sources
                  (iPhone + Watch both count steps). Cumulative quantities
                  are totalled per ``(day, source)`` and the single highest
                  source wins the day — never summed across sources.
  * manual-precedence — every write lands through the ``upsert_*`` helpers in
                  ``routers.health``, so a day the user corrected by hand
                  survives any sync.

``health_xml.py`` feeds this raw per-sample records from an export.xml
backfill; the ``/api/ingest/health/shortcut`` endpoint feeds it the small,
pre-aggregated daily payload an iOS Shortcut posts. The finalize step — the
part that actually decides what reaches the database — is shared, so the two
paths cannot drift.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session as DBSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parsing helpers — tolerant, because Shortcut / export payloads are loose.
# ---------------------------------------------------------------------------

def to_kg(raw: float, unit: Optional[str]) -> float:
    """Normalise a bodyweight reading to kilograms. Defaults to kg."""
    u = (unit or "kg").strip().lower()
    if u in ("lb", "lbs", "pound", "pounds"):
        return raw * 0.453592
    if u in ("g", "gram", "grams"):
        return raw / 1000
    return raw  # kg / unknown → assume already kg


def to_float(value) -> float:
    """
    Coerce a JSON number or numeric string to float. Handles the comma
    decimal separator an iOS Shortcut on a pt-BR (or other European-locale)
    phone emits — "82,5" → 82.5, "1.234,5" → 1234.5 — the same locale quirk
    the frontend already guards against on manual entry.
    """
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if "," in s and "." in s:
        # European grouping: "." thousands, "," decimal
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def parse_when(s: str) -> datetime:
    """
    Parse a timestamp from a Shortcut / export payload into a datetime.
    Accepts ISO 8601 (with 'Z' or ±HH:MM offset), the space-separated
    "``YYYY-MM-DD HH:MM:SS ±HHMM``" Apple form, and a bare date.
    """
    s = str(s).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Last resort: the leading date portion.
    return datetime.fromisoformat(s[:10])


def parse_day(s: str) -> date:
    """Calendar date of a timestamp string."""
    return parse_when(s).date()


def _sort_key(dt: datetime) -> float:
    """
    A comparable ordering key for a reading, robust to mixing tz-aware and
    naive datetimes within one payload (``datetime`` comparison raises on the
    mix; ``.timestamp()`` never does).
    """
    return dt.timestamp()


def _night_of(end: datetime) -> date:
    """
    Attribute a sleep interval to the wake-up morning. An interval ending at
    or after 18:00 is the pre-midnight chunk of the *next* morning's night.
    """
    d = end.date()
    if end.hour >= 18:
        return d + timedelta(days=1)
    return d


# How many parse warnings to surface in a report before going quiet.
_MAX_WARNINGS = 10


class HealthAggregator:
    """
    Collects health readings, then (in :meth:`finalize`) resolves the single
    best source per day and upserts through the manual-precedence helpers.

    Callers push readings via the ``add_*`` methods and bump
    :attr:`records_seen` for every raw record they consider (handled or not,
    so ``records_parsed`` in the report reflects the whole file). Unknown
    types go in :attr:`ignored_types`; recoverable problems in
    :attr:`warnings` via :meth:`warn`.
    """

    def __init__(self) -> None:
        # cumulative → total per (day, source), best single source wins the day
        self.steps_by_day_source: dict[tuple[date, str], int] = defaultdict(int)
        # weight → latest reading of the day wins, keyed (sort_key, kg)
        self.weight_by_day: dict[date, tuple[float, float]] = {}
        self.sleep_acc: dict[tuple[date, str], dict[str, float]] = defaultdict(
            lambda: {"asleep": 0.0, "in_bed": 0.0, "deep": 0.0, "rem": 0.0, "core": 0.0}
        )
        self.diet_by_day_source: dict[tuple[date, str], dict[str, float]] = defaultdict(dict)
        self.ignored_types: set[str] = set()
        self.warnings: list[str] = []
        self.records_seen = 0

    def warn(self, msg: str) -> None:
        if len(self.warnings) < _MAX_WARNINGS:
            self.warnings.append(msg)

    # -- ingest ------------------------------------------------------------

    def add_steps(self, day: date, value: float, source: str) -> None:
        self.steps_by_day_source[(day, source)] += int(round(value))

    def add_weight(self, when: datetime, raw: float, unit: Optional[str], source: str) -> None:
        kg = to_kg(raw, unit)
        key = _sort_key(when)
        prev = self.weight_by_day.get(when.date())
        if prev is None or key >= prev[0]:
            self.weight_by_day[when.date()] = (key, round(kg, 2))

    def add_sleep_interval(
        self, start: datetime, end: datetime, value_str: str, source: str
    ) -> None:
        """One raw HealthKit sleep interval (export.xml path)."""
        minutes = (end - start).total_seconds() / 60
        if minutes <= 0:
            return
        night = self.sleep_acc[(_night_of(end), source)]
        if "InBed" in value_str:
            night["in_bed"] += minutes
        elif "Asleep" in value_str:
            night["asleep"] += minutes
            if "Deep" in value_str:
                night["deep"] += minutes
            elif "REM" in value_str:
                night["rem"] += minutes
            elif "Core" in value_str:
                night["core"] += minutes

    def add_sleep_night(
        self,
        night: date,
        source: str,
        *,
        asleep: float = 0.0,
        in_bed: float = 0.0,
        deep: float = 0.0,
        rem: float = 0.0,
        core: float = 0.0,
    ) -> None:
        """One pre-aggregated night, keyed to the wake date (Shortcut path)."""
        acc = self.sleep_acc[(night, source)]
        acc["asleep"] += asleep
        acc["in_bed"] += in_bed
        acc["deep"] += deep
        acc["rem"] += rem
        acc["core"] += core

    def add_diet(self, day: date, amount: float, key: str, source: str) -> None:
        day_values = self.diet_by_day_source[(day, source)]
        day_values[key] = day_values.get(key, 0.0) + amount

    # -- resolve + persist -------------------------------------------------

    def finalize(self, db: DBSession, user_id: int) -> dict:
        """
        Reduce to the best source per day and upsert (scoped to `user_id` —
        the account whose ingest_token authenticated this push). Returns the
        canonical import report shared by every ingest path.
        """
        # Lazy import: routers.health imports this module.
        from app.health_metrics import upsert_nutrition_partial
        from app.routers.health import upsert_sleep, upsert_steps, upsert_weight

        created = 0

        best_steps: dict[date, int] = {}
        for (d, _src), total in self.steps_by_day_source.items():
            if total > best_steps.get(d, 0):
                best_steps[d] = total
        for d, steps in best_steps.items():
            created += upsert_steps(db, d, steps, "apple_health", user_id)

        for d, (_key, kg) in self.weight_by_day.items():
            created += upsert_weight(db, d, kg, "apple_health", user_id)

        best_sleep: dict[date, dict[str, float]] = {}
        for (d, _src), v in self.sleep_acc.items():
            # Legacy records may only carry InBed — still worth keeping.
            score = v["asleep"] or v["in_bed"]
            kept = best_sleep.get(d)
            if kept is None or score > (kept["asleep"] or kept["in_bed"]):
                best_sleep[d] = v
        for d, v in best_sleep.items():
            created += upsert_sleep(
                db, d,
                asleep_minutes=round(v["asleep"]),
                in_bed_minutes=round(v["in_bed"]),
                deep_minutes=round(v["deep"]) or None,
                rem_minutes=round(v["rem"]) or None,
                core_minutes=round(v["core"]) or None,
                source="apple_health",
                user_id=user_id,
            )

        best_diet: dict[date, dict[str, float]] = {}
        for (d, _src), values in self.diet_by_day_source.items():
            kept = best_diet.get(d)
            rank = (values.get("calories", 0.0), len(values))
            if kept is None or rank > (kept.get("calories", 0.0), len(kept)):
                best_diet[d] = values
        for d, values in best_diet.items():
            created += upsert_nutrition_partial(db, d, values, "apple_health", user_id)

        all_days = (
            list(best_steps) + list(self.weight_by_day)
            + list(best_sleep) + list(best_diet)
        )
        return {
            "status": "ok",
            "records_parsed": self.records_seen,
            "days": {
                "steps": len(best_steps),
                "weight": len(self.weight_by_day),
                "sleep": len(best_sleep),
                "nutrition": len(best_diet),
            },
            "rows_created": created,
            "date_range": {
                "from": min(all_days).isoformat() if all_days else None,
                "to": max(all_days).isoformat() if all_days else None,
            },
            "ignored_types": sorted(self.ignored_types)[:25],
            "warnings": self.warnings,
        }
