"""
AI Coach (Phase 8) — Claude-powered planning over the athlete's own data.

GET  /api/coach/status          — is a key configured? which model?
POST /api/coach/chat            — streaming chat (text/plain stream)
POST /api/coach/plan/workout    — structured next-workout proposal
POST /api/coach/plan/day        — structured day plan
POST /api/coach/plan/study      — structured study plan
POST /api/coach/accept/workout  — turn an approved workout into a routine
POST /api/coach/accept/day      — turn an approved day/study plan into plan items

Design: the planners return *proposals* (nothing saved); the accept endpoints
commit them after the user taps approve. Every call is grounded in
coach_context.build_context(), so the Coach reasons from real training, health,
and nutrition data. With no ANTHROPIC_API_KEY set, the planning/chat endpoints
return 503 and the rest of the app is unaffected.
"""
import logging
from datetime import date as date_cls
from typing import Optional

import anthropic
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.coach_context import build_context
from app.config import settings
from app.db import get_db
from app.models import Exercise, Routine, RoutineExercise, User
from app.routers.plan import add_plan_item
from app.schemas import PLAN_CATEGORIES, PlanItemCreate, PlanItemOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/coach", tags=["coach"])

MAX_TOKENS = 4096

COACH_SYSTEM = """You are the user's personal coach inside their life-tracking app. \
You help plan workouts, days, and study sessions, and answer questions about \
their training, health, and habits.

Voice: calm, direct, and honest — never hype, never gamified, no exclamation \
marks or emoji. Concise. Metric units (kg, km). Speak to the user as "you".

Ground every recommendation in the data brief below. Reference specifics \
(recent sessions, sleep, weight trend, what's already planned) rather than \
giving generic advice. If the data shows poor recovery (short sleep, low mood, \
high recent volume), say so and adjust the plan down. If you lack data to \
answer well, say what's missing rather than inventing it.

--- DATA BRIEF ---
{context}
--- END BRIEF ---"""


# ---------------------------------------------------------------------------
# Request / proposal models
# ---------------------------------------------------------------------------

class ChatTurn(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatTurn]


class PlanRequest(BaseModel):
    note: Optional[str] = None          # free-text steer, e.g. "short session, tired"
    date: Optional[date_cls] = None     # day/study target date; defaults to today


class WorkoutAcceptExercise(BaseModel):
    name: str
    sets: int = 3
    rep_low: int = 8
    rep_high: int = 12
    rest_seconds: int = 120
    note: Optional[str] = None


class WorkoutAccept(BaseModel):
    title: str
    exercises: list[WorkoutAcceptExercise]


class DayItemProposal(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    title: str
    category: str = "task"
    notes: Optional[str] = None


class DayAccept(BaseModel):
    date: date_cls
    items: list[DayItemProposal]


# ---------------------------------------------------------------------------
# Tool schemas for structured proposals (forced tool use)
# ---------------------------------------------------------------------------

WORKOUT_TOOL = {
    "name": "propose_workout",
    "description": "Return a single proposed strength workout.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short session name, e.g. 'Upper A'"},
            "rationale": {"type": "string", "description": "1-2 sentences tying the choice to the athlete's recent data"},
            "exercises": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sets": {"type": "integer"},
                        "rep_low": {"type": "integer"},
                        "rep_high": {"type": "integer"},
                        "rest_seconds": {"type": "integer"},
                        "note": {"type": "string", "description": "optional cue, e.g. target weight"},
                    },
                    "required": ["name", "sets", "rep_low", "rep_high"],
                },
            },
        },
        "required": ["title", "rationale", "exercises"],
    },
}

