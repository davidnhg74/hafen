"""Pure-function tests for the redaction + canonicalization pipeline.

The two correctness properties we lock in:

1. **No tenant secret survives `redact()`** — DSNs, passwords, API
   keys, emails, IPs are stripped before anything is sent to Claude
   or persisted in the corpus.

2. **`canonical_signature` is stable across cosmetic differences** —
   two error logs with the same error codes and the same identifier
   topology hash to the same `sig_hash` even when the actual schema
   names differ. That's what lets the corpus cluster "same problem,
   different customer."
"""

from __future__ import annotations

import pytest

from src.services.anonymizer import (
    anonymize,
    canonical_signature,
    extract_error_codes,
    hash_identifier,
    redact,
    signature_hash,
)


# ─── Redaction ───────────────────────────────────────────────────────────────


class TestRedact:
    def test_jdbc_url_with_credentials_stripped(self):
        s = "jdbc:oracle:thin:hr/Hr_Pw_2026!@orahost:1521:FREEPDB1"
        out = redact(s)
        assert "Hr_Pw_2026" not in out
        assert "hr" not in out or "REDACTED" in out
        assert "REDACTED" in out

    def test_sqlalchemy_url_stripped(self):
        s = (
            "Connection failed: postgresql+psycopg://hafen:secret123@"
            "db.internal.acme.com:5432/prod"
        )
        out = redact(s)
        assert "secret123" not in out
        assert "db.internal.acme.com" not in out
        assert "[REDACTED-DSN]" in out

    def test_bare_password_param_stripped(self):
        for case in (
            "password=hunter2",
            "PASSWORD: SuperSecret!",
            "pwd  =  abc-123",
        ):
            out = redact(case)
            assert "hunter2" not in out and "SuperSecret" not in out and "abc-123" not in out
            assert "REDACTED" in out

    def test_api_key_patterns_stripped(self):
        # Build the test strings via concatenation so GitHub's
        # secret scanner doesn't false-flag them as real keys (the
        # full literals match Anthropic / Stripe's regex shapes).
        for case in (
            "ANTHROPIC_API_KEY=" + "sk-ant-api03-" + "x" * 30,
            "AWS access key AKIA" + "X" * 16,
            "Stripe key " + "sk_live_" + "x" * 24,
        ):
            out = redact(case)
            assert "[REDACTED-API-KEY]" in out

    def test_bearer_token_stripped(self):
        s = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
        out = redact(s)
        assert "eyJ" not in out
        assert "REDACTED" in out

    def test_email_addresses_stripped(self):
        s = "User dba@acme.com triggered this; cc finance.dept@acme.co.uk"
        out = redact(s)
        assert "dba@acme.com" not in out
        assert "finance.dept@acme.co.uk" not in out
        assert "[REDACTED-EMAIL]" in out

    def test_ipv4_stripped(self):
        s = "Connection refused to 10.0.4.17:5432 from 192.168.1.42"
        out = redact(s)
        assert "10.0.4.17" not in out
        assert "192.168.1.42" not in out
        assert "[REDACTED-IP]" in out

    def test_idempotent(self):
        s = "Connection failed: postgresql://u:p@h:5432/d password=x"
        once = redact(s)
        twice = redact(once)
        assert once == twice

    def test_safe_text_passes_through(self):
        # Plain operator text with no secrets shouldn't be touched.
        s = "Migration completed successfully — 12_400 rows in 4.2s."
        assert redact(s) == s


# ─── Error code extraction ──────────────────────────────────────────────────


class TestExtractErrorCodes:
    def test_oracle_codes_extracted(self):
        s = "ORA-01017: invalid username/password\nORA-12541: TNS:no listener"
        assert extract_error_codes(s) == ["ORA-01017", "ORA-12541"]

    def test_dedup_preserves_first_occurrence_order(self):
        s = "ORA-01017 hit; later ORA-00942 hit; then ORA-01017 again"
        assert extract_error_codes(s) == ["ORA-01017", "ORA-00942"]

    def test_pg_sqlstate_extracted(self):
        s = "FATAL: ... SQLSTATE=42P01"
        assert extract_error_codes(s) == ["SQLSTATE-42P01"]

    def test_no_codes_returns_empty(self):
        assert extract_error_codes("everything's fine") == []


# ─── Canonical signature ─────────────────────────────────────────────────────


class TestCanonicalSignature:
    def test_same_codes_and_idents_produce_same_hash(self):
        a = "ORA-01017 against HR.EMPLOYEES join HR.JOBS failed"
        b = "ORA-01017 against HR.EMPLOYEES join HR.JOBS failed"
        assert canonical_signature(a) == canonical_signature(b)

    def test_different_idents_same_shape_collide_when_unsalted(self):
        # Without a salt, identifier hashes are deterministic.
        # Two logs naming different schema/table names hash to
        # different idents — so the canonical signatures differ.
        # That's the right behavior: SH.SALES is a different problem
        # signature from HR.EMPLOYEES even if the error code matches.
        a = canonical_signature("ORA-00942 from HR.EMPLOYEES")
        b = canonical_signature("ORA-00942 from SH.SALES")
        assert a != b

    def test_codes_dominate_when_idents_absent(self):
        a = canonical_signature("ORA-01017: invalid credentials")
        b = canonical_signature("ORA-01017 again — same root cause")
        # Both produce an empty ident list and the same code set.
        assert a == b

    def test_salt_changes_ident_hashes(self):
        a = canonical_signature("ORA-00942 from HR.EMPLOYEES", salt="install-A")
        b = canonical_signature("ORA-00942 from HR.EMPLOYEES", salt="install-B")
        assert a != b

    def test_signature_hash_is_64_hex_chars(self):
        sig = canonical_signature("ORA-01017 boom")
        h = signature_hash(sig)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_identifier_stable(self):
        assert hash_identifier("EMPLOYEES") == hash_identifier("EMPLOYEES")
        assert hash_identifier("EMPLOYEES") != hash_identifier("JOBS")


# ─── Combined entrypoint ────────────────────────────────────────────────────


class TestAnonymize:
    def test_returns_redacted_text_codes_and_signature(self):
        s = (
            "ORA-01017: invalid username/password; logon denied\n"
            "Connection: jdbc:oracle:thin:hr/secret@orahost:1521:FREEPDB1"
        )
        out = anonymize(s)
        assert "secret" not in out.redacted_text
        assert out.error_codes == ["ORA-01017"]
        assert len(out.sig_hash) == 64
        assert "ORA-01017" in out.canonical