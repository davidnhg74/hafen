"""CLI entry point for the data-movement runner.

  python -m src.migrate \
      --source 'oracle+oracledb://hr:hr@oracle:1521/?service_name=FREEPDB1' \
      --target 'postgresql+psycopg://depart_user:depart_secure_password@localhost:5432/depart' \
      --source-schema HR \
      --target-schema public \
      [--tables EMPLOYEES,DEPARTMENTS]   # restrict to a subset
      [--batch-size 5000]
      [--no-verify]                       # skip the Merkle hash pass

The CLI is deliberately thin — every primitive (introspection, plan,
runner, checkpoint adapter) is a library call. This file just parses
flags, opens connections, runs the loop, and prints a result table.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..migration.checkpoint import CheckpointManager
from .checkpoint_adapter import make_checkpoint_callback
from .introspect import introspect
from .keyset import Dialect
from .planner import plan_load_order
from .runner import Runner


def main(argv: Optional[list[str]] = None) -> int:
    args = _parse_args(argv)

    src_dialect = Dialect.ORACLE if args.source.startswith("oracle") else Dialect.POSTGRES

    src_engine = create_engine(args.source)
    dst_engine = create_engine(args.target)
    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)
    src_session = SrcSession()
    dst_session = DstSession()

    # Raw psycopg conn for the binary COPY protocol.
    pg_url = args.target.replace("postgresql+psycopg://", "postgresql://")
    pg_conn = psycopg.connect(pg_url, autocommit=True)

    print(f"introspecting source schema {args.source_schema!r}...", file=sys.stderr)
    schema = introspect(src_session, src_dialect, args.source_schema)
    if args.tables:
        wanted = {t.strip() for t in args.tables.split(",")}
        schema.tables = [t for t in schema.tables if t.name in wanted]

    specs = schema.build_specs(target_schema=args.target_schema)
    if not specs:
        print(
            f"no migratable tables found in {args.source_schema!r} "
            f"(after PK/whitelist filtering)",
            file=sys.stderr,
        )
        return 1

    plan = plan_load_order(
        [s.target_table for s in specs.values()],
        # Rewrite FK refs to point at the target schema so the planner
        # operates in the destination namespace.
        [
            type(fk)(
                name=fk.name,
                from_table=_rewrite_schema(fk.from_table, args.source_schema, args.target_schema),
                to_table=_rewrite_schema(fk.to_table, args.source_schema, args.target_schema),
                deferrable=fk.deferrable,
            )
            for fk in schema.foreign_keys
        ],
    )
    print(f"plan: {len(plan.groups)} group(s), {len(plan.flat_tables())} table(s)", file=sys.stderr)

    # Checkpoint manager + adapter — all batches are persisted to the
    # migrations table so a crash can resume.
    manager = CheckpointManager(dst_session)
    migration_id = manager.create_migration(
        f"{args.source_schema}->{args.target_schema}",
    )
    print(f"migration_id: {migration_id}", file=sys.stderr)
    callback = make_checkpoint_callback(manager, migration_id)

    runner = Runner(
        source_session=src_session,
        target_session=dst_session,
        target_pg_conn=pg_conn,
        source_dialect=src_dialect,
        batch_size=args.batch_size,
        checkpoint=callback,
    )

    result = runner.execute(plan, specs)

    print()
    print(f"{'table':40s}  {'rows':>10s}  verified")
    print("-" * 65)
    for qn, tr in result.tables.items():
        verified = "✓" if tr.verified else "✗"
        print(f"{qn:40s}  {tr.rows_copied:>10d}  {verified}")
    print()
    print(f"sequences advanced: {len(result.sequences)}")
    print(f"all verified: {result.all_verified}")
    print(f"total rows: {result.total_rows}")

    src_session.close()
    dst_session.close()
    pg_conn.close()
    return 0 if result.all_verified else 2


def _parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--source", required=True, help="SQLAlchemy URL for the source DB")
    p.add_argument("--target", required=True, help="SQLAlchemy URL for the target Postgres")
    p.add_argument(
        "--source-schema",
        required=True,
        help="Source schema/owner (e.g. HR for Oracle, public for Postgres)",
    )
    p.add_argument(
        "--target-schema",
        required=True,
        help="Destination schema in Postgres (typically public)",
    )
    p.add_argument(
        "--tables",
        default=None,
        help="Comma-separated table names to restrict to (default: every table with a PK)",
    )
    p.add_argument("--batch-size", type=int, default=5000, help="Rows per COPY batch (default 5000)")
    return p.parse_args(argv)


def _rewrite_schema(ref, src_schema: str, dst_schema: str):
    """If `ref.schema` matches the source schema, swap it to the target.
    Used so the FK graph lives in the destination namespace."""
    from .planner import TableRef

    if ref.schema and ref.schema.upper() == src_schema.upper():
        return TableRef(schema=dst_schema, name=ref.name)
    return ref


if __name__ == "__main__":
    sys.exit(main())
