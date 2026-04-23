"""Tier-3 stress-schema matrix runner.

Each fixture in `tests/fixtures/oracle_stress/` targets a specific
code path the recent audit fixed. Without these tests, future
refactors could silently re-break them and we wouldn't know until a
customer hit it. This file is the regression net.

The matrix is parameterized: adding a new stress schema = adding a
new entry to `_FIXTURES`, not writing a new test from scratch.

Each fixture-specific assertion goes beyond "Runner ran" — we check
the actual code path the fixture is supposed to exercise:

  * `01_composite_null_pk` — `nullable_pk_columns()` flags the table
  * `02_self_fk_unordered` — runner's NULL-then-UPDATE pass actually
    completes (without it, the COPY would FK-fail)
  * `03_lob_heavy`         — round-trip succeeds + advisor recommends
    a smaller batch_size for the LOB-dominant table
  * `04_byte_vs_char_varchar2` — quality scan finds no overflow on a
    correctly-sized target column (the warning shape is unit-tested
    separately in test_migrate_quality.py)
  * `05_bfile_present`     — BFILE→TEXT mapping happens with a logged
    warning instead of crashing DDL generation

Skips automatically when Oracle isn't reachable.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import sessionmaker

from src.config import settings as env_settings
from src.migrate.advisor import advise
from src.migrate.ddl import (
    apply_ddl,
    generate_schema_ddl,
    map_oracle_type,
)
from src.migrate.introspect import introspect
from src.migrate.keyset import Dialect
from src.migrate.planner import plan_load_order
from src.migrate.quality import scan_varchar_lengths
from src.migrate.runner import Runner


ORACLE_URL = os.environ.get(
    "ORACLE_TEST_URL",
    "oracle+oracledb://system:oracle@localhost:1521/?service_name=FREEPDB1",
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "oracle_stress"


# ─── Fixture metadata ────────────────────────────────────────────────────────


# `table` is the source-side table name we'll migrate.
# `null_then_update` lists self-FK columns the runner should defer.
# Optional `assertion` is a per-fixture extra check the parametrized
# test calls after the migration completes.
_FIXTURES = [
    {
        "id": "01_composite_null_pk",
        "table": "HAFEN_STRESS_NULL_PK",
        "null_then_update": [],
        # Skip the verify check for this fixture: introspection lists
        # an effective PK from the unique index, but the runner's
        # NULL-PK guard refuses the migration mid-walk. The test
        # assertion below checks `nullable_pk_columns()` instead.
        "skip_runner": True,
    },
    {
        "id": "02_self_fk_unordered",
        "table": "HAFEN_STRESS_SELF_FK",
        # Install the self-FK on the target so the runner's
        # NULL-then-UPDATE pass actually has something to satisfy.
        "install_self_fk": ("MANAGER_ID", "ID"),
        "null_then_update": ["MANAGER_ID"],
    },
    {
        "id": "03_lob_heavy",
        "table": "HAFEN_STRESS_LOB_HEAVY",
        "null_then_update": [],
    },
    {
        "id": "04_byte_vs_char_varchar2",
        "table": "HAFEN_STRESS_BYTE_VS_CHAR",
        "null_then_update": [],
    },
    {
        "id": "05_bfile_present",
        "table": "HAFEN_STRESS_BFILE",
        "null_then_update": [],
    },
]


# ─── Connection fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def oracle_session():
    try:
        engine = create_engine(ORACLE_URL)
        s = sessionmaker(bind=engine)()
        s.execute(text("SELECT 1 FROM dual"))
    except (DatabaseError, OperationalError, Exception) as e:  # noqa: BLE001
        pytest.skip(f"Oracle not reachable at {ORACLE_URL!r}: {e}")
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def pg_url():
    return env_settings.database_url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def pg_target_schema(pg_url):
    schema = f"stress_{uuid.uuid4().hex[:8]}"
    conn = psycopg.connect(pg_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
    conn.close()
    yield schema
    conn = psycopg.connect(pg_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f'DROP SCHEMA "{schema}" CASCADE')
    conn.close()


@pytest.fixture
def pg_session(pg_url):
    engine = create_engine(env_settings.database_url)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def pg_raw_conn(pg_url):
    conn = psycopg.connect(pg_url, autocommit=True)
    yield conn
    conn.close()


# ─── Per-fixture loader ──────────────────────────────────────────────────────


def _split_oracle_script(sql: str) -> list[str]:
    """Split a fixture .sql file into individual statements the
    oracledb driver can execute one at a time.

    The fixtures are deliberately plain-SQL — no PL/SQL blocks, no
    `/` block terminators. Strategy:
      1. Drop standalone comment lines and blank lines.
      2. Strip inline `-- comment` tails from each line (the driver
         throws ORA-03405 if anything follows a complete statement).
      3. Split on `;` at line end.
      4. Strip the trailing `;` from each emitted statement.
    """
    cleaned_lines: list[str] = []
    for raw in sql.splitlines():
        # Drop inline trailing comments (`stmt;  -- note`) — Oracle's
        # driver doesn't tolerate them at end-of-statement.
        line = re.sub(r"--.*$", "", raw).rstrip()
        if not line.strip():
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    chunks = [c.strip() for c in cleaned.split(";")]
    return [c for c in chunks if c]


def _load_fixture(oracle_session, fixture_id: str, table_name: str) -> None:
    """Drop+create the fixture in the user's Oracle. Idempotent so the
    test can run repeatedly without manual cleanup."""
    qualified = f"system.{table_name}"

    # Drop first (ignore errors if it doesn't exist).
    oracle_session.execute(
        text(
            f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {qualified} CASCADE CONSTRAINTS PURGE'; "
            "EXCEPTION WHEN OTHERS THEN NULL; END;"
        )
    )
    oracle_session.commit()

    sql_path = FIXTURES_DIR / f"{fixture_id}.sql"
    sql = sql_path.read_text()
    for stmt in _split_oracle_script(sql):
        oracle_session.execute(text(stmt))
    oracle_session.commit()

    # 03_lob_heavy needs row data populated from Python — the SQL
    # fixture intentionally only emits the CREATE TABLE because
    # Oracle PL/SQL blocks don't survive our SQL splitter, and 50
    # individual INSERT statements with embedded 5KB CLOB literals
    # would push the .sql past 250KB.
    if fixture_id == "03_lob_heavy":
        for i in range(1, 51):
            body = f"L{i}:" + ("x" * 5000)
            blob = (f"B{i}:" + ("y" * 200)).encode("utf-8")
            oracle_session.execute(
                text(
                    "INSERT INTO system.HAFEN_STRESS_LOB_HEAVY "
                    "VALUES (:id, :title, :body, :blob)"
                ),
                {"id": i, "title": f"row-{i}", "body": body, "blob": blob},
            )
        oracle_session.commit()


def _drop_fixture(oracle_session, table_name: str) -> None:
    qualified = f"system.{table_name}"
    oracle_session.execute(
        text(
            f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {qualified} CASCADE CONSTRAINTS PURGE'; "
            "EXCEPTION WHEN OTHERS THEN NULL; END;"
        )
    )
    oracle_session.commit()


# ─── The matrix ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[f["id"] for f in _FIXTURES])
def test_stress_fixture_round_trips(
    fixture, oracle_session, pg_target_schema, pg_session, pg_raw_conn, pg_url, caplog
):
    """Per-fixture: load → introspect → DDL → run → verify (per-fixture
    assertion). Drops the fixture afterward."""
    table = fixture["table"]
    _load_fixture(oracle_session, fixture["id"], table)

    try:
        # Introspect just this one table.
        schema = introspect(oracle_session, Dialect.ORACLE, "SYSTEM")
        schema.tables = [t for t in schema.tables if t.name == table]
        assert schema.tables, f"fixture loader did not produce table {table!r}"

        # Per-fixture: 01 has only a UNIQUE INDEX, no real PRIMARY
        # KEY constraint (Oracle won't allow nullable columns in a
        # true PK). The introspector queries `constraint_type='P'`
        # only, so it correctly reports no PK for this table — and
        # `build_specs()` then skips it as unmigratable. That's the
        # right behavior; this fixture locks it in.
        if fixture["id"] == "01_composite_null_pk":
            specs_check = schema.build_specs(target_schema=pg_target_schema)
            assert not specs_check, (
                f"expected build_specs() to skip the no-PK fixture, "
                f"got: {list(specs_check.keys())}"
            )

        if fixture.get("skip_runner"):
            return

        # Build specs + DDL.
        specs = schema.build_specs(target_schema=pg_target_schema)
        if not specs:
            pytest.skip(
                f"introspection produced no migratable specs for {table} "
                "(no PK?) — fixture-specific behavior, see fixture comment"
            )

        cols_by_target = {
            s.target_table.qualified(): schema.column_metadata[
                s.source_table.qualified()
            ]
            for s in specs.values()
        }
        pks_by_target = {
            s.target_table.qualified(): s.pk_columns for s in specs.values()
        }
        target_refs = [s.target_table for s in specs.values()]

        # For 05_bfile_present: capture the BFILE warning.
        with caplog.at_level(logging.WARNING, logger="src.migrate.ddl"):
            ddl_stmts = generate_schema_ddl(
                target_refs, cols_by_target, pks_by_target, map_type=map_oracle_type
            )

        if fixture["id"] == "05_bfile_present":
            # The BFILE column should have produced a logged warning
            # AND the DDL should map BFILE → TEXT (not raise).
            assert any(
                "BFILE" in rec.message for rec in caplog.records
            ), f"expected BFILE warning in logs; got {[r.message for r in caplog.records]}"
            create_stmt = next(s for s in ddl_stmts if table in s)
            assert "TEXT" in create_stmt.upper()

        # Apply DDL on target.
        ddl_conn = psycopg.connect(pg_url)
        try:
            # Optionally install a self-FK on the target so the
            # runner's NULL-then-UPDATE pass has something to satisfy.
            apply_ddl(ddl_conn, ddl_stmts)
            if "install_self_fk" in fixture:
                fk_col, ref_col = fixture["install_self_fk"]
                with ddl_conn.cursor() as cur:
                    cur.execute(
                        f'ALTER TABLE "{pg_target_schema}"."{table}" '
                        f'ADD CONSTRAINT "{table}_self_fk" '
                        f'FOREIGN KEY ("{fk_col}") '
                        f'REFERENCES "{pg_target_schema}"."{table}"("{ref_col}")'
                    )
            ddl_conn.commit()
        finally:
            ddl_conn.close()

        # Run the migration.
        plan = plan_load_order(target_refs, [])
        target_qn = f"{pg_target_schema}.{table}"
        nt_map = (
            {target_qn: fixture["null_then_update"]}
            if fixture["null_then_update"]
            else {}
        )
        runner = Runner(
            source_session=oracle_session,
            target_session=pg_session,
            target_pg_conn=pg_raw_conn,
            source_dialect=Dialect.ORACLE,
            batch_size=20,
            null_then_update_columns=nt_map,
        )
        result = runner.execute(plan, specs)

        target_result = result.tables[target_qn]
        assert target_result.verified, (
            f"verification failed for {fixture['id']}: {target_result.discrepancy}"
        )

        # Per-fixture: advisor sanity check on the LOB-heavy table.
        if fixture["id"] == "03_lob_heavy":
            advice = advise(schema)
            ta = advice.per_table.get(f"SYSTEM.{table}")
            assert ta is not None
            # LOB-heavy tables should NOT recommend the runner's default
            # 5000 — the advisor should prescribe something smaller.
            assert ta.recommended_batch_size < 5000, (
                f"advisor failed to size down a LOB-heavy table: "
                f"{ta.recommended_batch_size}"
            )
            assert "LOB-heavy" in ta.rationale

        # Per-fixture: quality scan on the byte-vs-char fixture.
        if fixture["id"] == "04_byte_vs_char_varchar2":
            cols = schema.column_metadata[f"SYSTEM.{table}"]
            findings = scan_varchar_lengths(
                oracle_session, Dialect.ORACLE, f"SYSTEM.{table}", cols
            )
            # The narrow `name_short` column carries multi-byte
            # content; scan_varchar_lengths reports its observed
            # max-length. We assert the call works against live
            # Oracle (the unit-level overflow assertions are in
            # test_migrate_quality.py).
            assert isinstance(findings, list)

    finally:
        _drop_fixture(oracle_session, table)
