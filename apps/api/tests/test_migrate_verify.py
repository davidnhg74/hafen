"""Pure-logic tests for the Merkle verifier."""

from __future__ import annotations

import hashlib

import pytest

from src.migrate.verify import (
    TableHash,
    find_first_divergent_batch,
    hash_batch,
    hash_row,
    hash_table,
    merkle_root,
)


# ─── Row hashing ─────────────────────────────────────────────────────────────


class TestHashRow:
    def test_deterministic(self):
        row = (1, "abc", 3.14)
        assert hash_row(row) == hash_row(row)

    def test_int_vs_string_distinguished(self):
        # Same repr but different types must not collide.
        assert hash_row((1,)) != hash_row(("1",))

    def test_column_count_affects_hash(self):
        # `(None,)` vs `(None, None)` must hash differently.
        assert hash_row((None,)) != hash_row((None, None))

    def test_order_matters(self):
        assert hash_row((1, 2)) != hash_row((2, 1))


# ─── Batch hashing ───────────────────────────────────────────────────────────


class TestHashBatch:
    def test_empty_batch_has_stable_hash(self):
        # Two independent calls produce identical bytes.
        assert hash_batch([]) == hash_batch([])
        # And it's just the domain-separator hash — no row contribution.
        assert hash_batch([]) == hashlib.sha256(b"BATCH").digest()

    def test_row_order_changes_batch_hash(self):
        a = hash_batch([(1, "x"), (2, "y")])
        b = hash_batch([(2, "y"), (1, "x")])
        assert a != b


# ─── Merkle root ─────────────────────────────────────────────────────────────


class TestMerkleRoot:
    def test_empty_input_has_marker_root(self):
        assert merkle_root([]) == hashlib.sha256(b"EMPTY").digest()

    def test_single_batch_returns_that_hash(self):
        h = hashlib.sha256(b"only").digest()
        assert merkle_root([h]) == h

    def test_two_batches_combine(self):
        a = hashlib.sha256(b"a").digest()
        b = hashlib.sha256(b"b").digest()
        assert merkle_root([a, b]) == hashlib.sha256(a + b).digest()

    def test_odd_level_duplicates_last(self):
        # Three leaves: H(H(a||b) || H(c||c))
        a = hashlib.sha256(b"a").digest()
        b = hashlib.sha256(b"b").digest()
        c = hashlib.sha256(b"c").digest()
        expected = hashlib.sha256(
            hashlib.sha256(a + b).digest() + hashlib.sha256(c + c).digest()
        ).digest()
        assert merkle_root([a, b, c]) == expected

    def test_changing_one_leaf_changes_root(self):
        a = hashlib.sha256(b"a").digest()
        b = hashlib.sha256(b"b").digest()
        c = hashlib.sha256(b"c").digest()
        bad = hashlib.sha256(b"BAD").digest()
        assert merkle_root([a, b, c]) != merkle_root([a, bad, c])


# ─── End-to-end TableHash ────────────────────────────────────────────────────


class TestHashTable:
    def test_identical_data_same_hash(self):
        batches = [[(1, "a"), (2, "b")], [(3, "c"), (4, "d")]]
        h1 = hash_table(batches)
        h2 = hash_table([list(b) for b in batches])
        assert h1.row_count == 4
        assert h1.matches(h2)

    def test_corrupted_row_detected(self):
        good = [[(1, "a"), (2, "b")]]
        bad = [[(1, "a"), (2, "TAMPERED")]]
        assert not hash_table(good).matches(hash_table(bad))

    def test_row_count_difference_detected(self):
        h_short = hash_table([[(1, "a")]])
        h_long = hash_table([[(1, "a"), (2, "b")]])
        assert not h_short.matches(h_long)

    def test_works_with_generators(self):
        def gen_batches():
            yield iter([(1, "a")])
            yield iter([(2, "b")])

        h = hash_table(gen_batches())
        assert h.row_count == 2


# ─── Divergence finder ───────────────────────────────────────────────────────


class TestFindFirstDivergent:
    def test_identical_returns_none(self):
        a = [hashlib.sha256(str(i).encode()).digest() for i in range(5)]
        assert find_first_divergent_batch(a, a) is None

    def test_finds_middle_corruption(self):
        a = [hashlib.sha256(str(i).encode()).digest() for i in range(5)]
        b = list(a)
        b[2] = hashlib.sha256(b"X").digest()
        assert find_first_divergent_batch(a, b) == 2

    def test_length_mismatch_points_at_surplus(self):
        a = [hashlib.sha256(str(i).encode()).digest() for i in range(3)]
        b = a[:2]
        assert find_first_divergent_batch(a, b) == 2  # index of surplus
        assert find_first_divergent_batch(b, a) == 2
