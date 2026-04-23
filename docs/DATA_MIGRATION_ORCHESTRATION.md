# Data Migration Orchestration & Resilience Strategy for Hafen

**Focus:** Moving terabytes of Oracle data to PostgreSQL efficiently, with automatic recovery and repeatability guarantees.

**Goal:** AI-powered orchestration that handles failures gracefully, minimizes downtime, and allows safe rollback.

---

## 🎯 The Data Migration Problem

### Why It's Hard
- **Scale:** Oracle → PostgreSQL migrations often involve 10 TB–100 TB datasets
- **Complexity:** Foreign keys, sequences, LOBs (BLOB/CLOB), JSON, spatial data
- **Reliability:** Network failures, timeouts, out-of-memory conditions mid-migration
- **Downtime:** Every minute of cutover costs $1,000+ at enterprise scale
- **Repeatability:** Test runs must match production exactly (same data volume, constraints)

### Traditional Approach (Fails at Scale)
```
1. AWS DMS / Azure DMS (schema + data only, no logic)
2. Manual SQL exports/imports (fragile, error-prone)
3. One-shot migrations (no rollback, hard to test)
4. Hope data matches (no validation until production)
```

### Hafen's AI-Powered Approach
```
1. Smart chunking: Partition data by size + dependencies
2. Parallel transfer: Multiple streams with backpressure
3. Resumable checkpoints: Crash at 30% → resume from 30%
4. Validation-driven: Continuous row-count + checksum matching
5. Automatic rollback: Detect anomalies → revert + alert
6. Synthetic replay: Test migration on realistic data
```

---

## 🔧 AI Services for Data Migration

### 1. **AWS Glue + Claude (Recommended for AWS Shops)** ⭐⭐⭐⭐⭐

**What it is:** AWS's ETL orchestrator + Claude for intelligent migration planning

**How it helps Hafen:**
- Glue discovers source schema, generates Spark jobs for parallel transfer
- Claude analyzes job logs, detects bottlenecks, recommends partitioning strategy
- Automatic retry with exponential backoff + circuit breaker pattern
- Cost: $0.44 DPU/hr, $6.25/million objects (very cheap at scale)

**Example:**
```
User uploads: 50 GB Oracle schema with 12 tables
  ↓
Glue crawls Oracle, creates catalog
  ↓
Claude analyzes:
  ├─ ORDERS (100M rows, 50 GB) → partition by order_date (1000 chunks)
  ├─ CUSTOMERS (5M rows, 2 GB) → full transfer in 1 chunk
  ├─ ORDER_ITEMS (300M rows, 30 GB) → depends on ORDERS, defer
  └─ Recommendation: "Transfer CUSTOMERS first, then ORDERS in parallel with 8 streams"
  ↓
Glue executes transfer with Claude-recommended strategy
  ↓
Real-time: Dashboard shows 12 GB/min, ETA 4 min, 3 retries so far
  ↓
Automatic: Every 10% checkpoint validated (row counts, checksums)
```

**Implementation in Hafen:**
1. Add AWS Glue job template to Phase 3.2
2. Claude analyzes schema → generates PySpark migration code
3. Hafen UI: "Start migration" → Glue runs with streaming logs
4. On error: Auto-rollback to last checkpoint, notify user

**Cost:** $0.44 DPU/hr, typically $20–100 per migration  
**ROI:** Handles terabytes, automatic parallelization, built-in checkpoints  
**Recommended:** ✅ **Phase 3.2** (for AWS-hosted Hafen SaaS)

---

### 2. **Custom Python Migrator + Claude Planning** ⭐⭐⭐⭐

**What it is:** Hafen builds a smart migration orchestrator using Claude for strategy

**How it helps:**
- Hafen analyzes Oracle schema, generates migration plan with Claude
- Custom Python orchestrator transfers data in chunks, validates continuously
- Claude monitors logs, detects stalls, recommends remediation
- Works on-prem, hybrid, or any cloud

**Example Flow:**
```python
# Step 1: Claude analyzes schema and generates plan
claude_prompt = """
Schema analysis: 
- EMPLOYEES (1M rows, all indexed)
- SALARY_HISTORY (50M rows, partitioned by year)
- BONUSES (10M rows, depends on EMPLOYEES)

Output a migration plan with:
1. Optimal chunk size (batch size for inserts)
2. Parallelization strategy (which tables can run in parallel)
3. Dependency order (what must run first)
4. Estimated duration
5. Suggested rollback strategy
"""

plan = claude.messages.create(
    model="claude-opus-4-7",
    max_tokens=2000,
    messages=[{"role": "user", "content": claude_prompt}]
)
# Returns: "EMPLOYEES in 100K chunks (10 parallel), then SALARY_HISTORY in 1M chunks..."

# Step 2: Execute plan
migrator = DataMigrator(oracle_conn, postgres_conn)
migrator.execute_plan(plan)
# Handles: resumable checkpoints, validation, automatic rollback

# Step 3: Monitor & adapt
while migrator.is_running():
    status = migrator.get_status()
    if status.throughput < 5_MB_s:  # Stalling
        # Call Claude for remediation
        remediation = claude.analyze_bottleneck(status)
        # Returns: "Reduce batch size from 50K to 10K, increase connections"
        migrator.apply_remediation(remediation)
```

