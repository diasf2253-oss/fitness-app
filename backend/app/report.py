"""Weekly / biweekly report builder.

Assembles a period report from existing data sources — new PRs, the training
streak, bodyweight trend (reusing weight_trend.weekly_averages), diet
adherence, sleep, and a forward-looking plan (adaptive calorie target +
sets-per-week volume flags). Every section is built independently and returns
None when there's no data for the period, so the report never breaks on
missing Apple-Health-derived data.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session as DBSession

from app.config import settings as app_config
from app.models import (
    Exercise, NutritionDay, Session, SessionExercise, Set, SleepLog, WeightLog,
)
from app.muscles import MUSCLE_GROUPS, resolved_volume_targets
from app.routers.settings import get_or_create_settings
from app.routers.stats import epley_1rm
from app.routers.streak import streak_snapshot
from app.weight_trend import iso_week_start, weekly_averages

PERIOD_DAYS = {"weekly": 7, "biweekly": 14}


def _period_prs(db: DBSession, start: date, end: date, user_id: int) -> list[dict]:
    """Estimated-1RM PRs achieved in [start, end] — an in-period best that
    beats the best from before the period (a fresh lift with no history counts
    as a new PR)."""
    end_dt = datetime.combine(end, time.max)
    rows = (
        db.query(Session.started_at, Set.weight_kg, Set.reps, Exercise.id, Exercise.name)
        .join(SessionExercise, Session.id == SessionExercise.session_id)
        .join(Set, SessionExercise.id == Set.session_exercise_id)
        .join(Exercise, SessionExercise.exercise_id == Exercise.id)
        .filter(
            Session.user_id == user_id,
            Set.is_completed == True, Set.is_warmup == False,   # noqa: E712
            Set.reps > 0, Set.weight_kg > 0, Session.started_at <= end_dt,
        )
        .all()
    )
    by_ex: dict[int, dict] = {}
    for started_at, weight, reps, exid, name in rows:
        rec = by_ex.setdefault(exid, {"name": name, "prior": 0.0, "in": 0.0, "set": None})
        e1rm = epley_1rm(weight, reps)
        if started_at.date() < start:
            rec["prior"] = max(rec["prior"], e1rm)
        elif e1rm > rec["in"]:
            rec["in"], rec["set"] = e1rm, (weight, reps)

    prs = []
    for rec in by_ex.values():
        if rec["in"] > 0 and rec["in"] > rec["prior"]:
            w, reps = rec["set"]
            prs.append({
                "exercise": rec["name"],
                "estimated_1rm": round(rec["in"], 1),
                "previous_best": round(rec["prior"], 1) if rec["prior"] > 0 else None,
                "best_set": f"{w:g} kg × {reps}",
            })
    prs.sort(key=lambda p: p["estimated_1rm"], reverse=True)
    return prs


def _bodyweight(db: DBSession, end: date, weeks_back: int, user_id: int) -> dict | None:
    """Change in the weekly-average weight over the period (reuses the shared
    weekly-average function)."""
    since = end - timedelta(days=7 * (weeks_back + 2) + 7)
    rows = db.query(WeightLog).filter(
        WeightLog.user_id == user_id, WeightLog.date >= since, WeightLog.date <= end
    ).all()
    weeks = weekly_averages({w.date: w.weight_kg for w in rows}, end)
    if len(weeks) < 2:
        return None
    end_wk = weeks[-1]
    target_start = end_wk.week_start - timedelta(days=7 * weeks_back)
    start_wk = next((w for w in weeks if w.week_start == target_start), weeks[0])
    if start_wk.week_start == end_wk.week_start:
        return None
    change = round(end_wk.avg_kg - start_wk.avg_kg, 2)
    return {
        "start_week": start_wk.week_start.isoformat(), "start_avg": start_wk.avg_kg,
        "end_week": end_wk.week_start.isoformat(), "end_avg": end_wk.avg_kg,
        "change_kg": change,
        "direction": "down" if change < 0 else "up" if change > 0 else "flat",
    }


def _diet(db: DBSession, start: date, end: date, settings, user_id: int) -> dict | None:
    """Days within ±10% of the calorie target and ≥90% of the protein target,
    over the days that actually have logged nutrition."""
    rows = db.query(NutritionDay).filter(
        NutritionDay.user_id == user_id, NutritionDay.date >= start, NutritionDay.date <= end
    ).all()
    if not rows:
        return None
    cal_t, prot_t = settings.calorie_target, settings.protein_target_g
    cal_ok = sum(1 for n in rows if n.calories and abs(n.calories - cal_t) <= 0.10 * cal_t)
    prot_ok = sum(1 for n in rows if n.protein_g and n.protein_g >= 0.90 * prot_t)
    n = len(rows)
    return {
        "logged_days": n, "calorie_target": cal_t, "protein_target_g": prot_t,
        "calorie_on_target": cal_ok, "protein_on_target": prot_ok,
        "calorie_pct": round(100 * cal_ok / n), "protein_pct": round(100 * prot_ok / n),
    }


def _sleep(db: DBSession, start: date, end: date, days: int, user_id: int) -> dict | None:
    def avg(s: date, e: date):
        rows = db.query(SleepLog).filter(
            SleepLog.user_id == user_id, SleepLog.date >= s, SleepLog.date <= e
        ).all()
        if not rows:
            return None, 0
        return sum(r.asleep_minutes for r in rows) / len(rows) / 60.0, len(rows)

    cur, nights = avg(start, end)
    if cur is None:
        return None
    prev, _ = avg(start - timedelta(days=days), start - timedelta(days=1))
    return {
        "avg_hours": round(cur, 1), "nights": nights,
        "prev_avg_hours": round(prev, 1) if prev else None,
        "change_h": round(cur - prev, 1) if prev else None,
    }


def _current_week_volume_flags(db: DBSession, settings, today: date, user_id: int) -> list[dict]:
    week_start = iso_week_start(today)
    since = datetime.combine(week_start, time.min)
    rows = (
        db.query(Exercise.primary_muscle_group)
        .join(SessionExercise, SessionExercise.exercise_id == Exercise.id)
        .join(Session, Session.id == SessionExercise.session_id)
        .join(Set, Set.session_exercise_id == SessionExercise.id)
        .filter(
            Session.user_id == user_id,
            Set.is_completed == True, Set.is_warmup == False,   # noqa: E712
            Session.started_at >= since,
        )
        .all()
    )
    counts: dict[str, int] = {}
    for (group,) in rows:
        if group:
            counts[group] = counts.get(group, 0) + 1

    targets = resolved_volume_targets(settings.volume_targets)
    flags = []
    for m in MUSCLE_GROUPS:
        c = counts.get(m, 0)
        low, high = targets[m]
        if c < low:
            flags.append({"muscle": m, "count": c, "low": low, "high": high, "status": "under"})
        elif c > high:
            flags.append({"muscle": m, "count": c, "low": low, "high": high, "status": "over"})
    return flags


def build_report(db: DBSession, user_id: int, period: str = "weekly") -> dict:
    if period not in PERIOD_DAYS:
        raise ValueError(f"period must be one of {list(PERIOD_DAYS)}")
    days = PERIOD_DAYS[period]
    weeks_back = days // 7
    today = date.today()
    start = today - timedelta(days=days - 1)

    settings = get_or_create_settings(db, user_id)
    streak = streak_snapshot(db, user_id)

    prs = _period_prs(db, start, today, user_id)
    return {
        "period": period,
        "period_days": days,
        "start": start.isoformat(),
        "end": today.isoformat(),
        "generated_at": datetime.utcnow().isoformat(),
        "prs": {"items": prs, "count": len(prs)},
        "streak": {
            "current": streak.current, "longest": streak.longest,
            "alive": streak.alive, "at_risk": streak.at_risk,
        },
        "bodyweight": _bodyweight(db, today, weeks_back, user_id),
        "diet": _diet(db, start, today, settings, user_id),
        "sleep": _sleep(db, start, today, days, user_id),
        "plan": {
            "calorie_target": settings.calorie_target,
            "goal_kg_per_week": settings.goal_kg_per_week,
            "next_adapt": (iso_week_start(today) + timedelta(days=7)).isoformat(),
            "volume_flags": _current_week_volume_flags(db, settings, today, user_id),
        },
        "coach_available": app_config.coach_enabled,
    }


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def report_markdown(r: dict) -> str:
    NONE = "_No data for this period._"
    lines: list[str] = []
    title = "Weekly" if r["period"] == "weekly" else "Biweekly"
    lines += [f"# {title} report", "", f"**{r['start']} → {r['end']}**", ""]

    lines += ["## New PRs", ""]
    if r["prs"]["items"]:
        for p in r["prs"]["items"]:
            prev = f" (was {p['previous_best']} kg)" if p["previous_best"] else " (first record)"
            lines.append(f"- **{p['exercise']}** — est. 1RM {p['estimated_1rm']} kg{prev}, best set {p['best_set']}")
    else:
        lines.append("_No new PRs this period._")
    lines.append("")

    s = r["streak"]
    lines += ["## Streak", "",
              f"- Current: **{s['current']}** workout(s) in a row" + (" · ⚠️ at risk" if s["at_risk"] else ""),
              f"- Longest ever: {s['longest']}", ""]

    bw = r["bodyweight"]
    lines += ["## Bodyweight trend", ""]
    if bw:
        arrow = "▼" if bw["direction"] == "down" else "▲" if bw["direction"] == "up" else "→"
        lines.append(f"- {bw['start_avg']} kg → {bw['end_avg']} kg ({arrow} {abs(bw['change_kg'])} kg, weekly avg)")
    else:
        lines.append(NONE)
    lines.append("")

    d = r["diet"]
    lines += ["## Diet adherence", ""]
    if d:
        lines += [
            f"- Calories within target: **{d['calorie_pct']}%** ({d['calorie_on_target']}/{d['logged_days']} logged days)",
            f"- Protein on target: **{d['protein_pct']}%** ({d['protein_on_target']}/{d['logged_days']})",
        ]
    else:
        lines.append(NONE)
    lines.append("")

    sl = r["sleep"]
    lines += ["## Sleep", ""]
    if sl:
        trend = f" ({'+' if (sl['change_h'] or 0) >= 0 else ''}{sl['change_h']} h vs prior)" if sl["change_h"] is not None else ""
        lines.append(f"- Average **{sl['avg_hours']} h** over {sl['nights']} night(s){trend}")
    else:
        lines.append(NONE)
    lines.append("")

    p = r["plan"]
    lines += ["## Plan for next week", "",
              f"- Calorie target: **{p['calorie_target']} kcal** (aiming to lose {p['goal_kg_per_week']} kg/wk; next adapt {p['next_adapt']})"]
    if p["volume_flags"]:
        for f in p["volume_flags"]:
            lines.append(f"- {f['muscle']}: {f['count']} sets — **{f['status']}** target ({f['low']}–{f['high']})")
    else:
        lines.append("- Volume on track across all muscle groups this week.")
    lines.append("")

    return "\n".join(lines)
