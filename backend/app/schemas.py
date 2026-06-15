"""
Pydantic v2 schemas for request/response validation.
We never return raw SQLAlchemy objects from API endpoints — always use these.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared config: enable from_attributes so we can build schemas from ORM rows
# ---------------------------------------------------------------------------

class OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Exercise
# ---------------------------------------------------------------------------

class ExerciseBase(BaseModel):
    name: str
    primary_muscle: Optional[str] = None
    secondary_muscles: list[str] = []
    equipment: Optional[str] = None
    notes: Optional[str] = None


class ExerciseCreate(ExerciseBase):
    is_custom: bool = True


class ExerciseUpdate(ExerciseBase):
    name: Optional[str] = None
    is_custom: Optional[bool] = None


class ExerciseOut(OrmBase, ExerciseBase):
    id: int
    is_custom: bool


# ---------------------------------------------------------------------------
# Routine
# ---------------------------------------------------------------------------

class RoutineExerciseBase(BaseModel):
    exercise_id: int
    position: int
    target_sets: int = 3
    target_rep_low: int = 8
    target_rep_high: int = 12
    rest_seconds: int = 120


class RoutineExerciseCreate(RoutineExerciseBase):
    pass


class RoutineExerciseOut(OrmBase, RoutineExerciseBase):
    id: int
    exercise: ExerciseOut


class RoutineBase(BaseModel):
    name: str
    notes: Optional[str] = None


class RoutineCreate(RoutineBase):
    exercises: list[RoutineExerciseCreate] = []


class RoutineUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    exercises: Optional[list[RoutineExerciseCreate]] = None


class RoutineOut(OrmBase, RoutineBase):
    id: int
    created_at: datetime
    exercises: list[RoutineExerciseOut] = []


# ---------------------------------------------------------------------------
# Session (workout)
# ---------------------------------------------------------------------------

class SetBase(BaseModel):
    set_number: int
    weight_kg: float = 0.0
    reps: int = 0
    rpe: Optional[float] = None
    is_warmup: bool = False
    is_completed: bool = False


class SetCreate(SetBase):
    pass


class SetUpdate(BaseModel):
    weight_kg: Optional[float] = None
    reps: Optional[int] = None
    rpe: Optional[float] = None
    is_warmup: Optional[bool] = None
    is_completed: Optional[bool] = None
    completed_at: Optional[datetime] = None


class SetOut(OrmBase, SetBase):
    id: int
    session_exercise_id: int
    completed_at: Optional[datetime] = None


class SessionExerciseBase(BaseModel):
    exercise_id: int
    position: int


class SessionExerciseCreate(SessionExerciseBase):
    sets: list[SetCreate] = []


class SessionExerciseOut(OrmBase, SessionExerciseBase):
    id: int
    session_id: int
    exercise: ExerciseOut
    sets: list[SetOut] = []


class SessionCreate(BaseModel):
    name: str
    routine_id: Optional[int] = None
    notes: Optional[str] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    ended_at: Optional[datetime] = None
    notes: Optional[str] = None


class SessionOut(OrmBase):
    id: int
    name: str
    routine_id: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    notes: Optional[str] = None
    exercises: list[SessionExerciseOut] = []


class SessionSummary(OrmBase):
    """Lightweight session for history list (no nested exercises)."""
    id: int
    name: str
    routine_id: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Health & nutrition
# ---------------------------------------------------------------------------

class WeightLogCreate(BaseModel):
    date: date
    weight_kg: float
    source: str = "manual"


class WeightLogOut(OrmBase):
    id: int
    date: date
    weight_kg: float
    source: str


class StepsLogCreate(BaseModel):
    date: date
    steps: int
    source: str = "manual"


class StepsLogOut(OrmBase):
    id: int
    date: date
    steps: int
    source: str


class SleepLogCreate(BaseModel):
    date: date
    asleep_minutes: int
    in_bed_minutes: int
    deep_minutes: Optional[int] = None
    rem_minutes: Optional[int] = None
    core_minutes: Optional[int] = None
    source: str = "manual"


class SleepLogOut(OrmBase):
    id: int
    date: date
    asleep_minutes: int
    in_bed_minutes: int
    deep_minutes: Optional[int] = None
    rem_minutes: Optional[int] = None
    core_minutes: Optional[int] = None
    source: str


class NutritionDayCreate(BaseModel):
    date: date
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    # Optional micronutrients; omitting it on a manual macro correction
    # preserves whatever micros Apple Health already synced for that day
    micros: Optional[dict] = None
    source: str = "manual"


class NutritionDayOut(OrmBase):
    id: int
    date: date
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    micros: Optional[dict] = None
    source: str


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class AppSettingsUpdate(BaseModel):
    calorie_target: Optional[int] = None
    protein_target_g: Optional[int] = None
    fat_max_g: Optional[int] = None
    unit_system: Optional[str] = None


class AppSettingsOut(OrmBase):
    id: int
    calorie_target: int
    protein_target_g: int
    fat_max_g: int
    unit_system: str
    health_last_ingest: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Stats / PRs
# ---------------------------------------------------------------------------

class PRRecord(BaseModel):
    exercise_id: int
    exercise_name: str
    heaviest_weight_kg: float
    best_estimated_1rm: float
    best_set_volume: float  # weight × reps for one set


class PRHit(BaseModel):
    """A PR achieved during a specific session."""
    exercise_id: int
    exercise_name: str
    kind: str           # 'heaviest' | 'best_1rm' | 'best_volume'
    value: float
    previous_best: Optional[float] = None  # None if this is the first ever record


class SessionSummaryStats(BaseModel):
    """Computed summary shown when a workout is finished."""
    session_id: int
    duration_minutes: Optional[int] = None
    total_volume_kg: float
    completed_sets: int
    prs_hit: list[PRHit] = []


# ---------------------------------------------------------------------------
# Dashboard (Phase 2) — one payload for the whole home screen
# ---------------------------------------------------------------------------

class WeightPoint(BaseModel):
    date: date
    weight_kg: float


class MovingAvgPoint(BaseModel):
    date: date
    avg_kg: float


class DashboardWeight(BaseModel):
    series: list[WeightPoint] = []
    moving_avg_7d: list[MovingAvgPoint] = []


class StepsPoint(BaseModel):
    date: date
    steps: int


class SleepPoint(BaseModel):
    date: date
    asleep_hours: float


class NutritionToday(BaseModel):
    """Today's intake; `logged` is False when nothing was recorded yet."""
    date: date
    logged: bool
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    micros: dict = {}


