"""Tests for src/auth/password.py.

Locks the bcrypt-direct rewrite so a future revert to passlib (which is
incompatible with bcrypt 5+) gets caught immediately.
"""

import pytest

from src.auth.password import hash_password, verify_password


class TestHashAndVerify:
    def test_round_trip(self):
        h = hash_password("secret123")
        assert verify_password("secret123", h)

    def test_wrong_password_rejected(self):
        h = hash_password("right")
        assert not verify_password("wrong", h)

    def test_hash_is_not_plaintext(self):
        # Trivial sanity check — every bcrypt hash starts with $2b$ or $2a$.
        h = hash_password("anything")
        assert h.startswith("$2")
        assert "anything" not in h

    def test_each_call_produces_different_salt(self):
        # Same input should produce different hashes (random salt) — both verify.
        a = hash_password("dup")
        b = hash_password("dup")
        assert a != b
        assert verify_password("dup", a)
        assert verify_password("dup", b)


class TestUnicodeAndLength:
    def test_unicode_password(self):
        h = hash_password("pässwörd-ünïcödé")
        assert verify_password("pässwörd-ünïcödé", h)
        assert not verify_password("password-unicode", h)

    def test_72_byte_password(self):
        # Right at the bcrypt limit — must work without sha256 prehash.
        pw = "x" * 72
        h = hash_password(pw)
        assert verify_password(pw, h)

    def test_long_password_works_via_sha256_prehash(self):
        # The whole point of the rewrite: passlib + bcrypt 5 raised here.
        pw = "x" * 200
        h = hash_password(pw)
        assert verify_password(pw, h)

    def test_long_passwords_with_different_suffixes_collide_only_by_design(self):
        # Two long passwords that differ in their content produce different
        # hashes (sha256 prehash preserves content distinction).
        a = hash_password("x" * 200 + "alice")
        b = hash_password("x" * 200 + "bob")
        assert a != b
        assert verify_password("x" * 200 + "alice", a)
        assert not verify_password("x" * 200 + "bob", a)


class TestVerifyIsTotallyDefensive:
    def test_empty_hash_returns_false(self):
        assert not verify_password("anything", "")

    def test_garbage_hash_returns_false(self):
        assert not verify_password("anything", "not-a-bcrypt-hash")

    def test_empty_password_against_real_hash(self):
        h = hash_password("real")
        assert not verify_password("", h)
