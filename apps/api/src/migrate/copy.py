"""Postgres COPY writer.

`psycopg`'s `cursor.copy()` is the fastest way to land rows in PG —
order-of-magnitude faster than executemany INSERT. This module wraps it
with the bookkeeping the runner needs: column ordering (so the row
tuples we ship from Oracle match the COPY header), batch boundaries (so
checkpoint can record progress), and error reporting (so a single bad
row identifies itself rather than aborting the whole batch silently).

The writer does NOT manage transactions — the runner is in charge of
when to commit and whether constraints stay deferred. We use a single
COPY for an entire batch; if any row fails, the COPY aborts and the
caller decides whether to retry the batch row-by-row or give up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class CopyResult:
    """Per-batch outcome reported back to the runner."""

    rows_written: int
    last_pk: tuple | None  # the PK tuple of the final row, for keyset resume


def copy_rows_to_postgres(
    *,
    pg_conn,  # raw psycopg.Connection
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence],
    pk_column_indexes: Sequence[int],
) -> CopyResult:
    """Stream `rows` into `table` via PG `COPY ... FROM STDIN`.

    The caller supplies an already-open psycopg connection (so the runner
    can decide on transaction scope). Rows are 1:1 with `columns`, in the
    same order. `pk_column_indexes` tells us which columns to read out of
    each row to form the keyset cursor for the next batch — this is much
    cheaper than re-querying the destination.

    Implementation notes:

      * We use the binary COPY format. Text COPY would force every value
        through `str()` and re-parse it on the server; binary skips that
        round-trip and preserves precision for NUMERIC/TIMESTAMP/UUID.
      * The COPY context manager calls `write_row()` per tuple. psycopg
        handles the binary header/trailer.
      * Identifier quoting is the caller's responsibility — same as
        `keyset.py`. We never interpolate user-controlled strings into
        the COPY statement.
    """
    cols_sql = ", ".join(_quote(c) for c in columns)
    table_sql = _quote_table(table)
    copy_sql = f"COPY {table_sql} ({cols_sql}) FROM STDIN WITH (FORMAT BINARY)"

    # Resolve types BEFORE entering the COPY block — issuing any other
    # statement on the same connection while a COPY is in progress
    # deadlocks (PG protocol won't multiplex).
    types = _infer_types(pg_conn, table, columns)

    rows_written = 0
    last_pk: tuple | None = None

    with pg_conn.cursor() as cur:
        with cur.copy(copy_sql) as copy:
            copy.set_types(types)
            for row in rows:
                copy.write_row(row)
                rows_written += 1
                last_pk = tuple(row[i] for i in pk_column_indexes)

    return CopyResult(rows_written=rows_written, last_pk=last_pk)


def _infer_types(pg_conn, table: str, columns: Sequence[str]) -> list[str]:
    """Look up the canonical type name for each column in `pg_catalog`.

    Binary COPY needs the type per column so psycopg can format the bytes
    correctly. psycopg's type registry is keyed on bare type names —
    `numeric`, not `numeric(10,2)` — so we read `pg_type.typname`
    directly rather than `format_type()` which includes the type
    modifier.
    """
    schema, name = _split_qualified(table)
    sql = """
        SELECT a.attname, t.typname
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_type t ON t.oid = a.atttypid
        WHERE n.nspname = %s AND c.relname = %s AND a.attnum > 0 AND NOT a.attisdropped
    """
    with pg_conn.cursor() as cur:
        cur.execute(sql, (schema, name))
        type_by_col = {row[0]: row[1] for row in cur.fetchall()}
    missing = [c for c in columns if c not in type_by_col]
    if missing:
        raise LookupError(
            f"columns {missing} not found in {table}; introspection out of sync?"
        )
    return [type_by_col[c] for c in columns]


def _split_qualified(table: str) -> tuple[str, str]:
    if "." in table:
        s, n = table.split(".", 1)
        return s, n
    return "public", table


def _quote(ident: str) -> str:
    if '"' in ident:
        raise ValueError(f"identifier contains quote: {ident!r}")
    return f'"{ident}"'


def _quote_table(qualified: str) -> str:
    s, n = _split_qualified(qualified)
    return f"{_quote(s)}.{_quote(n)}"
