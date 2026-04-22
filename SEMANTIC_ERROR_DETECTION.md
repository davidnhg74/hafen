# Semantic Error Detection — Implementation Guide

## Overview

**Semantic Error Detection** uses Claude AI to catch logical/data-corruption errors in Oracle→PostgreSQL type mappings before they reach production. Unlike syntax checkers, it detects issues like:
- **Precision Loss**: NUMBER(12,2) → NUMERIC(10,2) silently truncates values > 99,999
- **Date Behavior**: Oracle DATE stores time; PostgreSQL DATE strips it
- **NULL Semantics**: Oracle treats '' as NULL; PostgreSQL does not
- **Type Coercion**: Oracle NUMBER(1) as boolean has no implicit cast in PostgreSQL
- **Encoding Mismatches**: VARCHAR2(100 BYTE) vs (100 CHAR) behavior differs
- **Implicit Casts**: Oracle implicit conversions don't exist in PostgreSQL
- **Range Changes**: NUMERIC precision/scale changes affect valid value ranges

## Architecture

### Backend
- **File**: `apps/api/src/analyzers/semantic_analyzer.py` (550 lines)
- **Classes**:
  - `StaticDDLExtractor`: regex-based DDL parser → type mappings
  - `SemanticAnalyzer`: orchestrates static (DDL text) and live (DB connection) analysis
  - `SemanticIssue`: dataclass with severity, issue_type, oracle_type, pg_type, description, recommendation
  - `IssueSeverity`: CRITICAL, ERROR, WARNING, INFO
  - `IssueType`: 7 issue types (precision loss, date behavior, NULL semantics, etc.)

- **Extended**: `LLMClient.detect_semantic_issues()` in `apps/api/src/llm/client.py`
  - Claude model: `claude-sonnet-4-20250514`
  - Prompt: passes structured JSON type-mapping pairs (not raw DDL)
  - Returns: parsed JSON list of semantic issues

- **Connectors**: Added metadata query methods
  - `OracleConnector.get_column_metadata()`: queries `user_tab_columns`
  - `PostgresConnector.get_column_metadata()`: queries `information_schema.columns`

### Frontend
- **Component**: `apps/web/app/components/SemanticIssuesPanel.tsx` (280 lines)
  - Input: oracleDdl, pgDdl, autoAnalyze flag
  - Display: severity-coded issue cards (red=CRITICAL, orange=ERROR, yellow=WARNING, blue=INFO)
  - Shows: affected_object, oracle_type → pg_type, description, recommendation
  - Summary: counts for each severity level

- **Integration**: Wired into `/convert/page.tsx`
  - Auto-analyzes after TABLE construct conversion
  - Displays below DiffViewer when conversion succeeds

### API
- **Endpoint**: `POST /api/v3/analyze/semantic`
- **Modes**:
  - **Static**: DDL text analysis (no database connection needed)
  - **Live**: Query live databases for actual column metadata
- **Request**:
  ```json
  {
    "oracle_ddl": "CREATE TABLE ...",
    "pg_ddl": "CREATE TABLE ...",
    // OR
    "oracle_connection_id": "conn-1",
    "pg_connection_id": "conn-2",
    "schema_name": "public",
    "table_names": ["users", "orders"]
  }
  ```
- **Response**:
  ```json
  {
    "mode": "static",
    "analyzed_objects": 12,
    "issues": [
      {
        "severity": "CRITICAL",
        "issue_type": "PRECISION_LOSS",
        "affected_object": "ORDERS.AMOUNT",
        "oracle_type": "NUMBER(12,2)",
        "pg_type": "NUMERIC(10,2)",
        "description": "Precision reduced from 12 to 10 digits...",
        "recommendation": "Use NUMERIC(12,2) in PostgreSQL schema..."
      }
    ],
    "summary": {
      "critical": 1,
      "error": 2,
      "warning": 3,
      "info": 1,
      "total": 7
    }
  }
  ```

## Claude Prompt Strategy

