-- Stress fixture: LOB-heavy table.
--
-- Targets:
--   * apps/api/src/migrate/runner.py:_materialize_value — must turn
--     oracledb.LOB instances into bytes/str before COPY and verify see them
--   * apps/api/src/migrate/advisor.py — must recommend a smaller batch_size
--     for tables whose row width is dominated by LOBs
--
-- The matrix runner populates the rows from Python after this DDL
-- runs (50 rows × ~5KB CLOB each); doing the inserts here would
-- require a PL/SQL block which the test harness's SQL splitter
-- doesn't handle well.

CREATE TABLE system.HAFEN_STRESS_LOB_HEAVY (
    id NUMBER(6) NOT NULL PRIMARY KEY,
    title VARCHAR2(50) NOT NULL,
    body CLOB,
    blob_payload BLOB
);
