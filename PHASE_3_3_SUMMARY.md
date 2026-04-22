# Phase 3.3: HITL Migration Cockpit — Implementation Summary

## Completed Features

### 1. Database Models & Migrations ✅
- **MigrationWorkflow** model: Tracks workflow state with approval gates, DBA notes, and settings
- **BenchmarkCapture** model: Stores Oracle and PostgreSQL performance metrics
- Migration functions: `setup_workflow_tables()` and `setup_benchmark_tables()`
- Properly indexed for efficient queries on status, migration_id, db_type, captured_at

### 2. LLM Client Extensions ✅
**File**: `apps/api/src/llm/client.py`

Two new methods added:
- `analyze_permission_mapping(oracle_privs_json: str) -> dict`
  - Accepts JSON of Oracle privileges (system_privs, object_privs, role_grants, dba_users)
  - Returns structured JSON with mappings, unmappable, overall_risk
  - Handles privilege mapping analysis via Claude AI

- `summarize_benchmark(report_json: str) -> str`
  - Accepts JSON benchmark comparison data
  - Returns plain text 2-3 sentence summary
  - Designed for executive-level benchmark review

### 3. Permission Analyzer ✅
**File**: `apps/api/src/analyzers/permission_analyzer.py`

Classes:
- **OraclePrivilegeExtractor**: Extracts Oracle privileges with DBA/non-DBA fallback
  - Tries DBA path first: dba_sys_privs, dba_tab_privs, dba_role_privs
  - Falls back to: session_privs, user_tab_privs for non-DBA users
  
- **PermissionMapper**: Maps Oracle privileges to PostgreSQL using Claude
  - Generates GRANT SQL statements
  - Calculates risk levels (1-10) for each privilege
  - Identifies unmappable privileges with workarounds
  
- **PermissionAnalyzer**: Main orchestrator
  - `analyze_from_connector()`: Live Oracle connection
  - `analyze_from_json()`: Direct JSON input (for testing)

Dataclasses:
- PrivilegeMapping, UnmappablePrivilege, OraclePrivileges, PermissionAnalysisResult

### 4. Benchmark Analyzer ✅
**File**: `apps/api/src/analyzers/benchmark_analyzer.py`

Classes:
- **BenchmarkCapture**: Static methods for capturing metrics
  - `capture_oracle_baseline()`: Queries v$sql, captures top 20 slowest queries, table stats
  - `capture_postgres_metrics()`: Queries pg_stat_statements (requires extension)
  
- **BenchmarkComparator**: Compares Oracle vs PostgreSQL
  - `_normalize_sql()`: Strips comments, normalizes whitespace
  - `_find_matching_query()`: Fuzzy SQL matching (0.7 threshold)
  - `compare()`: Calculates speedup_factor, verdict, calls Claude for summary

Dataclasses:
- QueryStat, TableStat, OracleBaseline, PostgresMetrics, QueryComparison, BenchmarkReport

### 5. API Endpoints ✅
**File**: `apps/api/src/main.py`

**Permission Analysis Endpoints** (1):
- `POST /api/v3/analyze/permissions`
  - Accepts: oracle_connection_id OR oracle_privileges_json
  - Returns: mappings[], unmappable[], grant_sql[], overall_risk, analyzed_at

**Workflow Endpoints** (5):
- `POST /api/v3/workflow/create` - Create new HITL workflow
- `GET /api/v3/workflow/{id}` - Get workflow details
- `POST /api/v3/workflow/{id}/approve/{step}` - Approve DBA review step (advances current_step)
- `POST /api/v3/workflow/{id}/reject/{step}` - Reject step (blocks workflow)
- `POST /api/v3/workflow/{id}/settings` - Update workflow settings
- `GET /api/v3/workflow/{id}/progress` - Get progress summary

**Benchmark Endpoints** (3):
- `POST /api/v3/benchmark/capture-oracle` - Capture Oracle v$sql baseline
- `POST /api/v3/benchmark/capture-postgres` - Capture PostgreSQL metrics
- `GET /api/v3/benchmark/compare/{migration_id}` - Compare and generate report

### 6. Frontend Components ✅

**PermissionAuditPanel.tsx**
- Props: oracleConnectionId?, rawPrivilegesJson?, autoAnalyze?
- Displays: Risk summary, GRANT SQL copy button, mapping details, unmappable privileges
- Risk color coding: Green (1-3), Yellow (4-6), Red (7-10)
- Features: Auto-analyze, manual trigger, copy-to-clipboard for SQL

**Migration Cockpit Page** (`/migration`)
- 20-step timeline across 5 phases with DBA approval gates
- Step statuses: NOT_STARTED, IN_PROGRESS, NEEDS_DBA_REVIEW, APPROVED, COMPLETED, BLOCKED, ERROR
- Visual timeline with phase organization
- Approval modal with DBA name and notes fields
- Real-time workflow polling
- Phase breakdown:
  - Phase 1 (ASSESSMENT): Steps 1-4, gate at step 3
  - Phase 2 (CONVERSION): Steps 5-8, gates at steps 6, 8
  - Phase 3 (MIGRATION PLANNING): Steps 9-11, gate at step 10
  - Phase 4 (EXECUTION): Steps 12-15
  - Phase 5 (CUTOVER): Steps 16-20, gates at steps 16, 17

**Navigation Update**
- Added "Migration" link to app navigation bar

## Testing Status

### Syntax Validation ✅
- All Python files compile successfully
- All TypeScript files are syntactically correct
- No import errors or undefined references

### Runtime Testing Needed
1. Start dev server and test API endpoints manually
2. Create workflow: POST /api/v3/workflow/create
3. Approve steps: POST /api/v3/workflow/{id}/approve/3
4. View in browser: http://localhost:3000/migration?workflow_id={id}
5. Test permission analysis with mock JSON
6. Test benchmark capture (requires Oracle/PostgreSQL connections)

## Known Limitations & Next Steps

1. **Connection Management**: 
   - Benchmark capture endpoints require connection_id → connection manager integration
   - Currently return 501 (Not Implemented) stub responses

2. **Missing Integration**:
   - LiveData progress polling (step 12 live migration)
   - Error escalation logic (step 14)
   - Post-migration scripts (step 13)

3. **Optional Enhancements**:
   - WebSocket support for real-time workflow updates
   - Email notifications on approval gates
   - Audit log for all approvals/rejections
   - Cost impact calculation per step
   - Performance comparison visualization

## Files Modified/Created

**Created**:
- apps/api/src/analyzers/permission_analyzer.py (291 lines)
- apps/api/src/analyzers/benchmark_analyzer.py (355 lines)
- apps/web/app/components/PermissionAuditPanel.tsx (287 lines)
- apps/web/app/migration/page.tsx (371 lines)

**Modified**:
- apps/api/src/main.py (+916 lines, added 9 endpoints + models)
- apps/api/src/llm/client.py (+95 lines, added 2 methods)
- apps/web/app/components/Navigation.tsx (+1 link)
- apps/api/src/migrations.py (already had schema setup)
- apps/api/src/models.py (already had dataclasses)

**Total Addition**: ~2,400 lines of new code

## Git Commits

1. `915155e` - Phase 3.3: Add HITL workflow, permission analysis, and benchmark endpoints
2. `9a37edc` - Phase 3.3: Add frontend components for HITL workflow and permission auditing
