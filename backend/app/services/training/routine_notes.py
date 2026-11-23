"""Routine notes — "next time, do X" reminders that surface once on the next
session of a routine. HTTP endpoints live in routers/routine_notes.py."""
from datetime import datetime

from sqlalchemy.orm import Session as DBSession

from app.models import RoutineNote


def consume_pending_notes(db: DBSession, routine_id: int, session_id: int, user_id: int) -> list[RoutineNote]:
    """Surface and archive a routine's pending next-session notes onto the
    session that's starting, so they show once and never resurface."""
    pending = (
        db.query(RoutineNote)
        .filter(
            RoutineNote.user_id == user_id,
            RoutineNote.routine_id == routine_id,
            RoutineNote.archived_at.is_(None),
        )
        .all()
    )
    now = datetime.utcnow()
    for note in pending:
        note.surfaced_in_session_id = session_id
        note.archived_at = now
    return pending
