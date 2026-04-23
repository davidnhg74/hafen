"""Typed exceptions raised by HafenClient."""

from __future__ import annotations

from typing import Any


class HafenError(Exception):
    """Base for everything this SDK raises. Carries the HTTP status,
    the parsed response body (if any), and the raw detail so callers
    can inspect specifics without another round-trip.

    All the more specific subclasses in this module are `HafenError`,
    so catching `HafenError` handles everything the API can surface."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class AuthError(HafenError):
    """401/403 — missing, expired, or insufficient credentials."""


class LicenseError(HafenError):
    """402 — the endpoint requires a licensed feature. `.detail` is
    the API's structured body, typically including the `feature`
    field so the caller knows which license tier unblocks them."""


class NotFoundError(HafenError):
    """404 — the addressed resource doesn't exist."""


class ValidationError(HafenError):
    """400 — the request was malformed (invalid cron, unknown event
    name, bad URL, etc.). `.detail` is the API's response body."""


class ServerError(HafenError):
    """5xx — the server choked. Worth retrying with backoff."""
