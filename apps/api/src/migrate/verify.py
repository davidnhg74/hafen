"""Merkle-hash verification for data movement.

Row counts catch missing rows; they don't catch corrupted ones. Hashing
each row would catch corruption but doesn't tell you *where* the
corruption is. Merkle hashing — where each batch's hash combines into a
single root — gives you both:

  • Compare roots; if they match, the entire table is bit-identical.
  • If they differ, walk the tree to find the offending batch in
    O(log n) hashes instead of O(n) row comparisons.

This module provides the pure hash plumbing. The runner is responsible
for actually reading the rows from each side and feeding row-tuples in
batch-shaped chunks. Both sides must use the same row serializer and
the same batch boundaries (defined by the keyset cursor) — otherwise
the hashes diverge for innocent reasons.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List, Sequence


# ─── Row + batch hashing ─────────────────────────────────────────────────────


def hash_row(values: Sequence) -> bytes:
    """SHA-256 over a canonical serialization of the row.

    Canonical means stable across runs and dialects:
      • each value rendered with `repr()` plus its type tag (so `1` and
        `'1'` differ);
      • values joined by NUL (a byte that can't appear in repr output);
      • prefixed with the column count to defeat tuple-vs-tuple-with-
        trailing-NULL ambiguity.

    Yes, repr() is Python-specific. That's fine — both sides of the
    verifier run in the same Python process. The day this becomes a
    cross-runtime check, swap to a binary canonical-form like CBOR.
    """
    parts: List[bytes] = [str(len(values)).encode()]
    for v in values:
        parts.append(type(v).__name__.encode())
        parts.append(repr(v).encode())
    return hashlib.sha256(b"\x00".join(parts)).digest()


def hash_batch(rows: Iterable[Sequence]) -> bytes:
    """Compose row hashes into a single batch hash. We chain via SHA-256
    (`H(prev || H(row))`) so any reordering changes the result — which
    is correct, since both sides walk the table by the same keyset
    order."""
    h = hashlib.sha256()
    h.update(b"BATCH")  # domain separator
    for row in rows:
        h.update(hash_row(row))
    return h.digest()


# ─── Merkle tree over batches ────────────────────────────────────────────────


def merkle_root(batch_hashes: Sequence[bytes]) -> bytes:
    """Build a binary Merkle tree from `batch_hashes` and return the
    root. Empty input → SHA-256 of the empty marker. Odd-length levels
    duplicate the last hash (Bitcoin-style) — simple and avoids the
    distinct-empty-leaf trap."""
    if not batch_hashes:
        return hashlib.sha256(b"EMPTY").digest()

    level: List[bytes] = list(batch_hashes)
    while len(level) > 1:
        nxt: List[bytes] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            nxt.append(hashlib.sha256(left + right).digest())
        level = nxt
    return level[0]


@dataclass
class TableHash:
    """Per-table verification artifact. `row_count` lets the caller make
    a cheap pre-check; `root` is the Merkle root for the full bitwise
    check."""

    row_count: int
    root: bytes

    def matches(self, other: "TableHash") -> bool:
        return self.row_count == other.row_count and self.root == other.root


def hash_table(batches: Iterable[Iterable[Sequence]]) -> TableHash:
    """Compose batch-by-batch row data into a TableHash. Iterates
    `batches` once — works with generators that stream from the DB."""
    batch_hashes: List[bytes] = []
    total_rows = 0
    for batch in batches:
        materialized = list(batch)
        total_rows += len(materialized)
        batch_hashes.append(hash_batch(materialized))
    return TableHash(row_count=total_rows, root=merkle_root(batch_hashes))


# ─── Diff helper for forensic mode ───────────────────────────────────────────


def find_first_divergent_batch(
    src_batch_hashes: Sequence[bytes],
    dst_batch_hashes: Sequence[bytes],
) -> int | None:
    """When the roots differ, locate the first batch index whose hash
    doesn't match. Returns None if the sequences are identical (caller
    should then use this to bisect rows inside the bad batch)."""
    common = min(len(src_batch_hashes), len(dst_batch_hashes))
    for i in range(common):
        if src_batch_hashes[i] != dst_batch_hashes[i]:
            return i
    if len(src_batch_hashes) != len(dst_batch_hashes):
        # Length mismatch — the first surplus batch is the divergence.
        return common
    return None
