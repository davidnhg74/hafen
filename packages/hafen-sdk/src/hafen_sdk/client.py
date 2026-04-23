"""HafenClient — programmatic access to a self-hosted Hafen install.

Mirrors the REST surface under ``/api/v1/*`` with typed Python
methods. Auth is bearer-token; the client will auto-log-in if
constructed with ``email + password``. Errors are raised as typed
exceptions (``HafenError`` hierarchy) so callers can match on
``LicenseError``, ``NotFoundError``, etc. rather than inspecting
HTTP status codes by hand.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx

from .errors import (
    AuthError,
    HafenError,
    LicenseError,
    NotFoundError,
    ServerError,
    ValidationError,
)
from .models import (
    MaskingPreview,
    MigrationDetail,
    MigrationSummary,
    Schedule,
    TokenPair,
    Webhook,
)


DEFAULT_TIMEOUT = 30.0


class HafenClient:
    """Entry point to the Hafen REST API.

    Construct with either an explicit bearer token::

        client = HafenClient("https://hafen.internal", access_token="eyJ…")

    or with credentials (the client will POST /auth/login for you)::

        client = HafenClient("https://hafen.internal",
                             email="admin@co.com", password="…")

    Pass ``transport=httpx.MockTransport(...)`` for testing.
    """

    def __init__(
        self,
        base_url: str,
        *,
        access_token: Optional[str] = None,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        transport: Optional[httpx.BaseTransport] = None,
    ):
        if access_token is None and not (email and password):
            raise ValueError(
                "HafenClient requires either access_token or (email, password)"
            )
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            transport=transport,
        )
        self._token: Optional[str] = access_token
        if self._token is None:
            # email/password already validated above
            self._token = self.login(email, password).access_token  # type: ignore[arg-type]

    # ── lifecycle ──────────────────────────────────────────────────

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "HafenClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ── HTTP plumbing ──────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "hafen-sdk/0.1"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict | None = None,
    ) -> Any:
        resp = self._http.request(
            method, path, json=json, params=params, headers=self._headers()
        )
        return self._parse(resp)

    @staticmethod
    def _parse(resp: httpx.Response) -> Any:
        # 2xx: return parsed body (or None for 204)
        if 200 <= resp.status_code < 300:
            if resp.status_code == 204 or not resp.content:
                return None
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                return resp.json()
            return resp.text

        # Error path — map HTTP status → typed exception.
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = resp.text or None
        detail = body.get("detail") if isinstance(body, dict) else body
        msg = f"{resp.status_code} {resp.reason_phrase or ''}".strip()

        cls: type[HafenError]
        if resp.status_code in (401, 403):
            cls = AuthError
        elif resp.status_code == 402:
            cls = LicenseError
        elif resp.status_code == 404:
            cls = NotFoundError
        elif resp.status_code == 400 or resp.status_code == 422:
            cls = ValidationError
        elif 500 <= resp.status_code < 600:
            cls = ServerError
        else:
            cls = HafenError
        raise cls(msg, status_code=resp.status_code, detail=detail)

    # ── auth ───────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> TokenPair:
        """POST /api/v1/auth/login — returns and stores a bearer
        token. Called automatically when the client is constructed
        with (email, password)."""
        body = self._request(
            "POST",
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        token = TokenPair(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", ""),
            token_type=body.get("token_type", "bearer"),
        )
        self._token = token.access_token
        return token

    # ── migrations ────────────────────────────────────────────────

    def list_migrations(self) -> list[MigrationSummary]:
        data = self._request("GET", "/api/v1/migrations")
        return [_to_summary(d) for d in data or []]

    def create_migration(
        self,
        *,
        name: str,
        source_url: str,
        target_url: str,
        schema_name: Optional[str] = None,
        source_schema: Optional[str] = None,
        target_schema: Optional[str] = None,
        tables: Optional[list[str]] = None,
        batch_size: int = 5000,
        create_tables: bool = False,
    ) -> MigrationSummary:
        body: dict[str, Any] = {
            "name": name,
            "source_url": source_url,
            "target_url": target_url,
            "batch_size": batch_size,
            "create_tables": create_tables,
        }
        if schema_name is not None:
            body["schema_name"] = schema_name
        if source_schema is not None:
            body["source_schema"] = source_schema
        if target_schema is not None:
            body["target_schema"] = target_schema
        if tables is not None:
            body["tables"] = tables
        return _to_summary(self._request("POST", "/api/v1/migrations", json=body))

    def get_migration(self, migration_id: str) -> MigrationDetail:
        data = self._request("GET", f"/api/v1/migrations/{migration_id}")
        return _to_detail(data)

    def run_migration(self, migration_id: str) -> MigrationSummary:
        data = self._request("POST", f"/api/v1/migrations/{migration_id}/run")
        return _to_summary(data)

    def get_progress(self, migration_id: str) -> list[dict[str, Any]]:
        """Per-table checkpoint rows. Shape is documented in the API
        but left loose here so new fields flow through."""
        return self._request("GET", f"/api/v1/migrations/{migration_id}/progress") or []

    def delete_migration(self, migration_id: str) -> None:
        self._request("DELETE", f"/api/v1/migrations/{migration_id}")

    # ── schedules ─────────────────────────────────────────────────

    def get_schedule(self, migration_id: str) -> Optional[Schedule]:
        try:
            data = self._request(
                "GET", f"/api/v1/migrations/{migration_id}/schedule"
            )
        except NotFoundError:
            return None
        return _to_schedule(data)

    def upsert_schedule(
        self,
        migration_id: str,
        *,
        name: str,
        cron_expr: str,
        timezone: str = "UTC",
        enabled: bool = True,
    ) -> Schedule:
        data = self._request(
            "PUT",
            f"/api/v1/migrations/{migration_id}/schedule",
            json={
                "name": name,
                "cron_expr": cron_expr,
                "timezone": timezone,
                "enabled": enabled,
            },
        )
        return _to_schedule(data)

    def delete_schedule(self, migration_id: str) -> None:
        self._request("DELETE", f"/api/v1/migrations/{migration_id}/schedule")

    def run_schedule_now(self, migration_id: str) -> dict[str, Any]:
        """Clone the scheduled migration and enqueue immediately.
        Returns the API's {migration_id, job_id} shape."""
        return self._request(
            "POST", f"/api/v1/migrations/{migration_id}/schedule/run-now"
        )

    # ── webhooks ──────────────────────────────────────────────────

    def list_webhooks(self) -> list[Webhook]:
        data = self._request("GET", "/api/v1/webhooks")
        return [_to_webhook(d) for d in data or []]

    def create_webhook(
        self,
        *,
        name: str,
        url: str,
        events: list[str],
        secret: Optional[str] = None,
        enabled: bool = True,
    ) -> Webhook:
        body = {
            "name": name,
            "url": url,
            "events": events,
            "enabled": enabled,
        }
        if secret is not None:
            body["secret"] = secret
        return _to_webhook(self._request("POST", "/api/v1/webhooks", json=body))

    def get_webhook(self, webhook_id: str) -> Webhook:
        return _to_webhook(self._request("GET", f"/api/v1/webhooks/{webhook_id}"))

    def update_webhook(
        self,
        webhook_id: str,
        *,
        name: Optional[str] = None,
        url: Optional[str] = None,
        secret: Optional[str] = None,
        events: Optional[list[str]] = None,
        enabled: Optional[bool] = None,
    ) -> Webhook:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if url is not None:
            body["url"] = url
        if secret is not None:
            body["secret"] = secret
        if events is not None:
            body["events"] = events
        if enabled is not None:
            body["enabled"] = enabled
        return _to_webhook(
            self._request("PATCH", f"/api/v1/webhooks/{webhook_id}", json=body)
        )

    def delete_webhook(self, webhook_id: str) -> None:
        self._request("DELETE", f"/api/v1/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/webhooks/{webhook_id}/test")

    # ── masking ───────────────────────────────────────────────────

    def get_masking(self, migration_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/api/v1/migrations/{migration_id}/masking")
        return (data or {}).get("rules", {}) or {}

    def put_masking(
        self, migration_id: str, rules: dict[str, Any]
    ) -> dict[str, Any]:
        data = self._request(
            "PUT",
            f"/api/v1/migrations/{migration_id}/masking",
            json={"rules": rules},
        )
        return (data or {}).get("rules", {}) or {}

    def delete_masking(self, migration_id: str) -> None:
        self._request("DELETE", f"/api/v1/migrations/{migration_id}/masking")

    def preview_masking(
        self, migration_id: str, sample_size: int = 5
    ) -> MaskingPreview:
        data = self._request(
            "POST",
            f"/api/v1/migrations/{migration_id}/masking/preview",
            json={"sample_size": sample_size},
        )
        return MaskingPreview(
            samples=data.get("samples", {}) or {},
            errors=data.get("errors", {}) or {},
        )


# ── response coercion helpers ─────────────────────────────────────


def _to_summary(d: dict[str, Any]) -> MigrationSummary:
    return MigrationSummary(
        id=d["id"],
        name=d.get("name"),
        status=d["status"],
        source_schema=d.get("source_schema"),
        target_schema=d.get("target_schema"),
        raw=dict(d),
    )


def _to_detail(d: dict[str, Any]) -> MigrationDetail:
    return MigrationDetail(
        id=d["id"],
        name=d.get("name"),
        status=d["status"],
        source_url=d.get("source_url"),
        target_url=d.get("target_url"),
        source_schema=d.get("source_schema"),
        target_schema=d.get("target_schema"),
        batch_size=d.get("batch_size"),
        rows_transferred=d.get("rows_transferred"),
        total_rows=d.get("total_rows"),
        error_message=d.get("error_message"),
        raw=dict(d),
    )


def _to_schedule(d: dict[str, Any]) -> Schedule:
    return Schedule(
        id=d["id"],
        migration_id=d["migration_id"],
        name=d["name"],
        cron_expr=d["cron_expr"],
        timezone=d["timezone"],
        enabled=d["enabled"],
        next_run_at=d.get("next_run_at"),
        last_run_at=d.get("last_run_at"),
        last_run_status=d.get("last_run_status"),
        raw=dict(d),
    )


def _to_webhook(d: dict[str, Any]) -> Webhook:
    return Webhook(
        id=d["id"],
        name=d["name"],
        url_host=d.get("url_host"),
        url_set=d["url_set"],
        secret_set=d["secret_set"],
        events=list(d.get("events", [])),
        enabled=d["enabled"],
        last_triggered_at=d.get("last_triggered_at"),
        last_status=d.get("last_status"),
        last_error=d.get("last_error"),
        raw=dict(d),
    )
