"""
Semantic error detection for Oracle → PostgreSQL migrations.
Uses Claude AI to detect logical errors (precision loss, date behavior, NULL semantics, etc.)
that syntax checkers miss.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    """Severity level for semantic issues."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IssueType(str, Enum):
    """Type of semantic issue detected."""

    PRECISION_LOSS = "PRECISION_LOSS"
    DATE_BEHAVIOR = "DATE_BEHAVIOR"
    TYPE_COERCION = "TYPE_COERCION"
    ENCODING_MISMATCH = "ENCODING_MISMATCH"
    NULL_SEMANTICS = "NULL_SEMANTICS"
    IMPLICIT_CAST = "IMPLICIT_CAST"
    RANGE_CHANGE = "RANGE_CHANGE"


@dataclass
class SemanticIssue:
    """A single semantic issue detected in type mapping."""

    severity: IssueSeverity
    issue_type: IssueType
    affected_object: str  # e.g., "ORDERS.AMOUNT"
    oracle_type: str  # e.g., "NUMBER(12,2)"
    pg_type: str  # e.g., "NUMERIC(10,2)"
    description: str
    recommendation: str


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis."""

    issues: List[SemanticIssue] = field(default_factory=list)
    mode: str = "static"  # "static" | "live"
    analyzed_objects: int = 0
    error: Optional[str] = None


class StaticDDLExtractor:
    """Extract type mappings from Oracle and PostgreSQL DDL text."""

    # Matches: col_name  TYPE(p,s) [BYTE|CHAR] [constraints...]
    # The same regex is used for both Oracle and PostgreSQL DDL — type names
    # from both dialects are listed below. Multi-word PG types like
    # `TIMESTAMP WITHOUT TIME ZONE` collapse to their leading token; that's
    # acceptable since the comparator only looks at the base name + precision.
    COLUMN_RE = re.compile(
        r"""^\s*(\w+)\s+                         # column name
            (NUMBER|VARCHAR2|NVARCHAR2|DATE|CLOB|
             BLOB|RAW|LONG|CHAR|NCHAR|TIMESTAMP|
             INTERVAL|FLOAT|BINARY_DOUBLE|BINARY_FLOAT|
             # PostgreSQL types
             INTEGER|INT|BIGINT|SMALLINT|NUMERIC|DECIMAL|
             REAL|DOUBLE|VARCHAR|TEXT|BOOLEAN|BYTEA|
             UUID|JSON|JSONB|SERIAL|BIGSERIAL)     # base type
            (\s*\([^)]+\))?                        # optional (p,s)
            (?:\s+(BYTE|CHAR))?                    # optional byte/char (Oracle only)
        """,
        re.IGNORECASE | re.VERBOSE | re.MULTILINE,
    )

    TABLE_RE = re.compile(
        r"CREATE\s+(?:GLOBAL\s+TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)",
        re.IGNORECASE,
    )

    def extract_type_mappings(
        self,
        oracle_ddl: str,
        pg_ddl: str,
    ) -> List[Dict]:
        """
        Parse Oracle and PostgreSQL DDL to extract column type mappings.
        Returns list of {table, column, oracle_type, pg_type}.
        """
        oracle_tables = self._parse_tables(oracle_ddl)
        pg_tables = self._parse_tables(pg_ddl)
        # Case-insensitive index over pg_tables — both Oracle and PG identifiers
        # fold to the same key without losing the original casing in the mapping.
        pg_index = {k.upper(): k for k in pg_tables}

        mappings = []
        for table_name, oracle_cols in oracle_tables.items():
            pg_key = pg_index.get(table_name.upper())
            pg_cols = pg_tables.get(pg_key) if pg_key else None

            if pg_cols is None:
                logger.warning(f"Table {table_name} not found in PostgreSQL DDL")
                continue

            # Match columns by name (case-insensitive), fallback to positional
            for oracle_col_name, oracle_type in oracle_cols.items():
                pg_col_name = next(
                    (name for name in pg_cols if name.upper() == oracle_col_name.upper()),
                    None,
                )
                if pg_col_name:
                    pg_type = pg_cols[pg_col_name]
                    mappings.append(
                        {
                            "table": table_name,
                            "column": oracle_col_name,
                            "oracle_type": oracle_type,
                            "pg_type": pg_type,
                        }
                    )

        return mappings

    def _parse_tables(self, ddl: str) -> Dict[str, Dict[str, str]]:
        """Parse DDL and extract {table_name: {column_name: type}}.

        Handles both formatting styles:
          • One column per line (multi-line CREATE TABLE).
          • All columns on the CREATE TABLE line (single-line tests, terse DDL).
        Strategy: locate each CREATE TABLE, find the body inside the
        outermost parentheses, then split the body on top-level commas
        (commas inside `NUMBER(10,2)` don't count) and feed each fragment
        through COLUMN_RE.
        """
        tables: Dict[str, Dict[str, str]] = {}
        for table_match in self.TABLE_RE.finditer(ddl):
            # Preserve original case — the comparator looks up case-insensitively
            # via .upper(), but mapping consumers expect to surface the actual
            # identifier from the source (lowercase `orders`, mixed-case `Emp`).
            table_name = table_match.group(1)
            body = self._extract_paren_body(ddl, table_match.end())
            if body is None:
                tables[table_name] = {}
                continue
            cols: Dict[str, str] = {}
            for fragment in self._split_top_level_commas(body):
                fragment = fragment.strip()
                if not fragment:
                    continue
                col_match = self.COLUMN_RE.match(fragment)
                if not col_match:
                    continue
                col_name = col_match.group(1)
                base_type = col_match.group(2).upper()
                precision = (col_match.group(3) or "").replace(" ", "")
                byte_char = col_match.group(4) or ""
                full_type = base_type + precision
                if byte_char:
                    full_type += f" {byte_char.upper()}"
                cols[col_name] = full_type
            tables[table_name] = cols
        return tables

    @staticmethod
    def _extract_paren_body(text: str, start: int) -> str | None:
        """Return the text between the next `(` after `start` and its
        matching `)`, balanced — or None if no opening paren is present."""
        try:
            open_idx = text.index("(", start)
        except ValueError:
            return None
        depth = 0
        for i in range(open_idx, len(text)):
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[open_idx + 1 : i]
        return text[open_idx + 1 :]

    @staticmethod
    def _split_top_level_commas(body: str) -> List[str]:
        """Split on commas that aren't inside nested parens — so
        `NUMBER(10,2)` stays intact while `id NUMBER, name VARCHAR2(50)`
        splits cleanly."""
        out: List[str] = []
        depth = 0
        buf: List[str] = []
        for ch in body:
            if ch == "(":
                depth += 1
                buf.append(ch)
            elif ch == ")":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                out.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
        if buf:
            out.append("".join(buf))
        return out


class SemanticAnalyzer:
    """Orchestrates semantic error detection (static and live modes)."""

    def __init__(self, llm_client):
        """
        Args:
            llm_client: LLMClient instance with detect_semantic_issues() method
        """
        self.llm = llm_client
        self.extractor = StaticDDLExtractor()

    def analyze_static(
        self,
        oracle_ddl: str,
        pg_ddl: str,
    ) -> SemanticAnalysisResult:
        """
        Static analysis: no database connections needed.
        Compares Oracle and PostgreSQL DDL text.
        """
        try:
            mappings = self.extractor.extract_type_mappings(oracle_ddl, pg_ddl)
            if not mappings:
                return SemanticAnalysisResult(
                    issues=[],
                    mode="static",
                    analyzed_objects=0,
                )

            raw_issues = self.llm.detect_semantic_issues(mappings)

            issues = []
            for issue_dict in raw_issues:
                try:
                    issues.append(
                        SemanticIssue(
                            severity=IssueSeverity(issue_dict["severity"]),
                            issue_type=IssueType(issue_dict["issue_type"]),
                            affected_object=issue_dict["affected_object"],
                            oracle_type=issue_dict["oracle_type"],
                            pg_type=issue_dict["pg_type"],
                            description=issue_dict["description"],
                            recommendation=issue_dict["recommendation"],
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse issue: {issue_dict}: {e}")
                    continue

            return SemanticAnalysisResult(
                issues=issues,
                mode="static",
                analyzed_objects=len(mappings),
            )

        except Exception as e:
            logger.error(f"Static analysis error: {e}")
            return SemanticAnalysisResult(
                issues=[],
                mode="static",
                analyzed_objects=0,
                error=str(e),
            )

    def analyze_live(
        self,
        oracle_connector,
        pg_connector,
        schema_name: Optional[str] = None,
    ) -> SemanticAnalysisResult:
        """
        Live analysis: queries both databases for actual column metadata.
        Compares Oracle column types to PostgreSQL column types.
        """
        try:
            oracle_meta = oracle_connector.get_column_metadata(schema_name)
            pg_meta = pg_connector.get_column_metadata(schema_name)

            mappings = self._join_metadata(oracle_meta, pg_meta)
            if not mappings:
                return SemanticAnalysisResult(
                    issues=[],
                    mode="live",
                    analyzed_objects=0,
                )

            raw_issues = self.llm.detect_semantic_issues(mappings)

            issues = []
            for issue_dict in raw_issues:
                try:
                    issues.append(
                        SemanticIssue(
                            severity=IssueSeverity(issue_dict["severity"]),
                            issue_type=IssueType(issue_dict["issue_type"]),
                            affected_object=issue_dict["affected_object"],
                            oracle_type=issue_dict["oracle_type"],
                            pg_type=issue_dict["pg_type"],
                            description=issue_dict["description"],
                            recommendation=issue_dict["recommendation"],
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse issue: {issue_dict}: {e}")
                    continue

            return SemanticAnalysisResult(
                issues=issues,
                mode="live",
                analyzed_objects=len(mappings),
            )

        except Exception as e:
            logger.error(f"Live analysis error: {e}")
            return SemanticAnalysisResult(
                issues=[],
                mode="live",
                analyzed_objects=0,
                error=str(e),
            )

    @staticmethod
    def _join_metadata(oracle: List[Dict], pg: List[Dict]) -> List[Dict]:
        """
        Inner join on (table_name, column_name) case-insensitively.
        Returns list of {table, column, oracle_type, pg_type}.
        """
        pg_index = {(r["table_name"].upper(), r["column_name"].upper()): r for r in pg}

        result = []
        for o in oracle:
            key = (o["table_name"].upper(), o["column_name"].upper())
            if key in pg_index:
                pg_row = pg_index[key]
                result.append(
                    {
                        "table": o["table_name"],
                        "column": o["column_name"],
                        "oracle_type": o.get("data_type", "UNKNOWN"),
                        "pg_type": pg_row.get("data_type", "UNKNOWN"),
                    }
                )

        return result