DAY_TOOL = {
    "name": "propose_plan",
    "description": "Return a time-blocked plan as a list of items.",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "1-2 sentences on the shape of the plan"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "HH:MM 24-hour, optional"},
                        "end_time": {"type": "string", "description": "HH:MM 24-hour, optional"},
                        "title": {"type": "string"},
                        "category": {"type": "string", "enum": list(PLAN_CATEGORIES)},
                        "notes": {"type": "string"},
                    },
                    "required": ["title", "category"],
                },
            },
        },
        "required": ["summary", "items"],
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client() -> anthropic.Anthropic:
    if not settings.coach_enabled:
        raise HTTPException(
            status_code=503,
            detail="AI Coach is not configured. Set ANTHROPIC_API_KEY in the backend .env.",
        )
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _propose(db: DBSession, tool: dict, user_prompt: str, user_id: int) -> dict:
    """Run a forced-tool-use request and return the tool input dict."""
    client = _client()
    system = COACH_SYSTEM.format(context=build_context(db, user_id))
    try:
        resp = client.messages.create(
            model=settings.coach_model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.warning("Coach API error: %s", e)
        raise HTTPException(status_code=502, detail=f"AI request failed: {e}")

    block = next((b for b in resp.content if b.type == "tool_use"), None)
    if block is None:
        raise HTTPException(status_code=502, detail="The coach did not return a structured plan.")
    return block.input


# ---------------------------------------------------------------------------
# Status + chat
# ---------------------------------------------------------------------------

@router.get("/status")
def coach_status(_: User = Depends(require_auth)):
    return {"enabled": settings.coach_enabled, "model": settings.coach_model}


@router.post("/chat")
def coach_chat(
    body: ChatRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Stream a chat reply as text/plain. Context is built before streaming so
    the DB session isn't held open across the network stream."""
    client = _client()
    if not body.messages:
        raise HTTPException(status_code=422, detail="messages must not be empty")

    system = COACH_SYSTEM.format(context=build_context(db, current_user.id))
    msgs = [{"role": t.role, "content": t.content} for t in body.messages]

    def generate():
        try:
            with client.messages.stream(
                model=settings.coach_model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=msgs,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except anthropic.APIError as e:
            logger.warning("Coach chat error: %s", e)
            yield f"\n\n[The coach hit an error: {e}]"

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


# ---------------------------------------------------------------------------
# Planners (proposals — nothing saved)
# ---------------------------------------------------------------------------

@router.post("/plan/workout")
def plan_workout(
    body: PlanRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    prompt = (
        "Plan my next strength workout. Prefer exercises I already train and "
        "respect my recent volume and recovery. Give concrete set/rep targets."
    )
    if body.note:
        prompt += f"\n\nExtra context from me: {body.note}"
    proposal = _propose(db, WORKOUT_TOOL, prompt, current_user.id)
    return {"kind": "workout", **proposal}


@router.post("/plan/day")
def plan_day(
    body: PlanRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    target = body.date or date_cls.today()
    prompt = (
        f"Plan my day for {target.isoformat()} as time-blocked items. "
        "Include training (or recovery) and meals around my targets, and leave "
        "room for focused work. Build around anything already planned."
    )
    if body.note:
        prompt += f"\n\nExtra context from me: {body.note}"
    proposal = _propose(db, DAY_TOOL, prompt, current_user.id)
    return {"kind": "day", "date": target.isoformat(), **proposal}


@router.post("/plan/study")
def plan_study(
    body: PlanRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    target = body.date or date_cls.today()
    prompt = (
        f"Plan focused study blocks for {target.isoformat()} as time-blocked "
        "items (category 'study'), with short breaks between blocks. Schedule "
        "around my training and energy through the day."
    )
    if body.note:
        prompt += f"\n\nWhat I need to study: {body.note}"
    proposal = _propose(db, DAY_TOOL, prompt, current_user.id)
    return {"kind": "study", "date": target.isoformat(), **proposal}


# ---------------------------------------------------------------------------
# Accept (commit an approved proposal)
# ---------------------------------------------------------------------------

@router.post("/accept/workout")
def accept_workout(
    body: WorkoutAccept,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Build a real routine from an approved workout proposal, creating any
    exercises that don't exist yet (case-insensitive match)."""
    if not body.exercises:
        raise HTTPException(status_code=422, detail="No exercises to add")

    user_id = current_user.id
    existing = {
        e.name.lower(): e
        for e in db.query(Exercise).filter(
            or_(Exercise.user_id.is_(None), Exercise.user_id == user_id)
        ).all()
    }
    routine = Routine(user_id=user_id, name=body.title.strip() or "Coached workout")
    db.add(routine)
    db.flush()

    for pos, ex in enumerate(body.exercises):
        match = existing.get(ex.name.strip().lower())
        if match is None:
            match = Exercise(user_id=user_id, name=ex.name.strip(), is_custom=True)
            db.add(match)
            db.flush()
            existing[match.name.lower()] = match
        db.add(RoutineExercise(
            user_id=user_id,
            routine_id=routine.id,
            exercise_id=match.id,
            position=pos,
            target_sets=max(1, ex.sets),
            target_rep_low=max(1, ex.rep_low),
            target_rep_high=max(ex.rep_low, ex.rep_high),
            rest_seconds=max(0, ex.rest_seconds),
        ))

    db.commit()
    db.refresh(routine)
    return {"routine_id": routine.id, "name": routine.name, "exercises": len(body.exercises)}


@router.post("/accept/day", response_model=list[PlanItemOut])
def accept_day(
    body: DayAccept,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Write an approved day/study plan into plan items (source='coach')."""
    if not body.items:
        raise HTTPException(status_code=422, detail="No items to add")

    created = []
    for it in body.items:
        item = add_plan_item(db, body.date, PlanItemCreate(
            title=it.title,
            start_time=it.start_time,
            end_time=it.end_time,
            category=it.category,
            notes=it.notes,
            source="coach",
        ), current_user.id)
        created.append(item)
    db.commit()
    for item in created:
        db.refresh(item)
    return created