**Building Blocks:**

#### A. Smart Chunking Engine
```python
class DataChunker:
    def plan_chunks(self, table, row_count, available_memory):
        """Determine optimal chunk size based on available resources."""
        # Large tables: size chunks to fit in memory
        # Small tables: full table in one go
        # Foreign keys: small chunks to avoid lock contention
        
        if has_foreign_key(table):
            return min(chunk_size, 10_000)  # Smaller = less lock time
        elif row_count > 100_M:
            return max(chunk_size, 1_M)  # Larger = fewer round trips
        else:
            return chunk_size

class ParallelMigrator:
    def __init__(self, num_workers=4):
        self.workers = [MigrationWorker() for _ in range(num_workers)]
    
    def migrate_in_parallel(self, tables):
        """Assign tables to workers, respecting dependencies."""
        # Build dependency graph
        # CUSTOMERS → ORDERS → ORDER_ITEMS
        # Assign to workers: Worker1(CUSTOMERS), Worker2(ORDERS), etc.
        # Execute in topological order
```

#### B. Checkpoint & Resumption
```python
class CheckpointManager:
    def create_checkpoint(self, table, last_rowid, byte_offset):
        """Save state to PostgreSQL _depart_checkpoint table."""
        self.db.insert("_depart_checkpoint", {
            "table_name": table,
            "last_rowid": last_rowid,
            "byte_offset": byte_offset,
            "timestamp": now(),
            "status": "in_progress"
        })
    
    def resume_from_checkpoint(self, table):
        """Resume migration from last known good state."""
        checkpoint = self.db.query("_depart_checkpoint").filter(
            table_name == table, status == "in_progress"
        )
        if checkpoint:
            return checkpoint.last_rowid
        return 0  # Start from beginning if no checkpoint
```

#### C. Continuous Validation
```python
class ValidationEngine:
    def validate_chunk(self, oracle_rows, postgres_rows):
        """Compare transferred data against source."""
        assert len(oracle_rows) == len(postgres_rows), "Row count mismatch"
        
        for oracle_row, postgres_row in zip(oracle_rows, postgres_rows):
            # Row-by-row comparison
            for col in schema.columns:
                oracle_val = oracle_row[col]
                postgres_val = postgres_row[col]
                
                # Handle type differences (DATE, TIMESTAMP, BLOB, etc.)
                if not self.values_equal(oracle_val, postgres_val):
                    raise DataMismatchError(
                        f"Column {col}: {oracle_val} != {postgres_val}"
                    )
    
    def compute_checksum(self, rows):
        """Fast checksum for high-volume validation."""
        import hashlib
        checksum = hashlib.md5()
        for row in rows:
            checksum.update(str(row).encode())
        return checksum.hexdigest()
```

#### D. Automatic Rollback
```python
class MigrationGuardian:
    def monitor(self):
        """Detect anomalies and trigger rollback if needed."""
        while self.is_running():
            status = self.get_status()
            
            # Check for red flags
            if status.error_rate > 0.01:  # >1% errors
                self.trigger_rollback("High error rate detected")
            
            if status.data_divergence > 1000:  # >1000 rows mismatched
                self.trigger_rollback("Data integrity check failed")
            
            if status.throughput_drop > 50:  # Dropped 50% in 5 min
                self.trigger_rollback("Performance degradation detected")
            
            time.sleep(30)  # Check every 30 sec
```

**Cost:** Free (use existing infra)  
**ROI:** Full control, works anywhere, no vendor lock-in  
**Recommended:** ✅ **Phase 3.2+** (core offering for Hafen Enterprise)

---

### 3. **dbt (Data Build Tool) + Claude Orchestration** ⭐⭐⭐

**What it is:** dbt for transformation + Claude for migration strategy

**How it helps:**
- dbt models codify transformation logic (testable, versionable)
- Claude generates dbt migration scripts from Oracle SQL
- Built-in testing: row counts, null checks, uniqueness, foreign keys
- Lineage tracking: knows data flow, dependencies, impact zones

