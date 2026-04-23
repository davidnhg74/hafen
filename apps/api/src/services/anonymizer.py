"""Redaction + canonicalization pipeline for the troubleshoot service.

Two responsibilities:

1. **Redaction** — strip values that would either compromise the
   submitting tenant's confidentiality (DSNs with passwords, hostnames,
   API keys) or that wouldn't be useful in the corpus anyway (line
   numbers, transient timestamps). Done BEFORE any payload reaches
   the AI client.

2. **Canonicalization** — turn a heterogeneous error log into stable
   features that can be hashed for the Plane-2 corpus:
     * extracted error CODES (ORA-01017, etc.) — kept verbatim because
       they're universal
     * a table-shape signature (column types, PK arity, LOB presence)
       — derived from any DDL or table identifiers in the input, with
       actual names hashed away
     * an error_signature_hash — SHA-256 over the canonicalized form,
       so "same problem, different customer" clusters together

Pure functions; no DB, no network. Tests in `test_anonymizer.py`
exercise the redaction patterns + signature stability properties.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List


# ─── Redaction patterns ──────────────────────────────────────────────────────

# Each pattern matches something we never want to send to Claude or
# persist in the corpus. Order matters — more-specific patterns first
# so they don't get partially-eaten by broader ones (e.g. JDBC URL
# before bare `password=`).
_REDACT_PATTERNS: List[tuple[re.Pattern, str]] = [
    # JDBC URLs with embedded credentials.
    # jdbc:oracle:thin:user/pass@host:port:sid → jdbc:oracle:thin:[REDACTED-DSN]
    (re.compile(r"jdbc:[\w]+:[\w]+:[^/\s]+/[^@\s]+@[^\s'\"]+", re.IGNORECASE),
     "jdbc:[REDACTED-DSN]"),
    # SQLAlchemy-style URLs.
    # postgresql+psycopg://user:pass@host:5432/db → [REDACTED-DSN]
    (re.compile(r"\b(?:oracle|postgres(?:ql)?(?:\+\w+)?|mysql|mssql)://[^\s'\";]+",
                re.IGNORECASE),
     "[REDACTED-DSN]"),
    # Bare password=... fragments (URL params, CLI args, conn-string entries).
    (re.compile(r"\b(password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
     r"\1=[REDACTED]"),
    # API keys — common prefixes (sk-, sk_test_, ghp_, AKIA, etc.).
    (re.compile(r"\b(sk-[a-zA-Z0-9_\-]{20,}|sk_(?:test|live)_[a-zA-Z0-9_]{20,}"
                r"|ghp_[a-zA-Z0-9]{20,}|AKIA[A-Z0-9]{16})\b"),
     "[REDACTED-API-KEY]"),
    # Bearer tokens in HTTP headers — handle the full
    # `Authorization: Bearer <jwt>` shape AND a bare `Bearer <jwt>`.
    (re.compile(r"\bAuthorization\s*:\s*Bearer\s+\S+", re.IGNORECASE),
     "Authorization: Bearer [REDACTED-TOKEN]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
     "Bearer [REDACTED-TOKEN]"),
    # Email addresses — rough but acceptable. We don't want to leak
    # individual users' emails into the corpus.
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"),
     "[REDACTED-EMAIL]"),
    # IPv4 addresses with no-context surrounding text. Loose; acceptable
    # to over-redact internal IPs.
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"),
     "[REDACTED-IP]"),
]


def redact(text: str) -> str:
    """Apply every redaction pattern. Idempotent — running twice
    produces the same output. Errors fall through unchanged rather
    than crashing the caller."""
    out = text
    for pattern, replacement in _REDACT_PATTERNS:
        try:
            out = pattern.sub(replacement, out)
        except re.error:
            continue
    return out


# ─── Canonicalization ────────────────────────────────────────────────────────


# Oracle errors look like ORA-01017, ORA-00942. Postgres uses 5-char
# alphanumeric SQLSTATE (e.g. 42P01). Keep both shapes verbatim — the
# codes are universal and the most useful clustering signal.
_ORA_CODE = re.compile(r"\bORA-\d{5}\b")
_PG_SQLSTATE = re.compile(r"\bSQLSTATE\s*[:=]?\s*([0-9A-Z]{5})\b", re.IGNORECASE)


def extract_error_codes(text: str) -> List[str]:
    """Pull out every Oracle ORA- / Postgres SQLSTATE code in the
    input. Deduplicated, order-preserving so repeated errors don't
    bloat the signature."""
    seen: List[str] = []
    for m in _ORA_CODE.finditer(text):
        code = m.group(0)
        if code not in seen:
            seen.append(code)
    for m in _PG_SQLSTATE.finditer(text):
        code = f"SQLSTATE-{m.group(1).upper()}"
        if code not in seen:
            seen.append(code)
    return seen


# Identifier shapes in error messages — quoted "FOO"."BAR" or bare
# FOO.BAR.BAZ. We hash the names with a per-call salt so the corpus
# never carries customer-specific identifiers verbatim.
_QUOTED_QN = re.compile(r'"([\w$#]+)"(?:\."([\w$#]+)")?(?:\."([\w$#]+)")?')
_BARE_QN = re.compile(r"\b([A-Z][A-Z0-9_$#]{2,})(?:\.([A-Z][A-Z0-9_$#]+))?(?:\.([A-Z][A-Z0-9_$#]+))?\b")


def hash_identifier(name: str, salt: str = "") -> str:
    """Stable per-(name,salt) hash. 8 hex chars is enough to keep
    collisions rare in practice and short enough that operators
    eyeballing the corpus still see something readable."""
    return hashlib.sha256(f"{salt}:{name}".encode("utf-8")).hexdigest()[:8]


def canonical_signature(text: str, salt: str = "") -> str:
    """Reduce an error blob to a stable signature string.

    Strategy:
      * extract error codes (kept verbatim)
      * extract identifier-shaped tokens, hash them with the salt
      * join into a sortable, deduplicated representation

    Two inputs with the same codes and the same identifier topology
    (different names but same shape) produce the same signature —
    which is exactly what we want for clustering "same problem,
    different schema."
    """
    codes = sorted(set(extract_error_codes(text)))

    ident_hashes: List[str] = []
    seen_idents: set[str] = set()
    for m in _QUOTED_QN.finditer(text):
        for grp in m.groups():
            if grp and grp not in seen_idents:
                seen_idents.add(grp)
                ident_hashes.append(hash_identifier(grp, salt))
    for m in _BARE_QN.finditer(text):
        for grp in m.groups():
            if grp and len(grp) >= 3 and grp not in seen_idents:
                seen_idents.add(grp)
                ident_hashes.append(hash_identifier(grp, salt))
    ident_hashes.sort()

    return f"codes={','.join(codes)};idents={','.join(ident_hashes)}"


def signature_hash(canonical: str) -> str:
    """SHA-256 of the canonical signature, full hex. Used as the
    corpus row's `error_signature_hash` column — clustering happens
    via equality on this field."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ─── Public combined entrypoint ──────────────────────────────────────────────


@dataclass(frozen=True)
class AnonymizedInput:
    """Result of a single anonymization pass. `redacted_text` is what
    gets fed to Claude (and stored in Plane 1's `input_excerpt`).
    The signature fields populate Plane 2's `corpus_entries` row."""

    redacted_text: str
    error_codes: List[str]
    canonical: str
    sig_hash: str


def anonymize(text: str, salt: str = "") -> AnonymizedInput:
    """One-shot redaction + signature derivation for a log payload."""
    redacted = redact(text)
    codes = extract_error_codes(redacted)
    canonical = canonical_signature(redacted, salt=salt)
    return AnonymizedInput(
        redacted_text=redacted,
        error_codes=codes,
        canonical=canonical,
        sig_hash=signature_hash(canonical),
    )
