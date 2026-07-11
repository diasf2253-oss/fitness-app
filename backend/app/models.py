"""
SQLAlchemy ORM models.

All date columns and foreign keys are indexed for query performance.
JSON columns (secondary_muscles) use SQLAlchemy's JSON type, which stores
as TEXT in SQLite and as jsonb in Postgres — no code change needed.

Sync (multi-device): entity tables carry a `uuid` (globally unique identity —
integer PKs are device-local and collide across devices) and `updated_at`
(last-write-wins merge). Date-keyed health tables merge on `date`, so they
carry `updated_at` only. See app/sync.py.
"""
from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _new_uuid() -> str:
    return str(uuid4())


class SyncMixin:
    """Global identity + merge timestamp for tables that sync across devices."""
    uuid: Mapped[str] = mapped_column(
        String(36), default=_new_uuid, unique=True, index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class UpdatedAtMixin:
    """Merge timestamp for date-keyed / singleton tables (no uuid needed)."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


# ---------------------------------------------------------------------------
# Workout domain
# ---------------------------------------------------------------------------

class Exercise(SyncMixin, Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    primary_muscle: Mapped[Optional[str]] = mapped_column(String(100))
    # Canonical muscle-group taxonomy (muscles.MUSCLE_GROUPS) — drives the
    # Ranks body map. Auto-tagged from the name; the legacy free-text
    # primary_muscle is kept as the fallback hint.
    primary_muscle_group: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    # Stored as a JSON array of strings, e.g. ["hamstrings", "glutes"]
    secondary_muscles: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    equipment: Mapped[Optional[str]] = mapped_column(String(100))
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships (back-populated for convenience)
    routine_exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="exercise"
    )
    session_exercises: Mapped[list["SessionExercise"]] = relationship(
        back_populates="exercise"
    )


class Routine(SyncMixin, Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan",
        order_by="RoutineExercise.position"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="routine")


class RoutineExercise(SyncMixin, Base):
    __tablename__ = "routine_exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routine.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercise.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    target_sets: Mapped[int] = mapped_column(Integer, default=3)
    target_rep_low: Mapped[int] = mapped_column(Integer, default=8)
    target_rep_high: Mapped[int] = mapped_column(Integer, default=12)
    rest_seconds: Mapped[int] = mapped_column(Integer, default=120)

    routine: Mapped["Routine"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(back_populates="routine_exercises")


class Session(SyncMixin, Base):
    """A single workout session (one gym visit)."""
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Nullable: an ad-hoc workout has no routine template
    routine_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("routine.id"), index=True, nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    routine: Mapped[Optional["Routine"]] = relationship(back_populates="sessions")
    exercises: Mapped[list["SessionExercise"]] = relationship(
        back_populates="session", cascade="all, delete-orphan",
        order_by="SessionExercise.position"
    )


class SessionExercise(SyncMixin, Base):
    """An exercise slot within a live session."""
    __tablename__ = "session_exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercise.id"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped["Session"] = relationship(back_populates="exercises")
    exercise: Mapped["Exercise"] = relationship(back_populates="session_exercises")
    sets: Mapped[list["Set"]] = relationship(
        back_populates="session_exercise", cascade="all, delete-orphan",
        order_by="Set.set_number"
    )


class Set(SyncMixin, Base):
    """One set within a session exercise (e.g. 3rd set of bench press)."""
    __tablename__ = "set"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session_exercise.id", ondelete="CASCADE"), index=True
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # RPE (Rate of Perceived Exertion) 1-10, optional
    rpe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_warmup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    session_exercise: Mapped["SessionExercise"] = relationship(back_populates="sets")


# ---------------------------------------------------------------------------
# Plan items (Phase 8) — trackable day/study/workout plan, AI- or hand-drafted.
# Many rows per date (unlike the one-per-date health logs). A time-blocked
# to-do the user checks off; the AI Coach proposes them, the user approves.
# ---------------------------------------------------------------------------

class PlanItem(SyncMixin, Base):
    __tablename__ = "plan_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Optional time block, stored as zero-padded "HH:MM" so it sorts lexically
    start_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 'workout' | 'study' | 'task' | 'meal' | 'other'
    category: Mapped[str] = mapped_column(String(20), default="task", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 'coach' | 'manual'
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)


# ---------------------------------------------------------------------------
# Health & nutrition (one row per date; upsert on re-import)
# ---------------------------------------------------------------------------

class WeightLog(UpdatedAtMixin, Base):
    __tablename__ = "weight_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    # 'apple_health' | 'manual'
    source: Mapped[str] = mapped_column(String(50), default="manual")


class StepsLog(UpdatedAtMixin, Base):
    __tablename__ = "steps_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")


class SleepLog(UpdatedAtMixin, Base):
    __tablename__ = "sleep_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    asleep_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    in_bed_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    deep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rem_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    core_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")


class NutritionDay(UpdatedAtMixin, Base):
    __tablename__ = "nutrition_day"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    calories: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    # Micronutrients as {"fiber_g": 31.2, "sodium_mg": 2300, ...} — canonical
    # keys carry their unit suffix so the UI never has to guess units.
    micros: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    # 'apple_health' | 'manual' (nutrition syncs in via Apple Health)
    source: Mapped[str] = mapped_column(String(50), default="manual")


# ---------------------------------------------------------------------------
# Trackers (Phase 6) — the generic "track anything" system.
# A tracker is anything with a name and a kind; one log per day each.
#   habit  → done/not-done (value_num 0|1), streaks
#   scale  → 1–5 rating (e.g. the seeded Mood)
#   number → any quantity with a unit (reading minutes, caffeine, …)
#   text   → free text (e.g. the seeded Journal)
# ---------------------------------------------------------------------------

class Tracker(SyncMixin, Base):
    __tablename__ = "tracker"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 'habit' | 'scale' | 'number' | 'text'
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Display unit for kind='number' (e.g. 'min', 'mg', 'pages')
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Archived trackers keep their history but leave the daily check-in
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    logs: Mapped[list["TrackerLog"]] = relationship(
        back_populates="tracker", cascade="all, delete-orphan"
    )


class TrackerLog(SyncMixin, Base):
    """One tracker entry per day (upsert by tracker+date)."""
    __tablename__ = "tracker_log"
    __table_args__ = (UniqueConstraint("tracker_id", "date", name="uq_tracker_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tracker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tracker.id", ondelete="CASCADE"), index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_num: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tracker: Mapped["Tracker"] = relationship(back_populates="logs")


# ---------------------------------------------------------------------------
# App settings (single row, id=1 always)
# ---------------------------------------------------------------------------

class AppSettings(UpdatedAtMixin, Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    calorie_target: Mapped[int] = mapped_column(Integer, default=2400)
    protein_target_g: Mapped[int] = mapped_column(Integer, default=180)
    fat_max_g: Mapped[int] = mapped_column(Integer, default=100)
    # 'metric' | 'imperial'
    unit_system: Mapped[str] = mapped_column(String(20), default="metric")
    # 'male' | 'female' — scales the Ranks strength references
    sex: Mapped[str] = mapped_column(String(10), default="male")
    # Rank-ladder overrides (standards / female multiplier / agg); null ⇒ defaults
    rank_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # When the last successful Apple Health ingest ran (push or backfill)
    health_last_ingest: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
