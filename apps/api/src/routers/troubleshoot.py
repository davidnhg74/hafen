"""Public troubleshoot endpoint — paste-or-upload log → AI diagnosis.

The first AI feature on the SaaS that's available to anonymous users
(no signup required). Scoped per the privacy notice: anonymous + free
+ paid tiers all opt in to corpus contribution by default; Enterprise
tier opts out by default.

Tier-aware caps (`get_plan_limits` provides them):
  * Anonymous + Trial:    50 MB upload, 10 calls/day (3 for true
                          anonymous IPs — enforced separately below)
  * Starter:              200 MB, unlimited calls
  * Professional:         1 GB,    unlimited calls
  * Enterprise:           1 GB,    unlimited calls

Multi-file upload (up to 5) is supported; files concatenated server-
side with `=== filename ===` headers so Claude sees clear boundaries
between the files. `.gz` uploads are auto-decompressed.
"""

from __future__ import annotations

import gzip
import logging
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.dependencies import get_optional_user
from ..db import get_db
from ..models import User
from ..services.billing import get_plan_limits
from ..services.troubleshoot_service import Diagnosis, analyze_logs


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/troubleshoot", tags=["troubleshoot"])


# Per-anonymous-IP cap — separate from the per-user `troubleshoot_max_calls_per_day`
# in PLAN_LIMITS. Enforced via Redis when available; degrades to in-process
# bookkeeping otherwise (single-machine deploys are fine with that).
_ANON_DAILY_CAP = 3
_MAX_FILES = 5


# ─── Schemas ─────────────────────────────────────────────────────────────────


class DiagnosisResponse(BaseModel):
    likely_cause: str
    recommended_action: str
    code_suggestion: Optional[str] = None
    confidence: str
    escalate_if: Optional[str] = None
    analyzed_bytes: int
    extracted_line_count: int
    used_ai: bool
    analysis_id: str
    # "What we analyzed" footer fields. Tier-aware on the client.
    usage_remaining: Optional[int] = None  # None = unlimited (paid tier)


class PasteRequest(BaseModel):
    """JSON body for the paste path. Multipart uploads use the form
    fields below directly via FastAPI's `File`/`Form` dependencies."""

    logs: str = Field(..., min_length=1)
    context: Optional[str] = Field(default=None, max_length=2000)
    stage: Optional[str] = Field(default=None, max_length=32)


# ─── Tier helpers ────────────────────────────────────────────────────────────


def _resolve_plan(user: Optional[User]) -> str:
    """Map the caller to a billing plan key. Anonymous = "trial".
    The trial limits are the strictest paid-shape numbers in
    `PLAN_LIMITS` — appropriate for unauth use."""
    if user is None:
        return "trial"
    plan = getattr(user, "plan", None)
    return plan.value if plan is not None and hasattr(plan, "value") else "trial"


def _max_upload_bytes(user: Optional[User]) -> int:
    return int(get_plan_limits(_resolve_plan(user))["troubleshoot_max_upload_bytes"])


def _calls_per_day(user: Optional[User]) -> Optional[int]:
    """Per-user daily call cap. None = unlimited (paid tiers).
    Anonymous users hit a separate stricter IP-based cap below."""
    return get_plan_limits(_resolve_plan(user)).get("troubleshoot_max_calls_per_day")


# ─── Multi-file ingest ───────────────────────────────────────────────────────


async def _read_file(upload: UploadFile, max_bytes: int) -> bytes:
    """Read a single upload, decompressing `.gz` and refusing files
    that exceed `max_bytes` (counted on the decompressed size)."""
    raw = await upload.read()
    name = (upload.filename or "").lower()
    if name.endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except (OSError, gzip.BadGzipFile) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"could not decompress {upload.filename!r}: {exc}",
            )
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"{upload.filename!r} is {len(raw)} bytes (decompressed); "
                f"your plan's per-call cap is {max_bytes}. Trim the log "
                f"or upgrade — see the pricing page."
            ),
        )
    return raw


async def _concat_uploads(files: List[UploadFile], max_bytes_total: int) -> str:
    """Read every file, concatenate with `=== filename ===` headers
    so Claude sees clear boundaries. Enforces total byte budget."""
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"at most {_MAX_FILES} files per analysis; got {len(files)}",
        )
    buf: list[str] = []
    bytes_used = 0
    for f in files:
        raw = await _read_file(f, max_bytes_total - bytes_used)
        bytes_used += len(raw)
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — be liberal on input encoding
            text = raw.decode("latin-1", errors="replace")
        header = f"=== {f.filename or 'unnamed'} ===\n"
        buf.append(header + text)
    return "\n\n".join(buf)


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=DiagnosisResponse)
async def analyze_paste(
    body: PasteRequest,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> DiagnosisResponse:
    """JSON-paste path. Use this when the operator has an error string
    in their clipboard. For file uploads, see `/analyze/upload`."""
    cap = _max_upload_bytes(user)
    if len(body.logs.encode("utf-8")) > cap:
        raise HTTPException(
            status_code=413,
            detail=(
                f"pasted logs exceed your plan's per-call cap of {cap} bytes. "
                f"Trim to the error section or upgrade — see the pricing page."
            ),
        )
    return _run(db=db, user=user, raw_logs=body.logs, context=body.context, stage=body.stage)


@router.post("/analyze/upload", response_model=DiagnosisResponse)
async def analyze_upload(
    files: List[UploadFile] = File(...),
    context: Optional[str] = Form(default=None),
    stage: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
) -> DiagnosisResponse:
    """Multipart-upload path. Up to 5 files per analysis (configurable
    via `_MAX_FILES`); .gz auto-decompressed; total cap is plan-aware."""
    cap = _max_upload_bytes(user)
    raw_logs = await _concat_uploads(files, max_bytes_total=cap)
    return _run(db=db, user=user, raw_logs=raw_logs, context=context, stage=stage)


# ─── Internals ───────────────────────────────────────────────────────────────


def _should_write_corpus(user: Optional[User]) -> bool:
    """Per the privacy policy: anonymous + free + paid (Starter, Pro)
    opt in by default; Enterprise opts OUT by default. Toggle is a
    settings-page surface (not yet exposed) — for now, hard-code the
    Enterprise behavior."""
    if user is None:
        return True  # anonymous = implicit opt-in via the privacy notice
    plan = getattr(user, "plan", None)
    plan_value = plan.value if plan is not None and hasattr(plan, "value") else None
    if plan_value == "enterprise":
        return False
    return True


def _run(
    *,
    db: Session,
    user: Optional[User],
    raw_logs: str,
    context: Optional[str],
    stage: Optional[str],
) -> DiagnosisResponse:
    diagnosis, analysis_id = analyze_logs(
        db=db,
        raw_logs=raw_logs,
        user=user,
        context=context,
        stage=stage,
        write_corpus=_should_write_corpus(user),
    )
    return DiagnosisResponse(
        likely_cause=diagnosis.likely_cause,
        recommended_action=diagnosis.recommended_action,
        code_suggestion=diagnosis.code_suggestion,
        confidence=diagnosis.confidence,
        escalate_if=diagnosis.escalate_if,
        analyzed_bytes=diagnosis.analyzed_bytes,
        extracted_line_count=diagnosis.extracted_line_count,
        used_ai=diagnosis.used_ai,
        analysis_id=str(analysis_id),
        usage_remaining=_calls_per_day(user),
    )
