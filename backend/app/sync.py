"""
Multi-device sync engine (Phase 9), scoped per authenticated user (Phase
1-2 friends beta).

Devices are peers, each with a full local copy of one user's data (laptop:
this backend + SQLite/Postgres; phone: the PWA's IndexedDB). Sync is a
stateless pull/push over the same tables, scoped to whichever user's
session cookie authenticated the request:

  - Entity rows are identified by `uuid` (integer PKs are device-local);
    foreign keys travel as parent uuids and are re-resolved on import.
  - Date-keyed health rows merge on `date`; settings is a per-user singleton
    (one row per user, matched on `user_id`).
  - Merge is last-write-wins by `updated_at`, except health tables also
    respect source precedence (a manual correction is never buried by a
    synced value) via routers.health._write_blocked.
  - Incoming `updated_at` is preserved verbatim, so applying a sync does
    not make rows look newly-edited and echo back on the next exchange.
  - `user_id` never travels in the sync payload (excluded on read, ignored
    on write) — every row is scoped to and forced onto the authenticated
    caller server-side. `Exercise` is the one table with an owner-optional
    column: NULL rows are the shared global library, visible to and
    read-only-ish for everyone; a user's own custom exercises carry their
    `user_id` and sync only to their own devices. Every FK parent lookup
    (e.g. a TrackerLog's tracker_id) is scoped the same way its own table
    would be, even for child tables — like TrackerLog — that carry no
    user_id column of their own, so a row can never attach to another
    user's parent even if a client somehow sent that uuid.

Known v1 limits (deliberate, weekly sync within one user's devices):
  - No tombstones: deletions do not propagate and can resurface.
  - Clock skew between devices shifts last-write-wins fairness.
  - Rows created independently on both devices before their first sync
    get distinct uuids; unique-constrained collisions (exercise.name,
    tracker name+kind, tracker_log tracker+date) fall back to a natural-key
    match instead of crashing, keeping the local uuid.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy import inspect as sa_inspect, or_
from sqlalchemy.orm import Session as DBSession

from app.models import (
    Activity, AppSettings, Exercise, NutritionDay, PlanItem, Routine,
    RoutineExercise, RoutineNote, Session, SessionExercise, Set as SetModel,
    SleepLog, StepsLog, Tracker, TrackerLog, WeightLog,
)

_MAX_WARNINGS = 20

# Tables whose rows carry a health `source` and must respect its precedence
_SOURCE_PRECEDENCE_MODELS = (WeightLog, StepsLog, SleepLog, NutritionDay)


@dataclass(frozen=True)
class TableSpec:
    model: type
    key: str                                   # 'uuid' | 'date' | 'singleton'
    # local FK column -> (payload field carrying the parent uuid, parent model)
    fks: dict = field(default_factory=dict)
    # fallback identity when uuid lookup misses (pre-first-sync collisions)
    natural_key: tuple = ()
    # columns never serialized/applied (device-local facts)
    exclude: tuple = ()


# Parents before children: FK resolution on import walks this order.
SYNC_TABLES: dict[str, TableSpec] = {
    "exercise": TableSpec(Exercise, "uuid", natural_key=("name",)),
    "routine": TableSpec(Routine, "uuid"),
    "routine_exercise": TableSpec(
        RoutineExercise, "uuid",
        fks={"routine_id": ("routine_uuid", Routine),
             "exercise_id": ("exercise_uuid", Exercise)},
    ),
    "session": TableSpec(
        Session, "uuid", fks={"routine_id": ("routine_uuid", Routine)},
    ),
    "session_exercise": TableSpec(
        SessionExercise, "uuid",
        fks={"session_id": ("session_uuid", Session),
             "exercise_id": ("exercise_uuid", Exercise)},
    ),
    "set": TableSpec(
        SetModel, "uuid",
        fks={"session_exercise_id": ("session_exercise_uuid", SessionExercise)},
    ),
    # Next-session notes: sync by uuid, FK to routine. The session references
    # are device-local integer ids, so they never travel (excluded); the
    # archived_at flag DOES sync, so a note is never resurfaced on another device.
    "routine_note": TableSpec(
        RoutineNote, "uuid",
        fks={"routine_id": ("routine_uuid", Routine)},
        exclude=("created_in_session_id", "surfaced_in_session_id"),
    ),
    "activity": TableSpec(Activity, "uuid"),
    "plan_item": TableSpec(PlanItem, "uuid"),
    "tracker": TableSpec(Tracker, "uuid", natural_key=("name", "kind")),
    "tracker_log": TableSpec(
        TrackerLog, "uuid",
        fks={"tracker_id": ("tracker_uuid", Tracker)},
        natural_key=("tracker_id", "date"),
    ),
    "weight_log": TableSpec(WeightLog, "date"),
    "steps_log": TableSpec(StepsLog, "date"),
    "sleep_log": TableSpec(SleepLog, "date"),
    "nutrition_day": TableSpec(NutritionDay, "date"),
    "settings": TableSpec(AppSettings, "singleton", exclude=("health_last_ingest",)),
}


def _owner_filter(query, model: type, user_id: int):
    """Scope a query to rows this user may touch. Exercise is the one
    owner-optional table: NULL (the shared global library) or their own."""
    if model is Exercise:
        return query.filter(or_(model.user_id.is_(None), model.user_id == user_id))
    return query.filter(model.user_id == user_id)


def _columns(spec: TableSpec) -> list:
    return list(sa_inspect(spec.model).columns)


def _to_jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _coerce(column, value):
    """Parse an incoming JSON value into the column's Python type."""
    if value is None or not isinstance(value, str):
        return value
    type_name = type(column.type).__name__
    if type_name == "DateTime":
        return datetime.fromisoformat(value)
    if type_name == "Date":
        return date.fromisoformat(value)
    return value


