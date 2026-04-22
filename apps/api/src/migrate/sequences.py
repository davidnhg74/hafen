"""Postgres sequence catch-up after a bulk load.

When we COPY rows that already carry the parent's `id`, Postgres
sequences (whether `SERIAL`, `IDENTITY`, or explicit `SEQUENCE`s) stay
at their initial value. The very next INSERT that asks the sequence
for a default `nextval()` will collide with a row we already loaded.

Catch-up advances every owned sequence to `MAX(owning_column) + 1`. We
walk `pg_depend` to find the (sequence, table, column) triples — that
also picks up sequences attached to non-`SERIAL` columns through
`ALTER SEQUENCE ... OWNED BY`, which is the manual pattern operators
sometimes use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class SequenceLink:
    """One (sequence, owning table.column) tuple."""

    sequence: str  # schema-qualified
    table: str  # schema-qualified
    column: str


@dataclass
class CatchupResult:
    """Per-sequence outcome — what value we set, or why we skipped."""

    link: SequenceLink
    set_to: int | None  # None when the table is empty
    skipped_reason: str | None = None


def discover_owned_sequences(pg_conn, schema: str = "public") -> List[SequenceLink]:
    """List every sequence in `schema` whose ownership chain points at a
    column. Sequences without an owner (free-standing) are out of scope —
    catching them up is meaningless without an associated table column.
    """
    sql = """
        SELECT
            seq_ns.nspname || '.' || seq.relname AS sequence,
            tab_ns.nspname || '.' || tab.relname AS owning_table,
            col.attname                          AS owning_column
        FROM pg_class           seq
        JOIN pg_namespace       seq_ns ON seq_ns.oid = seq.relnamespace
        JOIN pg_depend          dep    ON dep.objid = seq.oid
                                       AND dep.classid = 'pg_class'::regclass
                                       AND dep.deptype = 'a'
        JOIN pg_class           tab    ON tab.oid = dep.refobjid
        JOIN pg_namespace       tab_ns ON tab_ns.oid = tab.relnamespace
        JOIN pg_attribute       col    ON col.attrelid = dep.refobjid
                                       AND col.attnum = dep.refobjsubid
        WHERE seq.relkind = 'S'
          AND seq_ns.nspname = %s
        ORDER BY sequence
    """
    with pg_conn.cursor() as cur:
        cur.execute(sql, (schema,))
        return [
            SequenceLink(sequence=row[0], table=row[1], column=row[2])
            for row in cur.fetchall()
        ]


def catch_up_sequence(pg_conn, link: SequenceLink) -> CatchupResult:
    """Advance one sequence to `MAX(column) + 1`. Empty tables are
    no-ops; we don't want to setval to 0 because PG sequences treat
    `is_called=true` differently than the post-CREATE state."""
    table_q = _quote_table(link.table)
    col_q = _quote(link.column)
    seq_q = _quote_table(link.sequence)
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT MAX({col_q}) FROM {table_q}")
        (max_val,) = cur.fetchone() or (None,)
        if max_val is None:
            return CatchupResult(link=link, set_to=None, skipped_reason="empty table")
        # `setval(seq, n, true)` — the third arg means is_called=true,
        # so the next nextval() returns n+1. That's exactly what we want.
        cur.execute("SELECT setval(%s, %s, true)", (link.sequence, max_val))
    return CatchupResult(link=link, set_to=int(max_val))


def catch_up_all(pg_conn, schema: str = "public") -> List[CatchupResult]:
    """Convenience wrapper: discover + catch-up every owned sequence in
    `schema`. Commits are the caller's responsibility."""
    out: List[CatchupResult] = []
    for link in discover_owned_sequences(pg_conn, schema=schema):
        out.append(catch_up_sequence(pg_conn, link))
    return out


# ─── helpers ─────────────────────────────────────────────────────────────────


def _quote(ident: str) -> str:
    if '"' in ident:
        raise ValueError(f"identifier contains quote: {ident!r}")
    return f'"{ident}"'


def _quote_table(qualified: str) -> str:
    if "." in qualified:
        s, n = qualified.split(".", 1)
        return f"{_quote(s)}.{_quote(n)}"
    return _quote(qualified)