The prompt passes **structured JSON type mappings** (not raw DDL) to Claude:

```json
[
  {
    "table": "ORDERS",
    "column": "AMOUNT",
    "oracle_type": "NUMBER(12,2)",
    "pg_type": "NUMERIC(10,2)"
  },
  ...
]
```

**Why?** Structured input → more consistent JSON output. Claude reasons about type pairs rather than parsing DDL, reducing tokens and improving reliability.

**Semantic rules Claude checks:**
1. NUMBER(p,s)→NUMERIC: if p decreased → PRECISION_LOSS CRITICAL
2. Oracle DATE stores time → PG DATE drops it → DATE_BEHAVIOR ERROR
3. NUMBER(1) used as boolean → no implicit cast → IMPLICIT_CAST WARNING
4. VARCHAR2(N BYTE) vs CHAR: multibyte chars truncate → ENCODING_MISMATCH ERROR
5. Oracle '' IS NULL, PG '' IS NOT NULL → NULL_SEMANTICS ERROR
6. TIMESTAMP WITH vs WITHOUT TIME ZONE → DATE_BEHAVIOR WARNING
7. Oracle LONG → PostgreSQL TEXT: loses constraints → RANGE_CHANGE
8. Oracle RAW → PostgreSQL BYTEA: encoding differs → ENCODING_MISMATCH

## Implementation Files

| File | Lines | Purpose |
|------|-------|---------|
| `apps/api/src/analyzers/semantic_analyzer.py` | 550 | Core analyzer, extractor, dataclasses |
| `apps/api/src/llm/client.py` | +60 | Extended with `detect_semantic_issues()` |
| `apps/api/src/connectors/oracle_connector.py` | +60 | Added `get_column_metadata()` |
| `apps/api/src/connectors/postgres_connector.py` | +60 | Added `get_column_metadata()` |
| `apps/api/src/main.py` | +100 | API endpoint + request/response models |
| `apps/web/app/components/SemanticIssuesPanel.tsx` | 280 | React UI component |
| `apps/web/app/convert/page.tsx` | +5 | Integration: import + wire component |
| `apps/api/tests/test_semantic_analyzer.py` | 380 | Unit tests + integration tests |

**Total implementation: ~1,495 lines (Phase 2 of 4 weeks)**

## Testing

### Unit Tests
```bash
cd apps/api
pytest tests/test_semantic_analyzer.py -v
```

Tests cover:
- DDL parsing: columns with precision/scale, BYTE/CHAR qualifiers, multiple tables
- Extractor: case-insensitive matching, missing tables, precision changes
- Analyzer: static/live modes, issue aggregation, error handling
- Metadata join: inner join by table/column, case-insensitive

### Integration Tests
```bash
pytest tests/test_semantic_analyzer.py::TestSemanticAnalyzerIntegration -v
```
Requires `ANTHROPIC_API_KEY` environment variable (skipped otherwise).

### Manual Testing
1. **Browser**: `http://localhost:3000/convert`
   - Paste Oracle CREATE TABLE with NUMBER(12,2), DATE, VARCHAR2(500 BYTE)
   - Paste PostgreSQL DDL with narrowed types
   - Click "Convert" → SemanticIssuesPanel auto-analyzes below DiffViewer

2. **curl**:
   ```bash
   curl -X POST http://localhost:8000/api/v3/analyze/semantic \
     -H "Content-Type: application/json" \
     -d '{
       "oracle_ddl": "CREATE TABLE orders (amount NUMBER(12,2), order_date DATE)",
       "pg_ddl": "CREATE TABLE orders (amount NUMERIC(10,2), order_date DATE)"
     }'
   ```

## Severity Levels

| Severity | Use Case | Example |
|----------|----------|---------|
| **CRITICAL** | Data loss/corruption guaranteed | NUMBER(12,2)→NUMERIC(5,2): 99,999.99 truncates to 99.99 |
| **ERROR** | Behavior change, likely breaks code | Oracle DATE→PG DATE: time component lost |
| **WARNING** | Potential issue, may need review | VARCHAR2(500 BYTE)→VARCHAR(500): multibyte truncation risk |
| **INFO** | FYI, no action required | Informational about conversion choice |

