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
    source: str = "manual"


class NutritionDayOut(OrmBase):
    id: int
    date: date
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
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
