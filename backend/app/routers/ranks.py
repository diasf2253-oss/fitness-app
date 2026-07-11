"""Rank ladder — per-body-part tier / division / LP from logged data and
current bodyweight.

GET /api/ranks — body-map data: every muscle group's rank (the average of its
exercises' benchmark scores) plus the per-exercise PR breakdown behind it.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app import ranks as R
from app.auth import require_auth
from app.db import get_db
from app.models import Exercise, Session, SessionExercise, Set, WeightLog
from app.muscles import MUSCLE_GROUPS
from app.routers.settings import get_or_create_settings

router = APIRouter(prefix="/api/ranks", tags=["ranks"])


def _latest_bodyweight(db: DBSession) -> float | None:
    """Latest REAL reading only — a leftover demo ('sample') or interpolated
    ('estimated') row must never set the bodyweight every rank divides by."""
    from app.routers.health import DERIVED_SOURCES
    row = (
        db.query(WeightLog)
        .filter(WeightLog.source.notin_(DERIVED_SOURCES))
        .order_by(WeightLog.date.desc())
        .first()
    )
    return row.weight_kg if row else None


def _best_alltime_by_exercise(db: DBSession) -> dict[int, tuple]:
    """{exercise_id: (best_1rm, weight, reps)} over ALL completed working sets
    ever (no recency window) — the ranks are PR-based, using the same capped
    Epley as the PR system so the two never disagree."""
    rows = (
        db.query(SessionExercise.exercise_id, Set.weight_kg, Set.reps)
        .join(Session, Session.id == SessionExercise.session_id)
        .join(Set, Set.session_exercise_id == SessionExercise.id)
        .filter(
            Set.is_completed == True, Set.is_warmup == False,   # noqa: E712
            Set.reps > 0, Set.weight_kg > 0,
        )
        .all()
    )
    best: dict[int, tuple] = {}
    for exid, w, reps in rows:
        e = R.epley_1rm(w, reps)
        if exid not in best or e > best[exid][0]:
            best[exid] = (e, w, reps)
    return best


@router.get("")
def get_ranks(db: DBSession = Depends(get_db), _: None = Depends(require_auth)):
    settings = get_or_create_settings(db)
    cfg = R.resolve_config(settings.rank_config)
    bw = _latest_bodyweight(db)
    sex = settings.sex

    exercises = db.query(Exercise).all()
    by_id = {e.id: e for e in exercises}
    by_group: dict[str, list[int]] = {}
    for e in exercises:
        if e.primary_muscle_group:
            by_group.setdefault(e.primary_muscle_group, []).append(e.id)

    best_all = _best_alltime_by_exercise(db)

    # A muscle's rank is the AVERAGE of its exercises' scores. Each exercise's
    # score = all-time best 1RM ÷ bodyweight, measured against that exercise's
    # own benchmark (equipment- and unilateral-aware for custom exercises), so
    # every logged movement for the muscle contributes.
    body_parts = []
    for m in list(MUSCLE_GROUPS) + list(R.BODY_MAP_EXTRA):
        contribs = []
        if bw:
            for eid in by_group.get(m, []):
                rec = best_all.get(eid)
                if not rec:
                    continue
                e1rm, w, reps = rec
                ex = by_id[eid]
                bench = R.exercise_benchmark(ex.name, m, sex, cfg, ex.equipment)
                score = (e1rm / bw) / bench
                er = R.compute_rank(score, R.COMMON_ANCHORS)
                contribs.append({
                    "exercise_name": ex.name,
                    "equipment": ex.equipment,
                    "best_1rm": round(e1rm, 1),
                    "best_set": f"{w:g} kg × {reps}",
                    "relative": round(e1rm / bw, 2),
                    "score": round(score, 2),
                    "tier": er["tier"], "tier_index": er["tier_index"],
                    "division": er["division"], "lp": er["lp"], "color": er["color"],
                })
        contribs.sort(key=lambda c: c["tier_index"] + c["lp"] / 100, reverse=True)
        bp = {"muscle": m, "ranked": False, "color": R.UNRANKED_COLOR,
              # tracked = part of the muscle taxonomy; BODY_MAP_EXTRA regions
              # are anatomy-only and can never rank.
              "tracked": m in MUSCLE_GROUPS,
              "n_exercises": len(contribs), "exercises": contribs}
        if contribs:
            mean_score = sum(c["score"] for c in contribs) / len(contribs)
            rank = R.compute_rank(mean_score, R.COMMON_ANCHORS)
            bp.update({"ranked": True, "score": round(mean_score, 2), **rank})
        body_parts.append(bp)

    return {
        "bodyweight": bw, "sex": sex,
        "tiers": R.TIERS, "tier_colors": R.TIER_COLORS, "unranked_color": R.UNRANKED_COLOR,
        "body_parts": body_parts,
        "note": None if bw else "Log your bodyweight to see ranks.",
    }