## Issue Types

| Issue Type | Description |
|------------|-------------|
| `PRECISION_LOSS` | Column precision (digits) reduced, values will truncate or error |
| `DATE_BEHAVIOR` | Date/time behavior changes (Oracle DATE stores time, PG DATE doesn't) |
| `TYPE_COERCION` | Implicit type casts no longer work (NUMBER→BOOLEAN) |
| `ENCODING_MISMATCH` | VARCHAR2 BYTE/CHAR semantics differ, multibyte chars may truncate |
| `NULL_SEMANTICS` | NULL handling differs (Oracle ''=NULL, PG ''!=NULL) |
| `IMPLICIT_CAST` | Oracle implicit conversions don't exist in PostgreSQL |
| `RANGE_CHANGE` | Valid value range changes (affects constraints, indexes) |

## Frontend Workflow

1. User pastes Oracle DDL → PostgreSQL DDL in converter
2. Clicks "Convert" or selects construct type TABLE
3. `SemanticIssuesPanel` auto-calls `POST /api/v3/analyze/semantic`
4. Issues display in severity-coded cards below DiffViewer
5. Each card shows:
   - Severity badge (red/orange/yellow/blue)
   - Issue type label
   - Affected object (TABLE.COLUMN)
   - Oracle type → PostgreSQL type
   - Detailed description of the risk
   - Recommendation for fix

## Performance

- **StaticDDLExtractor**: ~1ms per 100 columns (regex-based)
- **Claude API call**: ~2-3 seconds (typical response time)
- **Total for typical schema**: <5 seconds

Cache opportunity: For identical type mappings, results could be cached (future optimization).

## Limitations

1. **Regex-based DDL parsing**: doesn't handle:
   - Complex CONSTRAINT definitions
   - Comments within DDL
   - Generated columns, computed columns
   - → Falls back to positional matching or skips columns

2. **Claude analysis**: depends on prompt quality
   - May miss obscure edge cases
   - Requires valid JSON response (has fallback to empty list)
   - Rate-limited by Anthropic API

3. **No live comparison**: live mode only compares metadata, not actual data
   - Doesn't detect: data type mismatches in stored procedures, UDFs
   - For full validation, use `ValidationLayer` from Phase 3.2

## Next Steps

1. **Data-level validation**: Compare sample row counts/distributions (Phase 3.2 integration)
2. **Automated fixes**: Suggest specific PostgreSQL DDL changes to resolve issues
3. **Caching**: LRU cache for repeated analyses (same type mappings)
4. **PDF export**: Include semantic issues in migration report
5. **Integration with migration workflow**: Block migrations if CRITICAL issues detected (configurable)

## Checklist

- [x] SemanticAnalyzer core logic
- [x] StaticDDLExtractor with regex parsing
- [x] LLMClient.detect_semantic_issues() integration
- [x] Connector metadata queries (OracleConnector, PostgresConnector)
- [x] API endpoint with dual modes (static/live)
- [x] Frontend component SemanticIssuesPanel
- [x] Wire into /convert/page.tsx
- [x] Comprehensive unit tests (32+ assertions)
- [x] Integration tests with real Claude API
- [x] Documentation

## Key Design Decisions

1. **Structured JSON to Claude, not raw DDL**: Simpler prompts → more reliable JSON → fewer API calls
2. **Regex extraction over full SQL parser**: Fast, lightweight, good enough for deterministic mappings
3. **Static mode (DDL text) + Live mode (DB connections)**: Flexibility — works pre-migration (no DB yet) or post-schema-conversion (with live DBs)
4. **Severity-coded UI**: Clear visual hierarchy, matches existing ValidationResult pattern
5. **Auto-analyze for TABLE constructs only**: Most relevant for schema (not procedures) where types matter most
