"""Response dataclasses returned by HafenClient methods.

These mirror the API's response shapes but are intentionally lenient
— unknown fields are accepted (preserved on `.raw`) so a newer API
version doesn't break older SDKs. Only the fields the SDK actively
uses are typed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@dataclass
class MigrationSummary:
    id: str
    name: str | None
    status: str
    source_schema: str | None = None
    target_schema: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationDetail:
    id: str
    name: str | None
    status: str
    source_url: str | None
    target_url: str | None
    source_schema: str | None
    target_schema: str | None
    batch_size: int | None
    rows_transferred: int | None
    total_rows: int | None
    error_message: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Schedule:
    id: str
    migration_id: str
    name: str
    cron_expr: str
    timezone: str
    enabled: bool
    next_run_at: str | None
    last_run_at: str | None
    last_run_status: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Webhook:
    id: str
    name: str
    url_host: str | None
    url_set: bool
    secret_set: bool
    events: list[str]
    enabled: bool
    last_triggered_at: str | None
    last_status: int | None
    last_error: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class MaskingPreview:
    samples: dict[str, list[dict[str, Any]]]
    errors: dict[str, str]


def _pop_known(data: dict, keys: list[str]) -> dict:
    """Return a dict of just the keys we know about, leaving `data`
    intact — callers stash the whole dict into `.raw` for
    forward-compat."""
    return {k: data.get(k) for k in keys}