def serialize_table(
    db: DBSession, name: str, user_id: int, since: Optional[datetime] = None
) -> list[dict]:
    """Rows of one table as sync payload dicts (FKs replaced by parent uuids).
    Scoped to `user_id` (plus the shared global exercise library)."""
    spec = SYNC_TABLES[name]
    query = _owner_filter(db.query(spec.model), spec.model, user_id)
    if since is not None:
        query = query.filter(spec.model.updated_at > since)
    rows = query.all()
    if not rows:
        return []

    # Prefetch id -> uuid per parent model (one query each, not per row)
    fk_uuid_maps = {
        local_col: dict(db.query(parent.id, parent.uuid).all())
        for local_col, (_field, parent) in spec.fks.items()
    }

    skip = set(spec.exclude) | {"id", "user_id"} | set(spec.fks)
    out = []
    for row in rows:
        data = {
            c.name: _to_jsonable(getattr(row, c.name))
            for c in _columns(spec) if c.name not in skip
        }
        for local_col, (payload_field, _parent) in spec.fks.items():
            parent_id = getattr(row, local_col)
            data[payload_field] = fk_uuid_maps[local_col].get(parent_id)
        out.append(data)
    return out


def _find_existing(db: DBSession, spec: TableSpec, data: dict, resolved: dict, user_id: int):
    """Locate the local row this payload row refers to, or None. Always
    scoped to `user_id` (Exercise: or the shared global library) — a push
    can never match, and therefore never update, another user's row."""
    if spec.key == "singleton":
        return db.query(spec.model).filter(spec.model.user_id == user_id).first()
    if spec.key == "date":
        return (
            _owner_filter(db.query(spec.model), spec.model, user_id)
            .filter(spec.model.date == _coerce_date(data.get("date")))
            .first()
        )
    row = None
    if data.get("uuid"):
        row = (
            _owner_filter(db.query(spec.model), spec.model, user_id)
            .filter(spec.model.uuid == data["uuid"])
            .first()
        )
    if row is None and spec.natural_key:
        filters = []
        for col in spec.natural_key:
            value = resolved.get(col, data.get(col))
            value = _coerce(getattr(spec.model, col).expression, value)
            filters.append(getattr(spec.model, col) == value)
        query = db.query(spec.model).filter(*filters)
        # tracker_log's natural key already pins it to a specific (resolved)
        # tracker_id, itself owner-scoped by the FK resolution below — no
        # user_id column of its own to filter here. Every other natural-key
        # table has user_id directly.
        if hasattr(spec.model, "user_id"):
            query = _owner_filter(query, spec.model, user_id)
        row = query.first()
    return row


def _coerce_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def _parse_updated_at(data: dict) -> datetime:
    value = data.get("updated_at")
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value or datetime.min