**Example:**
```yaml
# models/oracle_migration.yml
version: 2

models:
  - name: employees
    description: "Employees table (Oracle EMPLOYEES → PostgreSQL)"
    columns:
      - name: emp_id
        data_tests:
          - unique
          - not_null
      - name: salary
        data_tests:
          - accepted_values:
              values: [salary > 0]  # Custom test
          - relationships:  # Foreign key test
              to: ref('departments')
              field: dept_id

  - name: order_items
    description: "Order items (Oracle ORDER_ITEMS)"
    columns:
      - name: qty
        data_tests:
          - dbt_expectations.expect_column_values_to_be_in_set:
              value_set: [1, 2, 3, 4, 5]  # Qty can't be > 5
```

**How Claude generates this:**
```
User inputs:
- Oracle table DDL
- Validation rules from requirements

Claude outputs:
1. dbt model file (SELECT with transformations)
2. YAML test definitions
3. Snapshot model for auditing changes
4. Documentation

dbt runs: 
- Builds tables
- Runs tests (fail if row count < expected, nulls > threshold, etc.)
- Generates lineage DAG
- Creates audit trail
```

**Cost:** Free (dbt open-source)  
**ROI:** Testable, reproducible migrations  
**Recommended:** ⚠️ **Phase 3.3** (nice-to-have if dbt already in use)

---

## 📊 Recommended Architecture for Hafen

### Three-Tier Migration System

```
Tier 1: Schema (Hafen's deterministic converters)
  → Phase 2: DDL conversion (tables, indexes, constraints)
  → Validation: Constraints load without error ✓

Tier 2: Data Movement (This section)
  → Claude plans strategy (chunk size, parallelization)
  → Custom Python orchestrator executes with checkpoints
  → Continuous validation (row counts, checksums)
  → Automatic rollback on errors

Tier 3: Logic (Hafen's PL/SQL converters)
  → Phase 2: Procedure/function conversion
  → Phase 3.2: pgTAP tests validate converted code
  → Data comparison: Oracle vs. PostgreSQL results match
```

### Implementation Roadmap

**Phase 3.2 (Weeks 1-2): Data Orchestrator**
- [ ] Build DataMigrator class with chunking + checkpoints
- [ ] Implement validation engine (row counts, checksums)
- [ ] Add CLI: `hafen migrate --plan` → shows strategy, duration estimate
- [ ] Test on sample dataset (1 GB → 100 GB)

**Phase 3.2 (Weeks 3-4): Claude Integration**
- [ ] Prompt: Schema analysis → migration strategy
- [ ] Auto-generate chunk sizes, parallelization, order
- [ ] Monitor throughput, detect stalls
- [ ] Remediation suggestions (reduce batch size, add connections, etc.)

**Phase 3.3 (Month 2): Production Features**
- [ ] AWS Glue integration (for SaaS customers)
- [ ] Web UI: Real-time migration dashboard
- [ ] Automatic rollback triggers + alerting
- [ ] Post-migration audit trail (what moved, when, validation results)

---

## 🔑 Key Design Principles

### 1. **Resumable, Not Restartable**
- Failure at 30% → resume from checkpoint (1 hour)
- Not restart from 0% (3 hours, wasteful)

### 2. **Continuous Validation**
- Validate every chunk before moving forward
- Catch errors early, not in production

### 3. **Dependency-Aware**
- Can't migrate ORDERS before CUSTOMERS
- Automatic topological sort

### 4. **Graceful Degradation**
- 1 worker stalls → others keep moving
- Stalled worker timeout → skip, alert DBA
- Single table failure → don't halt everything

### 5. **Audit Trail**
- Every row movement logged (security requirement)
- Timestamps, checksum, validation results
- Compliance: "Prove no data was modified during transfer"

---

## 💰 Cost Comparison

| Approach | One-Time | Per TB | Parallelism | Rollback | Control |
|----------|----------|--------|------------|----------|---------|
| AWS DMS | $0 | $200–500 | Good | Poor | Limited |
| Hafen Custom | 1 week | $50–100 | Excellent | Automatic | Full |
| dbt | 1 week | $0 | Good | Okay | Good |
| Glue | 3 days | $50–100 | Excellent | Automatic | Good |

**Recommended:** Hafen Custom (Phase 3.2) + Glue (Phase 3.3 for SaaS)

---

## ⚠️ Common Pitfalls & Solutions

### Pitfall 1: "Lock Contention"
- Problem: Large batch inserts lock destination table
- Solution: Smaller batches (10K rows), concurrent migrations on different tables
- Claude helps: Analyzes locks, suggests batch size

### Pitfall 2: "Memory Overflow"
- Problem: Reading 1 GB chunk into Python → kills process
- Solution: Stream data in 10 MB windows, write to PostgreSQL continuously
- Claude helps: Calculates safe batch size based on available RAM

