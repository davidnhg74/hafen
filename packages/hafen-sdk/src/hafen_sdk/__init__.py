"""hafen-sdk — Python client for the Hafen migration platform."""

from .client import HafenClient
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

__all__ = [
    "HafenClient",
    "HafenError",
    "AuthError",
    "LicenseError",
    "NotFoundError",
    "ServerError",
    "ValidationError",
    "MaskingPreview",
    "MigrationDetail",
    "MigrationSummary",
    "Schedule",
    "TokenPair",
    "Webhook",
]

__version__ = "0.1.0"
