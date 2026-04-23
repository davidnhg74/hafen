"""Migration schedule endpoints.

A schedule is 1:1 with a migration (the source acts as a template),
so the resource is named accordingly: one schedule per migration id.

    GET    /api/v1/migrations/{id}/schedule           → 200 or 404
    PUT    /api/v1/migrations/{id}/schedule           → upsert
    DELETE /api/v1/migrations/{id}/schedule           → 204 or 404
    POST   /api/v1/migrations/{id}/schedule/run-now   → clone + enqueue now

All endpoints are admin-only and gated by the `scheduled_migrations`
license feature.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.roles import require_role
from ..db import get_db
from ..license.dependencies import require_feature
from ..models import MigrationRecord, MigrationSchedule
from ..services import scheduler_service
from ..services.audit import log_event
from ..services.queue import enqueue_migration
from ..utils.time import utc_now


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/migrations", tags=["schedules"])


# ─── Schemas ─────────────────────────────────────────────────────────


class ScheduleUpsert(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    cron_expr: str = Field(..., min_length=1, max_length=120)
    timezone: str = Field(default="UTC", max_length=64)
    enabled: bool = True


class ScheduleView(BaseModel):
    id: str
    migration_id: str
    name: str
    cron_expr: str
    timezone: str
    enabled: bool
    next_run_at: Optional[str]
    last_run_at: Optional[str]
    last_run_migration_id: Optional[str]
    last_run_status: Optional[str]


class RunNowResult(BaseModel):
    migration_id: str
    job_id: str


# ─── Helpers ─────────────────────────────────────────────────────────


def _view(sched: MigrationSchedule) -> ScheduleView:
    return ScheduleView(
        id=str(sched.id),
        migration_id=str(sched.migration_id),
        name=sched.name,
        cron_expr=sched.cron_expr,
        timezone=sched.timezone,
        enabled=bool(sched.enabled),
        next_run_at=sched.next_run_at.isoformat() if sched.next_run_at else None,
        last_run_at=sched.last_run_at.isoformat() if sched.last_run_at else None,
        last_run_migration_id=(
            str(sched.last_run_migration_id) if sched.last_run_migration_id else None
        ),
        last_run_status=sched.last_run_status,
    )


def _parse_migration_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="migration not found")


def _assert_migration_exists(db: Session, migration_id: uuid.UUID) -> MigrationRecord:
    rec = db.get(MigrationRecord, migration_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="migration not found")
    return rec


# ─── Routes ──────────────────────────────────────────────────────────


@router.get("/{migration_id}/schedule", response_model=ScheduleView)
def get_schedule(
    migration_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role("admin")),
    _license=Depends(require_feature("scheduled_migrations")),
) -> ScheduleView:
    mid = _parse_migration_id(migration_id)
    _assert_migration_exists(db, mid)
    sched = scheduler_service.get_schedule_for_migration(db, mid)
    if sched is None:
        raise HTTPException(status_code=404, detail="no schedule configured")
    return _view(sched)


@router.put("/{migration_id}/schedule", response_model=ScheduleView)
def upsert_schedule(
    migration_id: str,
    body: ScheduleUpsert,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
    _license=Depends(require_feature("scheduled_migrations")),
) -> ScheduleView:
    mid = _parse_migration_id(migration_id)
    _assert_migration_exists(db, mid)
    try:
        sched = scheduler_service.upsert_schedule(
            db,
            mid,
            name=body.name,
            cron_expr=body.cron_expr,
            timezone_name=body.timezone,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    log_event(
        db,
        request=request,
        user=admin,
        action="schedule.upserted",
        resource_type="migration",
        resource_id=str(mid),
        details={
            "name": sched.name,
            "cron_expr": sched.cron_expr,
            "timezone": sched.timezone,
            "enabled": bool(sched.enabled),
            "next_run_at": sched.next_run_at.isoformat(),
        },
    )
    return _view(sched)


@router.delete(
    "/{migration_id}/schedule", status_code=status.HTTP_204_NO_CONTENT
)
def delete_schedule(
    migration_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
    _license=Depends(require_feature("scheduled_migrations")),
) -> None:
    mid = _parse_migration_id(migration_id)
    if not scheduler_service.delete_schedule(db, mid):
        raise HTTPException(status_code=404, detail="no schedule configured")
    log_event(
        db,
        request=request,
        user=admin,
        action="schedule.deleted",
        resource_type="migration",
        resource_id=str(mid),
    )


@router.post(
    "/{migration_id}/schedule/run-now",
    response_model=RunNowResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_now(
    migration_id: str,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_role("admin")),
    _license=Depends(require_feature("scheduled_migrations")),
) -> RunNowResult:
    """Clone the scheduled migration and enqueue it immediately.

    Does not advance next_run_at — the scheduled cadence continues
    independently. Last-run telemetry is updated so the UI shows
    this manual fire alongside automatic fires."""
    mid = _parse_migration_id(migration_id)
    _assert_migration_exists(db, mid)
    sched = scheduler_service.get_schedule_for_migration(db, mid)
    if sched is None:
        raise HTTPException(status_code=404, detail="no schedule configured")

    clone = scheduler_service.clone_from_schedule(db, sched)
    job_id = await enqueue_migration(str(clone.id), background=background)

    sched.last_run_at = utc_now()
    sched.last_run_migration_id = clone.id
    sched.last_run_status = clone.status
    db.commit()

    log_event(
        db,
        request=request,
        user=admin,
        action="schedule.run_now",
        resource_type="migration",
        resource_id=str(mid),
        details={"clone_id": str(clone.id), "job_id": job_id},
    )
    return RunNowResult(migration_id=str(clone.id), job_id=job_id)
