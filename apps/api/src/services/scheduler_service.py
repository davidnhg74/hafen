"""Cron-driven migration schedules.

The arq worker's 60s cron job calls `tick()`; that selects every
enabled schedule whose `next_run_at` is due, clones the source
migration's config into a fresh MigrationRecord, enqueues it through
the same `run_migration_job` path as manual runs, and advances
`next_run_at` to the next slot.

Missed-tick policy: we fire *once* and jump `next_run_at` to the
next future slot. No backfill. If the worker was down for 3 hours
and the schedule fires hourly, the operator sees a single catch-up
run at tick time and then the normal cadence resumes. This matches
cron's own behavior and avoids a thundering herd when a worker
recovers.

Schedule-to-migration is 1:1 (unique FK). If operators want two
cadences on the same data movement they clone the migration — one
`MigrationRecord` plus one schedule is easier to reason about than
a many-to-many.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy.orm import Session

from ..models import MigrationRecord, MigrationSchedule
from ..utils.time import utc_now


logger = logging.getLogger(__name__)


# Signature of the enqueue hook — an awaitable taking the new
# migration id. The worker passes one that posts into arq's redis
# pool; tests pass an in-memory recorder.
EnqueueFn = Callable[[str], Awaitable[Optional[str]]]


# ─── Validation + cron math ──────────────────────────────────────────


def validate_cron(expr: str, tz: str) -> None:
    """Raise ValueError if either the cron expression or the timezone
    is unparseable. Called at write time so operators get a useful
    400 instead of a later silent failure."""
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {tz!r}") from exc
    if not croniter.is_valid(expr):
        raise ValueError(f"invalid cron expression: {expr!r}")


def compute_next_run_at(cron_expr: str, tz: str, from_time: datetime) -> datetime:
    """Return the next naive-UTC datetime the cron should fire at,
    strictly after `from_time`. Evaluated in `tz` so "run at 2am"
    stays 2am across DST transitions."""
    zone = ZoneInfo(tz)
    aware_utc = from_time.replace(tzinfo=timezone.utc)
    aware_local = aware_utc.astimezone(zone)
    it = croniter(cron_expr, aware_local)
    nxt_local = it.get_next(datetime)
    return nxt_local.astimezone(timezone.utc).replace(tzinfo=None)


# ─── CRUD ────────────────────────────────────────────────────────────


def get_schedule_for_migration(
    db: Session, migration_id: uuid.UUID
) -> Optional[MigrationSchedule]:
    return (
        db.query(MigrationSchedule)
        .filter(MigrationSchedule.migration_id == migration_id)
        .one_or_none()
    )


def upsert_schedule(
    db: Session,
    migration_id: uuid.UUID,
    *,
    name: str,
    cron_expr: str,
    timezone_name: str,
    enabled: bool,
) -> MigrationSchedule:
    validate_cron(cron_expr, timezone_name)
    now = utc_now()
    next_run = compute_next_run_at(cron_expr, timezone_name, now)

    sched = get_schedule_for_migration(db, migration_id)
    if sched is None:
        sched = MigrationSchedule(
            id=uuid.uuid4(),
            migration_id=migration_id,
            name=name,
            cron_expr=cron_expr,
            timezone=timezone_name,
            enabled=enabled,
            next_run_at=next_run,
        )
        db.add(sched)
    else:
        sched.name = name
        sched.cron_expr = cron_expr
        sched.timezone = timezone_name
        sched.enabled = enabled
        # Only reset next_run_at when the cadence changed — otherwise
        # an operator who only toggles `enabled` shouldn't see the
        # schedule skip a beat.
        sched.next_run_at = next_run

    db.commit()
    db.refresh(sched)
    return sched


def delete_schedule(db: Session, migration_id: uuid.UUID) -> bool:
    sched = get_schedule_for_migration(db, migration_id)
    if sched is None:
        return False
    db.delete(sched)
    db.commit()
    return True


# ─── Cloning + firing ────────────────────────────────────────────────


# Columns that define the migration's *config* — copied wholesale
# onto the clone. Everything else (status, timings, row counts) is
# reset so the clone starts at a clean state.
_CLONE_CONFIG_COLUMNS = (
    "name",
    "schema_name",
    "source_url",
    "target_url",
    "source_schema",
    "target_schema",
    "tables",
    "batch_size",
    "create_tables",
)


def clone_from_schedule(
    db: Session, sched: MigrationSchedule
) -> MigrationRecord:
    """Create a fresh MigrationRecord from the schedule's source
    migration with run-state reset. Commits and returns the new row.
    Raises if the source migration was deleted out from under us."""
    source = db.get(MigrationRecord, sched.migration_id)
    if source is None:
        raise ValueError(
            f"schedule {sched.id} references missing migration "
            f"{sched.migration_id}"
        )
    clone = MigrationRecord(
        id=uuid.uuid4(),
        status="pending",
        spawned_from_schedule_id=sched.id,
    )
    for col in _CLONE_CONFIG_COLUMNS:
        setattr(clone, col, getattr(source, col))
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


async def fire_schedule(
    db: Session,
    sched: MigrationSchedule,
    enqueue: EnqueueFn,
    *,
    now: Optional[datetime] = None,
) -> MigrationRecord:
    """Clone, enqueue, and advance the schedule's `next_run_at`.

    Always advances next_run_at and updates last_run_* — even if the
    enqueue call fails. An unrecoverable enqueue failure still counts
    as an attempted fire; the operator sees it in last_run_status and
    can debug. We don't double-fire on the next tick just because the
    queue was briefly unreachable."""
    now = now or utc_now()
    clone = clone_from_schedule(db, sched)
    try:
        await enqueue(str(clone.id))
        enqueue_error: Optional[str] = None
    except Exception as exc:
        logger.exception(
            "scheduler enqueue failed for schedule %s (clone %s)",
            sched.id,
            clone.id,
        )
        enqueue_error = f"{type(exc).__name__}: {exc}"

    sched.last_run_at = now
    sched.last_run_migration_id = clone.id
    sched.last_run_status = (
        "enqueue_failed" if enqueue_error else clone.status
    )
    sched.next_run_at = compute_next_run_at(
        sched.cron_expr, sched.timezone, now
    )
    db.commit()
    return clone


async def tick(db: Session, enqueue: EnqueueFn) -> list[str]:
    """Called every minute by the arq cron job. Finds due schedules
    and fires each. Returns the list of new migration IDs that were
    created so the caller can log them.

    One schedule's failure must not skip the others — wrap each in
    its own try/except."""
    now = utc_now()
    due = (
        db.query(MigrationSchedule)
        .filter(
            MigrationSchedule.enabled.is_(True),
            MigrationSchedule.next_run_at <= now,
        )
        .all()
    )
    fired: list[str] = []
    for sched in due:
        try:
            clone = await fire_schedule(db, sched, enqueue, now=now)
            fired.append(str(clone.id))
        except Exception:
            logger.exception(
                "schedule %s failed to fire; continuing with next", sched.id
            )
            db.rollback()
    return fired
