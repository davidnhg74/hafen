"""Interim-vs-ANTLR parser equivalence gate.

When `_generated/` exists, both parser implementations parse the same
corpus and we assert they agree on Module shape (object kinds, names,
construct tags). The test skips when generation hasn't run — local-dev
without Java should still pass `make test`.

Once the ANTLR path is the only one that ships, this file goes away.
"""

import pytest

from src.source.oracle import _visitor
from src.source.oracle.parser import parse_with_interim


pytestmark = pytest.mark.skipif(
    not _visitor.is_available(),
    reason="ANTLR _generated/ not present; run `make grammar` to enable.",
)


CORPUS = [
    pytest.param(
        "CREATE TABLE t (id NUMBER PRIMARY KEY);",
        id="simple-table",
    ),
    pytest.param(
        "CREATE OR REPLACE VIEW v AS SELECT * FROM t;",
        id="simple-view",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PROCEDURE upsert AS
        BEGIN
            MERGE INTO t USING s ON (t.id = s.id)
            WHEN MATCHED THEN UPDATE SET t.x = s.x
            WHEN NOT MATCHED THEN INSERT (id, x) VALUES (s.id, s.x);
        END;
        """,
        id="proc-with-merge",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PROCEDURE org AS
        BEGIN
            SELECT id FROM emp START WITH mgr IS NULL CONNECT BY PRIOR id = mgr;
        END;
        """,
        id="proc-with-connect-by",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PROCEDURE bulk_load AS
            TYPE id_tab IS TABLE OF NUMBER;
            ids id_tab;
        BEGIN
            SELECT id BULK COLLECT INTO ids FROM emp;
            FORALL i IN 1 .. ids.COUNT
                UPDATE emp SET status = 'X' WHERE id = ids(i);
        END;
        """,
        id="proc-with-bulk-collect-and-forall",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PROCEDURE dyn AS
        BEGIN
            EXECUTE IMMEDIATE 'TRUNCATE TABLE t';
        END;
        """,
        id="proc-with-execute-immediate",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PROCEDURE auto AS
            PRAGMA AUTONOMOUS_TRANSACTION;
        BEGIN
            INSERT INTO audit_log VALUES (SYSDATE);
            COMMIT;
        END;
        """,
        id="proc-with-autonomous-transaction",
    ),
    pytest.param(
        """
        CREATE OR REPLACE VIEW emp_dept AS
        SELECT e.id, d.name
        FROM emp e, dept d
        WHERE e.dept_id = d.id(+);
        """,
        id="view-with-outer-join-plus",
    ),
    pytest.param(
        """
        CREATE OR REPLACE PACKAGE BODY emp_pkg AS
            TYPE emp_cur IS REF CURSOR;
            PROCEDURE list_emps(c OUT emp_cur) IS
            BEGIN
                OPEN c FOR SELECT id FROM emp;
            END;
        END;
        """,
        id="package-with-ref-cursor-type",
    ),
]


def _kinds(m) -> list:
    return sorted(o.kind.value for o in m.objects if o.name != "<module-constructs>")


def _construct_tags(m) -> set:
    tags = set()
    for o in m.objects:
        for r in getattr(o, "referenced_constructs", []):
            tags.add(r.tag.value)
    return tags


@pytest.mark.parametrize("source", CORPUS)
def test_object_kinds_agree(source):
    m_interim = parse_with_interim(source)
    m_antlr = _visitor.parse_with_antlr(source)
    assert _kinds(m_interim) == _kinds(m_antlr)


@pytest.mark.parametrize("source", CORPUS)
def test_construct_tags_agree(source):
    m_interim = parse_with_interim(source)
    m_antlr = _visitor.parse_with_antlr(source)
    assert _construct_tags(m_interim) == _construct_tags(m_antlr)
