"""
SQLAlchemy ORM models.

All date columns and foreign keys are indexed for query performance.
JSON columns (secondary_muscles) use SQLAlchemy's JSON type, which stores
as TEXT in SQLite and as jsonb in Postgres — no code change needed.

Sync (multi-device): entity tables carry a `uuid` (globally unique identity —
integer PKs are device-local and collide across devices) and `updated_at`
(last-write-wins merge). Date-keyed health tables merge on `date`, so they
carry `updated_at` only. See app/sync.py.

Multi-user: every data table below carries a `user_id` FK to `users.id`,
scoping it to its owner. Two exceptions: `Exercise.user_id` is nullable —
NULL means the shared/global seeded library, set only for a user's own
custom exercises — and `TrackerLog`, which has no `user_id` column at all
because it is always reached through `tracker_id` (`Tracker.user_id`
already scopes it; see routers/trackers.py's `_get_tracker`). `AppSettings`
and `StreakState` used to be hardcoded `id=1` singleton rows; `user_id` is
now their actual primary key, so "one row per user" is structurally
enforced rather than a convention.
"""
from datetime import datetime, date
from typing import Optional
from uuid import uuid4
import secrets

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _new_uuid() -> str:
    return str(uuid4())


def _new_ingest_token() -> str:
    return secrets.token_urlsafe(32)


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
# Auth / multi-user (Phase 1-2 friends beta)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 'admin' | 'user'
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    # 'pending' | 'active' | 'disabled'
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Bearer credential for the Apple Health Shortcut/HAE pushes — separate
    # from the browser cookie session, since a Shortcut can't hold a cookie.
    ingest_token: Mapped[str] = mapped_column(
        String(64), default=_new_ingest_token, unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_uses: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AuthSession(Base):
    """A logged-in browser session. Table name `auth_session`, not `session`
    — that name is taken by the workout Session model/table below."""
    __tablename__ = "auth_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # The opaque cookie value (secrets.token_urlsafe) — never a JWT, so it
    # can be looked up and deleted server-side (logout, temp-password reset).
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Workout domain
# ---------------------------------------------------------------------------

class Exercise(SyncMixin, Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # NULL = shared/global seeded library; set only on a user's own custom
    # exercise. `name` stays globally unique (accepted v1 limitation: two
    # users can't both name a custom exercise the same seeded/taken name).
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
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
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # 'manual' | 'generated' — the workout generator replaces only 'generated'
    # routines on apply, leaving hand-made ones untouched.
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    exercises: Mapped[list["RoutineExercise"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan",
        order_by="RoutineExercise.position"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="routine")
    # Next-session notes for this training day (distinct from the `notes` text
    # column above, which is the routine's own description).
    routine_notes: Mapped[list["RoutineNote"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan",
        order_by="RoutineNote.created_at",
    )


class RoutineExercise(SyncMixin, Base):
    __tablename__ = "routine_exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
    # Next-session notes surfaced at the start of this session (from the routine).
    next_session_notes: Mapped[list["RoutineNote"]] = relationship(
        "RoutineNote",
        primaryjoin="Session.id == foreign(RoutineNote.surfaced_in_session_id)",
        viewonly=True,
        order_by="RoutineNote.created_at",
    )


class SessionExercise(SyncMixin, Base):
    """An exercise slot within a live session."""
    __tablename__ = "session_exercise"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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


class RoutineNote(SyncMixin, Base):
    """A one-shot 'next session' note for a training day (routine). Written
    during/after a session; surfaces once at the next session of that routine
    and then auto-archives — still visible in history, never resurfaced again.
    (Persistent per-exercise cues live on Exercise.notes, not here.)"""
    __tablename__ = "routine_note"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    routine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("routine.id", ondelete="CASCADE"), index=True, nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Informational session references (no FK, so deleting a session is safe).
    # Device-local integer ids — excluded from sync (see app/sync.py).
    created_in_session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    surfaced_in_session_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    # Pending while NULL; set when consumed at the next session of the routine.
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    routine: Mapped["Routine"] = relationship(back_populates="routine_notes")


# ---------------------------------------------------------------------------
# Plan items (Phase 8) — trackable day/study/workout plan, AI- or hand-drafted.
# Many rows per date (unlike the one-per-date health logs). A time-blocked
# to-do the user checks off; the AI Coach proposes them, the user approves.
# ---------------------------------------------------------------------------

class PlanItem(SyncMixin, Base):
    __tablename__ = "plan_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
# Health & nutrition (one row per user per date; upsert on re-import)
# ---------------------------------------------------------------------------

class WeightLog(UpdatedAtMixin, Base):
    __tablename__ = "weight_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_weight_log_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    # 'apple_health' | 'manual'
    source: Mapped[str] = mapped_column(String(50), default="manual")


class StepsLog(UpdatedAtMixin, Base):
    __tablename__ = "steps_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_steps_log_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")


class SleepLog(UpdatedAtMixin, Base):
    __tablename__ = "sleep_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_sleep_log_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    asleep_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    in_bed_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    deep_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rem_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    core_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")


class NutritionDay(UpdatedAtMixin, Base):
    __tablename__ = "nutrition_day"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_nutrition_day_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
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
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
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
    """One tracker entry per day (upsert by tracker+date). No `user_id` of
    its own — always reached through `tracker_id`, and `Tracker.user_id`
    already scopes it (see routers/trackers.py's `_get_tracker`)."""
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
# App settings (one row per user; user_id is the primary key)
# ---------------------------------------------------------------------------

class AppSettings(UpdatedAtMixin, Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # unique (not the PK) — a plain autoincrement id avoids a fragile
    # PK-swap migration across SQLite/Postgres, while still structurally
    # enforcing one settings row per user.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    # The adaptive calorie anchor — nudged ±a step each completed week by the
    # weight trend (see app.calorie_adapt). Never recomputed from scratch.
    calorie_target: Mapped[int] = mapped_column(Integer, default=2300)
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

    # ---- Profile (drives the RDA targets and the onboarding wizard) ----
    age: Mapped[int] = mapped_column(Integer, default=19, nullable=False)
    # First-run onboarding: the wizard flips this after the profile questions.
    # Existing installs are backfilled to True by the migration.
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Adaptive calorie engine (anchored weekly-trend step model) ----
    # Signed weekly bodyweight goal (kg/week): negative = cut, 0 = maintain,
    # positive = bulk. Matches the Diet goal slider (workbook H1a).
    goal_kg_per_week: Mapped[float] = mapped_column(Float, default=-0.5, nullable=False)
    # How far the target moves in one adaptation, and the dead-band around the
    # target rate inside which the target holds.
    adapt_step_kcal: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    adapt_tolerance_kg: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    # Hard floor; ceiling is estimated maintenance unless overridden here.
    calorie_floor: Mapped[int] = mapped_column(Integer, default=1800, nullable=False)
    calorie_ceiling: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Monday of the ISO week the target was last adapted (once-per-week guard).
    last_adapted_week: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # ---- Training ----
    # {muscle: [low, high]} weekly volume-target overrides; null ⇒ defaults in
    # app.muscles. Read by the sets-per-week analytics and the generator.
    volume_targets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Allowed rest days between workouts before the training streak breaks.
    streak_rest_gap: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Default rest-timer duration (seconds) for exercises with no routine rest.
    default_rest_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)

    # ---- Legacy (retired from-scratch TDEE fields; kept nullable, unused) ----
    goal_rate_kg_per_week: Mapped[float] = mapped_column(Float, default=-0.25, nullable=False)
    expenditure_kcal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    calorie_target_set_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class StreakState(UpdatedAtMixin, Base):
    """Persisted training-streak snapshot, one row per user. Recomputed from
    logged workouts on read, so it is NOT synced across devices — each device
    derives it locally. Structured so a future points/gamification layer can
    hook on (e.g. a `points` column) without reshaping the computation."""
    __tablename__ = "streak_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_workout_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class Activity(SyncMixin, Base):
    """A logged sport/training session that isn't barbell work — football,
    judo, padel, etc. Tracked for context; in the adaptive engine the calories
    are already captured by the weight trend, so the burn estimate here is
    informational (METs × duration × bodyweight)."""
    __tablename__ = "activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")
