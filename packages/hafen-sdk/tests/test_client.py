"""Unit tests for HafenClient using httpx.MockTransport.

No real server; every test wires a transport that inspects the
outgoing request and returns a canned response. This keeps the
tests hermetic and fast.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from hafen_sdk import (
    AuthError,
    HafenClient,
    LicenseError,
    NotFoundError,
    ValidationError,
)


# ─── Helpers ─────────────────────────────────────────────────────────


def _mk_transport(handler):
    return httpx.MockTransport(handler)


def _mk_client(handler, *, with_token: str | None = "tkn") -> HafenClient:
    return HafenClient(
        base_url="https://h.example.com",
        access_token=with_token,
        transport=_mk_transport(handler),
    )


# ─── Auth ────────────────────────────────────────────────────────────


def test_constructor_requires_auth():
    with pytest.raises(ValueError):
        HafenClient(base_url="https://h.example.com")


def test_login_via_credentials_exchanges_tokens():
    captured: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        captured.append(req)
        return httpx.Response(
            200,
            json={
                "access_token": "the-bearer-token",
                "refresh_token": "refresh-abc",
                "token_type": "bearer",
            },
        )

    c = HafenClient(
        base_url="https://h.example.com",
        email="admin@acme.com",
        password="s3cret",
        transport=_mk_transport(handler),
    )

    assert len(captured) == 1
    assert captured[0].method == "POST"
    assert captured[0].url.path == "/api/v1/auth/login"
    body = json.loads(captured[0].content)
    assert body == {"email": "admin@acme.com", "password": "s3cret"}
    # Subsequent calls include the bearer token
    assert c._token == "the-bearer-token"  # type: ignore[attr-defined]


def test_bearer_header_sent_on_subsequent_calls():
    seen_auth: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen_auth.append(req.headers.get("Authorization", ""))
        if req.url.path == "/api/v1/auth/login":
            return httpx.Response(
                200,
                json={"access_token": "T", "refresh_token": "R", "token_type": "bearer"},
            )
        return httpx.Response(200, json=[])

    c = HafenClient(
        base_url="https://h.example.com",
        email="a@b.c",
        password="x",
        transport=_mk_transport(handler),
    )
    c.list_migrations()
    # login call has no prior token; list call does
    assert seen_auth == ["", "Bearer T"]


# ─── Error mapping ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status, cls",
    [
        (401, AuthError),
        (403, AuthError),
        (402, LicenseError),
        (404, NotFoundError),
        (400, ValidationError),
        (422, ValidationError),
    ],
)
def test_http_errors_map_to_typed_exceptions(status, cls):
    def handler(_req):
        return httpx.Response(status, json={"detail": "nope"})

    c = _mk_client(handler)
    with pytest.raises(cls) as exc_info:
        c.list_migrations()
    assert exc_info.value.status_code == status
    assert exc_info.value.detail == "nope"


def test_license_error_preserves_structured_detail():
    def handler(_req):
        return httpx.Response(
            402,
            json={"detail": {"error": "license_required", "feature": "webhooks"}},
        )

    c = _mk_client(handler)
    with pytest.raises(LicenseError) as exc_info:
        c.list_webhooks()
    assert exc_info.value.detail["feature"] == "webhooks"


# ─── Migrations ──────────────────────────────────────────────────────


def test_create_migration_round_trip():
    received: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        received.append(
            {
                "method": req.method,
                "path": req.url.path,
                "body": json.loads(req.content) if req.content else None,
            }
        )
        return httpx.Response(
            201,
            json={
                "id": "mig-1",
                "name": "nightly",
                "status": "pending",
                "source_schema": "HR",
                "target_schema": "hr",
            },
        )

    c = _mk_client(handler)
    m = c.create_migration(
        name="nightly",
        source_url="oracle://a",
        target_url="postgresql+psycopg://b",
        source_schema="HR",
        target_schema="hr",
        batch_size=1000,
        create_tables=True,
    )

    assert received[0]["path"] == "/api/v1/migrations"
    assert received[0]["body"]["name"] == "nightly"
    assert received[0]["body"]["batch_size"] == 1000
    assert m.id == "mig-1"
    assert m.status == "pending"


def test_list_migrations_empty():
    def handler(_req):
        return httpx.Response(200, json=[])

    assert _mk_client(handler).list_migrations() == []


def test_run_migration_returns_summary():
    def handler(req):
        assert req.method == "POST"
        assert req.url.path == "/api/v1/migrations/m-1/run"
        return httpx.Response(202, json={"id": "m-1", "name": "x", "status": "queued"})

    assert _mk_client(handler).run_migration("m-1").status == "queued"


# ─── Schedules ───────────────────────────────────────────────────────


def test_upsert_schedule_passes_fields_through():
    captured: list[dict] = []

    def handler(req):
        captured.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                "id": "sch-1",
                "migration_id": "m-1",
                "name": "nightly",
                "cron_expr": "0 2 * * *",
                "timezone": "America/New_York",
                "enabled": True,
                "next_run_at": "2026-04-24T06:00:00",
                "last_run_at": None,
                "last_run_migration_id": None,
                "last_run_status": None,
            },
        )

    s = _mk_client(handler).upsert_schedule(
        "m-1",
        name="nightly",
        cron_expr="0 2 * * *",
        timezone="America/New_York",
    )
    assert captured[0]["cron_expr"] == "0 2 * * *"
    assert s.timezone == "America/New_York"


def test_get_schedule_returns_none_on_404():
    def handler(_req):
        return httpx.Response(404, json={"detail": "no schedule"})

    assert _mk_client(handler).get_schedule("m-1") is None


# ─── Webhooks ────────────────────────────────────────────────────────


def test_create_webhook_sends_events_list():
    sent: list[dict] = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(
            201,
            json={
                "id": "wh-1",
                "name": "ops-slack",
                "url_host": "hooks.slack.com",
                "url_set": True,
                "secret_set": True,
                "events": ["migration.completed"],
                "enabled": True,
                "last_triggered_at": None,
                "last_status": None,
                "last_error": None,
            },
        )

    w = _mk_client(handler).create_webhook(
        name="ops-slack",
        url="https://hooks.slack.com/…",
        secret="shh",
        events=["migration.completed"],
    )
    assert sent[0]["events"] == ["migration.completed"]
    assert w.url_host == "hooks.slack.com"
    assert w.secret_set is True


def test_update_webhook_only_sends_changed_fields():
    sent: list[dict] = []

    def handler(req):
        sent.append(json.loads(req.content))
        return httpx.Response(
            200,
            json={
                "id": "wh-1",
                "name": "x",
                "url_host": "h",
                "url_set": True,
                "secret_set": False,
                "events": [],
                "enabled": False,
                "last_triggered_at": None,
                "last_status": None,
                "last_error": None,
            },
        )

    _mk_client(handler).update_webhook("wh-1", enabled=False)
    assert sent[0] == {"enabled": False}


# ─── Masking ─────────────────────────────────────────────────────────


def test_put_masking_round_trip():
    captured: list[dict] = []

    def handler(req):
        captured.append(json.loads(req.content))
        return httpx.Response(200, json={"rules": captured[-1]["rules"]})

    rules = {"HR.USERS": {"EMAIL": {"strategy": "hash"}}}
    out = _mk_client(handler).put_masking("m-1", rules)
    assert out == rules


def test_preview_masking_returns_samples():
    def handler(_req):
        return httpx.Response(
            200,
            json={
                "samples": {"HR.USERS": [{"id": 1, "email": "deadbeef"}]},
                "errors": {},
            },
        )

    p = _mk_client(handler).preview_masking("m-1", sample_size=3)
    assert "HR.USERS" in p.samples
    assert p.samples["HR.USERS"][0]["email"] == "deadbeef"
    assert p.errors == {}


# ─── Context manager ─────────────────────────────────────────────────


def test_client_closes_cleanly():
    def handler(_req):
        return httpx.Response(200, json=[])

    with _mk_client(handler) as c:
        c.list_migrations()
    # no assert needed — just verify it doesn't explode