class DashboardTargets(BaseModel):
    calorie_target: int
    protein_target_g: int
    fat_max_g: int
    unit_system: str


class RecentPR(PRHit):
    """A PR hit, annotated with the session date it happened on."""
    date: date


class DashboardTraining(BaseModel):
    week_volume_kg: float = 0.0
    sessions_this_week: int = 0
    recent_prs: list[RecentPR] = []


class DashboardOut(BaseModel):
    weight: DashboardWeight
    steps: list[StepsPoint] = []
    sleep: list[SleepPoint] = []
    nutrition_today: NutritionToday
    targets: DashboardTargets
    training: DashboardTraining


# ---------------------------------------------------------------------------
# Trackers (Phase 6)
# ---------------------------------------------------------------------------

TRACKER_KINDS = ("habit", "scale", "number", "text")


class TrackerCreate(BaseModel):
    name: str
    kind: str  # validated in the router against TRACKER_KINDS
    unit: Optional[str] = None


class TrackerUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    position: Optional[int] = None
    is_archived: Optional[bool] = None


class TrackerLogValue(BaseModel):
    """Today's (or any day's) entry for a tracker."""
    date: date
    value_num: Optional[float] = None
    value_text: Optional[str] = None


class TrackerOut(OrmBase):
    id: int
    name: str
    kind: str
    unit: Optional[str] = None
    position: int
    is_archived: bool
    # Enriched by the list endpoint for the daily check-in:
    today: Optional[TrackerLogValue] = None
    streak: Optional[int] = None  # habits only


class TrackerLogOut(OrmBase):
    date: date
    value_num: Optional[float] = None
    value_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Insights (Phase 7)
# ---------------------------------------------------------------------------

class HabitWeek(BaseModel):
    name: str
    done: int
    days: int


class ScaleWeek(BaseModel):
    name: str
    avg: Optional[float] = None


class WeekMetrics(BaseModel):
    date_from: date
    date_to: date
    volume_kg: float = 0.0
    sessions: int = 0
    steps_avg: Optional[int] = None
    sleep_avg_h: Optional[float] = None
    calories_avg: Optional[int] = None
    protein_avg_g: Optional[int] = None
    # Last reading minus first reading inside the window (needs ≥2 readings)
    weight_change_kg: Optional[float] = None
    scales: list[ScaleWeek] = []
    habits: list[HabitWeek] = []


class WeeklyReviewOut(BaseModel):
    current: WeekMetrics
    previous: WeekMetrics


class CorrelationPoint(BaseModel):
    date: date
    a: float
    b: float


class CorrelationPair(BaseModel):
    label_a: str
    label_b: str
    r: float
    n: int
    points: list[CorrelationPoint] = []


class TrainingSplit(BaseModel):
    """Average of a scale tracker on training days vs rest days."""
    name: str
    with_avg: float
    without_avg: float
    n_with: int
    n_without: int


class CorrelationsOut(BaseModel):
    window_days: int
    pairs: list[CorrelationPair] = []
    training_splits: list[TrainingSplit] = []


# ---------------------------------------------------------------------------
# Calendar + day detail (Phase 4) — desktop right rail
# ---------------------------------------------------------------------------

class CalendarDay(BaseModel):
    """Markers for one day that has any data. Days without data are omitted."""
    date: date
    sessions: int = 0
    steps: Optional[int] = None
    has_weight: bool = False
    has_sleep: bool = False
    has_nutrition: bool = False
    trackers: int = 0  # tracker entries logged that day
    plan_items: int = 0  # planned items that day


class MonthCalendarOut(BaseModel):
    year: int
    month: int
    days: list[CalendarDay] = []


class DaySession(BaseModel):
    """One workout on the selected day, summarized via Phase 1 stats."""
    id: int
    name: str
    duration_minutes: Optional[int] = None
    total_volume_kg: float
    completed_sets: int


class DayTracker(BaseModel):
    """A tracker entry shown in the day-detail panel."""
    name: str
    kind: str
    unit: Optional[str] = None
    value_num: Optional[float] = None
    value_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Plan items (Phase 8)
# ---------------------------------------------------------------------------

PLAN_CATEGORIES = ("workout", "study", "task", "meal", "other")


class PlanItemBase(BaseModel):
    title: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: str = "task"
    notes: Optional[str] = None


class PlanItemCreate(PlanItemBase):
    source: str = "manual"


class PlanItemUpdate(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    is_done: Optional[bool] = None
    position: Optional[int] = None


class PlanItemOut(OrmBase):
    id: int
    date: date
    title: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: str
    notes: Optional[str] = None
    is_done: bool
    position: int
    source: str


class DayDetailOut(BaseModel):
    date: date
    sessions: list[DaySession] = []
    weight_kg: Optional[float] = None
    steps: Optional[int] = None
    sleep: Optional[SleepLogOut] = None
    nutrition: Optional[NutritionDayOut] = None
    trackers: list[DayTracker] = []
    plan: list[PlanItemOut] = []