def apply_push(db: DBSession, tables: dict[str, list[dict]], user_id: int) -> dict:
    """
    Merge a device's pushed rows, all scoped to `user_id`. Returns a
    per-table report: {table: {received, inserted, updated, skipped_older,
    skipped_blocked, skipped_missing_parent}}, plus capped warnings.
    """
    from app.routers.health import _write_blocked

    counts: dict[str, dict[str, int]] = {}
    warnings: list[str] = []
    # incoming uuid -> local row, for parents merged by natural key in this
    # same payload (children must resolve to the local row, not the uuid)
    remap: dict[str, object] = {}

    def warn(msg: str) -> None:
        if len(warnings) < _MAX_WARNINGS:
            warnings.append(msg)

    for name, spec in SYNC_TABLES.items():  # parents before children
        rows = tables.get(name) or []
        c = counts[name] = {
            "received": len(rows), "inserted": 0, "updated": 0,
            "skipped_older": 0, "skipped_blocked": 0, "skipped_missing_parent": 0,
        }
        columns = {col.name: col for col in _columns(spec)}

        for data in rows:
            # ---- Resolve FKs: parent uuid -> local integer id, scoped to
            # this user (or the global library, for exercise) so a child row
            # can never link to another user's parent. ----
            resolved: dict[str, int] = {}
            missing_parent = False
            for local_col, (payload_field, parent) in spec.fks.items():
                parent_uuid = data.get(payload_field)
                if parent_uuid is None:
                    if columns[local_col].nullable:
                        resolved[local_col] = None
                        continue
                    missing_parent = True
                    break
                parent_row = remap.get(parent_uuid) or (
                    _owner_filter(db.query(parent), parent, user_id)
                    .filter(parent.uuid == parent_uuid)
                    .first()
                )
                if parent_row is None:
                    if columns[local_col].nullable:
                        warn(f"{name}: parent {payload_field}={parent_uuid} not found, linked as none")
                        resolved[local_col] = None
                        continue
                    missing_parent = True
                    break
                resolved[local_col] = parent_row.id
            if missing_parent:
                c["skipped_missing_parent"] += 1
                warn(f"{name}: row {data.get('uuid') or data.get('date')} skipped — parent not found")
                continue

            existing = _find_existing(db, spec, data, resolved, user_id)
            incoming_ts = _parse_updated_at(data)

            # ---- Source precedence for health rows (manual is sacred) ----
            if isinstance(existing, _SOURCE_PRECEDENCE_MODELS) and _write_blocked(
                existing, data.get("source", "")
            ):
                c["skipped_blocked"] += 1
                continue

            if existing is not None and existing.updated_at is not None \
                    and incoming_ts <= existing.updated_at:
                c["skipped_older"] += 1
                # Still remap so this payload's children resolve to our row
                if spec.key == "uuid" and data.get("uuid"):
                    remap[data["uuid"]] = existing
                continue

            # user_id never comes from the client — excluded on read, and
            # ignored here too even if a payload somehow carried one.
            skip = set(spec.exclude) | {"id", "user_id"} | set(spec.fks)
            field_values = {
                col_name: _coerce(col, data[col_name])
                for col_name, col in columns.items()
                if col_name in data and col_name not in skip
            }

            if existing is None:
                extra = {"user_id": user_id} if "user_id" in columns else {}
                row = spec.model(**field_values, **resolved, **extra)
                db.add(row)
                db.flush()  # assign id so children in this payload can link
                c["inserted"] += 1
            else:
                row = existing
                # Merged by natural key: keep the local uuid as this row's
                # stable identity here; children remap via the incoming uuid.
                if spec.key == "uuid" and existing.uuid != data.get("uuid"):
                    field_values.pop("uuid", None)
                    warn(f"{name}: '{data.get('uuid')}' merged by natural key into local row")
                # Ownership never changes on an update, regardless of payload.
                for col_name, value in {**field_values, **resolved}.items():
                    setattr(row, col_name, value)
                c["updated"] += 1

            if spec.key == "uuid" and data.get("uuid"):
                remap[data["uuid"]] = row

    return {"counts": counts, "warnings": warnings}


def build_manifest(db: DBSession, user_id: int) -> dict:
    """Cheap 'anything new?' summary: row count + newest updated_at per
    table, scoped to `user_id` (plus the shared global exercise library)."""
    tables = {}
    for name, spec in SYNC_TABLES.items():
        count = _owner_filter(db.query(spec.model), spec.model, user_id).count()
        last = (
            _owner_filter(db.query(spec.model.updated_at), spec.model, user_id)
            .order_by(spec.model.updated_at.desc())
            .limit(1)
            .scalar()
        )
        tables[name] = {"rows": count, "last_updated": last}
    return tables
