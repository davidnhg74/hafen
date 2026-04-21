import pytest
from src.parsers.plsql_parser import PlSqlParser, ConstructType


class TestPlSqlParser:
    @pytest.fixture
    def parser(self):
        return PlSqlParser()

    def test_parse_procedure(self, parser):
        """Test parsing a procedure."""
        sql = "CREATE PROCEDURE my_proc AS BEGIN NULL; END;"
        result = parser.parse(sql)

        assert result.total_lines > 0
        assert len(result.constructs) > 0
        assert any(c.type == ConstructType.PROCEDURE for c in result.constructs)

    def test_parse_function(self, parser):
        """Test parsing a function."""
        sql = "CREATE FUNCTION my_func RETURN NUMBER AS BEGIN RETURN 1; END;"
        result = parser.parse(sql)

        assert any(c.type == ConstructType.FUNCTION for c in result.constructs)

    def test_parse_trigger(self, parser):
        """Test parsing a trigger."""
        sql = "CREATE TRIGGER emp_trigger BEFORE INSERT ON employees FOR EACH ROW BEGIN NULL; END;"
        result = parser.parse(sql)

        assert any(c.type == ConstructType.TRIGGER for c in result.constructs)

    def test_parse_package(self, parser):
        """Test parsing a package."""
        sql = """
        CREATE PACKAGE my_pkg AS
          PROCEDURE proc1;
        END my_pkg;
        """
        result = parser.parse(sql)

        assert any(c.type == ConstructType.PACKAGE for c in result.constructs)

    def test_parse_connect_by(self, parser):
        """Test detection of CONNECT BY."""
        sql = """
        SELECT * FROM employees
        START WITH manager_id IS NULL
        CONNECT BY PRIOR employee_id = manager_id
        """
        result = parser.parse(sql)

        assert any(c.type == ConstructType.CONNECT_BY for c in result.constructs)

    def test_parse_merge(self, parser):
        """Test detection of MERGE."""
        sql = """
        MERGE INTO target t USING source s
        ON (t.id = s.id)
        WHEN MATCHED THEN UPDATE SET t.val = s.val
        WHEN NOT MATCHED THEN INSERT (id, val) VALUES (s.id, s.val)
        """
        result = parser.parse(sql)

        assert any(c.type == ConstructType.MERGE for c in result.constructs)

    def test_parse_autonomous_transaction(self, parser):
        """Test detection of PRAGMA AUTONOMOUS_TRANSACTION."""
        sql = """
        CREATE PROCEDURE audit_proc AS
          PRAGMA AUTONOMOUS_TRANSACTION;
        BEGIN
          NULL;
        END;
        """
        result = parser.parse(sql)

        assert any(
            c.type == ConstructType.AUTONOMOUS_TXN for c in result.constructs
        )

    def test_parse_rowtype(self, parser):
        """Test detection of %ROWTYPE."""
        sql = """
        CREATE PROCEDURE proc1 AS
          v_emp employees%ROWTYPE;
        BEGIN
          NULL;
        END;
        """
        result = parser.parse(sql)

        assert any(c.type == ConstructType.ROWTYPE for c in result.constructs)

    def test_parse_execute_immediate(self, parser):
        """Test detection of EXECUTE IMMEDIATE."""
        sql = """
        CREATE PROCEDURE dynamic_query AS
        BEGIN
          EXECUTE IMMEDIATE 'SELECT * FROM employees';
        END;
        """
        result = parser.parse(sql)

        assert any(
            c.type == ConstructType.EXECUTE_IMMEDIATE for c in result.constructs
        )

    def test_parse_dbms_calls(self, parser):
        """Test detection of DBMS_* calls."""
        sql = """
        BEGIN
          DBMS_OUTPUT.PUT_LINE('Hello');
          DBMS_SCHEDULER.CREATE_JOB(...);
          DBMS_AQ.ENQUEUE(...);
        END;
        """
        result = parser.parse(sql)

        assert any(
            c.type == ConstructType.DBMS_CALL for c in result.constructs
        )
        assert any(c.type == ConstructType.DBMS_SCHEDULER for c in result.constructs)
        assert any(c.type == ConstructType.DBMS_AQ for c in result.constructs)

    def test_comment_removal(self, parser):
        """Test that comments are removed."""
        sql = """
        -- This is a comment
        CREATE PROCEDURE proc1 AS
        /* Multi-line
           comment */
        BEGIN
          NULL;
        END;
        """
        result = parser.parse(sql)

        # Should still find the procedure despite comments
        assert any(c.type == ConstructType.PROCEDURE for c in result.constructs)

    def test_construct_count(self, parser):
        """Test construct counting."""
        sql = """
        CREATE TABLE emp (id NUMBER);
        CREATE PROCEDURE proc1 AS BEGIN NULL; END;
        CREATE FUNCTION func1 RETURN NUMBER AS BEGIN RETURN 1; END;
        """
        result = parser.parse(sql)

        assert len(result.constructs) >= 3

    def test_tier_classification(self, parser):
        """Test tier classification of lines."""
        sql = """
        CREATE PROCEDURE tier_a_proc AS BEGIN NULL; END;
        CREATE PROCEDURE tier_b_proc AS
        BEGIN
          EXECUTE IMMEDIATE 'SELECT 1';
        END;
        """
        result = parser.parse(sql)

        # Should have tier A (procedure) and tier B (EXECUTE IMMEDIATE)
        assert result.tier_a_lines > 0
        assert result.tier_b_lines > 0

    def test_global_temp_table_detection(self, parser):
        """Test detection of global temporary tables."""
        sql = "CREATE GLOBAL TEMPORARY TABLE temp_emp (id NUMBER);"
        result = parser.parse(sql)

        assert any(
            c.type == ConstructType.GLOBAL_TEMP_TABLE for c in result.constructs
        )
