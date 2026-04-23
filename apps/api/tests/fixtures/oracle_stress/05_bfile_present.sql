-- Stress fixture: BFILE column.
--
-- Targets apps/api/src/migrate/ddl.py:map_oracle_type — the BFILE
-- branch added during the audit. Before the fix, BFILE fell through
-- to the unknown-type ValueError mid-DDL generation, after the
-- operator had already kicked off the migration. The fix maps BFILE
-- to PG TEXT (which receives the file *locator string*, not the
-- file contents — Postgres has no equivalent for Oracle's external
-- file pointer concept) and emits a logger.warning so the operator
-- knows the underlying files weren't migrated.
--
-- We don't actually populate the BFILE column with a real directory
-- pointer (would require BFILE_DIR setup outside the test harness).
-- A NULL BFILE is enough to exercise the type-mapping code path:
-- the column exists, introspection sees it as data_type='BFILE',
-- the DDL generator must emit TEXT + warn rather than raise.

CREATE TABLE system.HAFEN_STRESS_BFILE (
    id NUMBER(6) NOT NULL PRIMARY KEY,
    label VARCHAR2(50) NOT NULL,
    file_pointer BFILE
);

INSERT INTO system.HAFEN_STRESS_BFILE VALUES (1, 'no file attached', NULL);
INSERT INTO system.HAFEN_STRESS_BFILE VALUES (2, 'still no file',    NULL);
INSERT INTO system.HAFEN_STRESS_BFILE VALUES (3, 'third row',        NULL);

COMMIT;
