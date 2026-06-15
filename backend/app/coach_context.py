"""
Coach context — turns the app's data into a compact text brief the AI Coach
plans from. Reuses existing read logic (dashboard summary, weekly insights,
recent sessions, trackers, today's plan) so the Coach sees exactly what the
rest of the app sees. Kept terse: this rides in every Coach request's system
prompt, so it favours signal over completeness.
"""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.models import (
    Exercise, NutritionDay, PlanItem, Routine, Session as WorkoutSession,
    SessionExercise, Set as SetModel, SleepLog, StepsLog, Tracker, TrackerLog, WeightLog,
)
from app.routers.insights import period_metrics
from app.routers.settings import get_or_create_settings


def _recent_training(db: DBSession, today: date, days: int = 14) -> list[str]:
    """One line per finished session in the window, most recent first."""
    start = datetime.combine(today - timedelta(days=days), time.min)
    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.started_at >= start)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    lines = []
    for ws in sessions[:8]:
        names = [se.exercise.name for se in ws.exercises]
        d = ws.started_at.date().isoformat()
        ex = ", ".join(names[:6]) if names else "no exercises"
        lines.append(f"  - {d} · {ws.name}: {ex}")
    return lines


def _pr_lines(db: DBSession) -> list[str]:
    """Heaviest working set per exercise (compact, capped)."""
    rows = (
        db.query(Exercise.name, func.max(SetModel.weight_kg))
        .join(SessionExercise, SessionExercise.exercise_id == Exercise.id)
        .join(SetModel, SetModel.session_exercise_id == SessionExercise.id)
        .filter(SetModel.is_completed.is_(True), SetModel.is_warmup.is_(False),
                SetModel.weight_kg > 0)
        .group_by(Exercise.id)
        .order_by(func.max(SetModel.weight_kg).desc())
        .limit(8)
        .all()
    )
    return [f"  - {name}: {kg:g} kg" for name, kg in rows]


def build_context(db: DBSession) -> str:
    """Assemble the full brief. Pure read; safe to call on every request."""
    today = date.today()
    s = get_or_create_settings(db)
    parts: list[str] = [f"Today is {today.strftime('%A, %d %B %Y')}."]

    # ---- Body & health snapshot ----
    w = db.query(WeightLog).order_by(WeightLog.date.desc()).first()
    sleep = db.query(SleepLog).order_by(SleepLog.date.desc()).first()
    steps_avg = (
        db.query(func.avg(StepsLog.steps))
        .filter(StepsLog.date >= today - timedelta(days=7))
        .scalar()
    )
    health = []
    if w:
        health.append(f"weight {w.weight_kg:g} kg (as of {w.date.isoformat()})")
    if sleep:
        health.append(f"last sleep {round(sleep.asleep_minutes / 60, 1)} h")
    if steps_avg:
        health.append(f"~{round(steps_avg):,} steps/day (7d avg)")
    if health:
        parts.append("Body & health: " + "; ".join(health) + ".")

    # ---- Nutrition today vs targets ----
    nut = db.query(NutritionDay).filter(NutritionDay.date == today).first()
    if nut:
        parts.append(
            f"Today's intake: {round(nut.calories)} kcal "
            f"(target {s.calorie_target}), protein {round(nut.protein_g)} g "
            f"(target {s.protein_target_g}), carbs {round(nut.carbs_g)} g, fat {round(nut.fat_g)} g."
        )
    else:
        parts.append(
            f"Nutrition targets: {s.calorie_target} kcal, {s.protein_target_g} g protein, "
            f"{s.fat_max_g} g fat cap. Nothing logged today yet."
        )

    # ---- Training: weekly review + recent sessions + PRs ----
    cur = period_metrics(db, today - timedelta(days=6), today)
    parts.append(
        f"This week's training: {cur.sessions} sessions, "
        f"{round(cur.volume_kg):,} kg volume."
    )
    recent = _recent_training(db, today)
    if recent:
        parts.append("Recent workouts:\n" + "\n".join(recent))
    prs = _pr_lines(db)
    if prs:
        parts.append("Heaviest sets on record:\n" + "\n".join(prs))

    # ---- Routines available to start ----
    routines = db.query(Routine).order_by(Routine.name).all()
    if routines:
        rl = [f"  - {r.name} ({len(r.exercises)} exercises)" for r in routines]
        parts.append("Saved routines:\n" + "\n".join(rl))

    # ---- Trackers (habits/mood) this week ----
    tracker_lines = []
    for t in db.query(Tracker).filter(Tracker.is_archived.is_(False)).order_by(Tracker.position).all():
        if t.kind == "scale":
            vals = [
                r.value_num for r in db.query(TrackerLog).filter(
                    TrackerLog.tracker_id == t.id,
                    TrackerLog.date >= today - timedelta(days=6),
                    TrackerLog.value_num.isnot(None),
                ).all()
            ]
            if vals:
                tracker_lines.append(f"  - {t.name}: avg {round(sum(vals) / len(vals), 1)}/5 this week")
        elif t.kind == "habit":
            done = db.query(TrackerLog).filter(
                TrackerLog.tracker_id == t.id,
                TrackerLog.date >= today - timedelta(days=6),
                TrackerLog.value_num >= 1,
            ).count()
            tracker_lines.append(f"  - {t.name}: {done}/7 days this week")
    if tracker_lines:
        parts.append("Trackers:\n" + "\n".join(tracker_lines))

    # ---- Today's existing plan ----
    plan = (
        db.query(PlanItem)
        .filter(PlanItem.date == today)
        .order_by(PlanItem.position, PlanItem.start_time)
        .all()
    )
    if plan:
        pl = [
            f"  - {(p.start_time + ' ') if p.start_time else ''}{p.title} "
            f"[{p.category}]{' ✓' if p.is_done else ''}"
            for p in plan
        ]
        parts.append("Already planned today:\n" + "\n".join(pl))

    return "\n\n".join(parts)