### Pitfall 3: "Silent Data Loss"
- Problem: Migration completes, but 1000 rows missing (never detected)
- Solution: Continuous validation (row counts, checksums after every chunk)
- Claude helps: Flags anomalies in logs

### Pitfall 4: "No Rollback Plan"
- Problem: Migration succeeds, but cutover fails → Can't revert
- Solution: Keep Oracle schema intact for 48 hours, re-migrate if needed
- Claude helps: Suggests rollback checkpoints, validates reversibility

### Pitfall 5: "Can't Reproduce Failures"
- Problem: Prod migration fails, can't replicate in test
- Solution: Use exact same data volume, constraints, timing
- Claude helps: Generates synthetic test datasets that match prod

---

## 🚀 Detailed Implementation Plan

### DataMigrator Class (200–300 lines)

```python
class DataMigrator:
    """Orchestrates parallel, resumable data migration."""
    
    def __init__(self, oracle_conn, postgres_conn, num_workers=4):
        self.oracle = oracle_conn
        self.postgres = postgres_conn
        self.workers = [Worker(self.postgres) for _ in range(num_workers)]
        self.checkpoints = CheckpointManager(self.postgres)
        self.validator = ValidationEngine()
    
    def plan_migration(self, schema):
        """Ask Claude for migration strategy."""
        prompt = self._build_planning_prompt(schema)
        plan = claude.messages.create(
            model="claude-opus-4-7",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_plan(plan.content[0].text)
    
    def execute_plan(self, plan):
        """Run migration with automatic checkpoints & rollback."""
        for table in plan.table_order:
            self._migrate_table(table, plan.chunk_size[table])
    
    def _migrate_table(self, table, chunk_size):
        """Migrate single table in parallel chunks."""
        total_rows = self._get_row_count(table)
        chunks = list(range(0, total_rows, chunk_size))
        
        for worker, chunk_start in zip(cycle(self.workers), chunks):
            chunk_end = min(chunk_start + chunk_size, total_rows)
            worker.queue(MigrationTask(table, chunk_start, chunk_end))
        
        # Wait for all chunks to complete
        self._wait_for_completion()
        
        # Validate table
        self.validator.validate_table(table)
    
    def _wait_for_completion(self):
        """Block until all workers finish."""
        while any(w.is_busy() for w in self.workers):
            time.sleep(1)
            self._check_for_anomalies()
    
    def _check_for_anomalies(self):
        """Monitor for stalls, errors, data divergence."""
        for error in self.get_errors():
            if error.severity == "CRITICAL":
                self.trigger_rollback(error.message)
            elif error.severity == "WARNING":
                remediation = self._ask_claude_for_fix(error)
                self._apply_remediation(remediation)

class Worker(Thread):
    """Background thread that processes migration tasks."""
    
    def __init__(self, postgres_conn):
        self.queue = Queue()
        self.postgres = postgres_conn
        self.is_busy_flag = False
        super().start()
    
    def run(self):
        while True:
            task = self.queue.get()
            self.is_busy_flag = True
            try:
                rows = self._fetch_from_oracle(task)
                self._insert_into_postgres(task, rows)
                self._create_checkpoint(task)
            except Exception as e:
                self._handle_error(task, e)
            finally:
                self.is_busy_flag = False
                self.queue.task_done()
    
    def _fetch_from_oracle(self, task):
        """Read chunk from Oracle."""
        query = f"""
            SELECT * FROM {task.table} 
            WHERE ROWNUM BETWEEN {task.start} AND {task.end}
        """
        return self.oracle.fetchall(query)
    
    def _insert_into_postgres(self, task, rows):
        """Insert rows into PostgreSQL."""
        insert_query = f"INSERT INTO {task.table} VALUES (%s, %s, ...)"
        self.postgres.executemany(insert_query, rows)
        self.postgres.commit()
```

---

## 📋 Success Criteria

✅ Migrate 100 GB Oracle schema to PostgreSQL without errors  
✅ Handle 5+ failures and resume automatically  
✅ Validate row counts, checksums, foreign keys  
✅ Generate audit trail (security compliance)  
✅ Automatic rollback on data divergence > 1000 rows  
✅ Throughput: 50+ MB/sec on modest hardware  
✅ Parallel execution: 4+ workers, no lock contention  

---

## Next Phase Deliverables

- [ ] DataMigrator class implementation
- [ ] Claude planning prompt (schema → strategy)
- [ ] Checkpoint & resumption logic
- [ ] Validation engine (row counts, checksums)
- [ ] Error handling & automatic rollback
- [ ] Documentation with runbooks
- [ ] Web UI dashboard (real-time migration progress)
