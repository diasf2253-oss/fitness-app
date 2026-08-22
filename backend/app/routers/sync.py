"""
Sync endpoints (Phase 9) — the laptop side of device-to-device sync.

The phone PWA (local-first, own IndexedDB copy) calls these when it can
reach the laptop on the LAN — on app open and via a manual Sync button:

  GET  /api/sync/manifest      — cheap "anything new?" probe
  GET  /api/sync/pull?since=…  — rows changed after `since` (omit: everything)
  POST /api/sync/push          — device's changes, merged last-write-wins

The server is stateless about peers: each device remembers its own last
sync time and passes it as `since`. Merge semantics live in app/sync.py.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import User
from app.schemas import SyncManifestOut, SyncPullOut, SyncPushIn, SyncPushOut
from app.sync import SYNC_TABLES, apply_push, build_manifest, serialize_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.get("/manifest", response_model=SyncManifestOut)
def sync_manifest(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    return SyncManifestOut(server_time=datetime.utcnow(), tables=build_manifest(db, current_user.id))


@router.get("/pull", response_model=SyncPullOut)
def sync_pull(
    since: Optional[datetime] = Query(None),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    tables = {name: serialize_table(db, name, current_user.id, since) for name in SYNC_TABLES}
    return SyncPullOut(
        server_time=datetime.utcnow(),
        since=since,
        # Omit untouched tables so an incremental pull stays small
        tables={name: rows for name, rows in tables.items() if rows},
    )


@router.post("/push", response_model=SyncPushOut)
def sync_push(
    payload: SyncPushIn,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    unknown = sorted(set(payload.tables) - set(SYNC_TABLES))
    result = apply_push(db, payload.tables, current_user.id)
    db.commit()
    warnings = result["warnings"]
    if unknown:
        warnings = [f"unknown tables ignored: {', '.join(unknown)}"] + warnings
    logger.info("Sync push merged: %s", result["counts"])
    return SyncPushOut(
        status="ok",
        server_time=datetime.utcnow(),
        counts=result["counts"],
        warnings=warnings,
    )
