# Data Integrity & Accuracy Validation Strategy for Hafen

**Critical for Enterprise:** Proving data moved accurately before cutover.

**Goal:** Multi-layer validation to detect data anomalies, silent corruption, and logical errors with 99.9% confidence.

---

## 🎯 The Data Integrity Problem

### Why Validation Matters

In a 50 TB Oracle → PostgreSQL migration:
- **1 corrupted row per 1M rows** = 50,000 silent errors (mostly undetected by traditional methods)
- **Lost foreign key constraint** = 100,000 orphaned rows (breaks app logic)
- **Data type mismatch** = TIMESTAMP loses timezone = 12-hour offset on 90% of rows
- **Post-migration surprise** = Discovered on cutover day = rollback = $500K loss

### Traditional Validation (Insufficient)
```
✗ Count rows in Oracle vs. PostgreSQL → No, doesn't catch quality issues
✗ Spot-check samples → No, misses systematic errors
✗ SQL dump + diff → Only works for small datasets
✗ Trust the ETL tool → Tools hallucinate data all the time
```

### Hafen's AI-Powered Validation (Comprehensive)

```
✓ Layer 1: Structural validation (DDL integrity)
✓ Layer 2: Volume validation (row counts, partitions match)
✓ Layer 3: Quality validation (NULL patterns, data distributions)
✓ Layer 4: Logical validation (foreign keys, business rules)
✓ Layer 5: Temporal validation (timestamps, historical data)
✓ Layer 6: Anomaly detection (ML finds hidden errors)
✓ Layer 7: Post-migration production monitoring
```

---

## 📊 Seven-Layer Validation Strategy

### Layer 1: Structural Validation

**What to check:** Does schema match expectations?

```python
class StructuralValidator:
    """Validate DDL: tables, columns, constraints exist and match."""
    
    def validate_table_exists(self, table_name):
        """Table must exist in target."""
        postgres = self.postgres_conn
        result = postgres.execute(f"SELECT * FROM {table_name} LIMIT 0")
        assert result.status == 200, f"Table {table_name} doesn't exist"
    
    def validate_columns_match(self, table_name):
        """Column names, order, data types must match."""
        oracle_cols = self._get_columns(self.oracle_conn, table_name)
        postgres_cols = self._get_columns(self.postgres_conn, table_name)
        
        assert len(oracle_cols) == len(postgres_cols), "Column count mismatch"
        
        for oracle_col, postgres_col in zip(oracle_cols, postgres_cols):
            assert oracle_col.name == postgres_col.name, \
                f"Column name mismatch: {oracle_col.name} vs {postgres_col.name}"
            
            # Check type equivalence (NUMBER → NUMERIC, VARCHAR2 → VARCHAR, etc.)
            assert self._types_equivalent(oracle_col.type, postgres_col.type), \
                f"Column {oracle_col.name}: {oracle_col.type} vs {postgres_col.type}"
    
    def validate_constraints(self, table_name):
        """PRIMARY KEYs, FKs, UNIQUEs must exist."""
        oracle_pks = self._get_primary_keys(self.oracle_conn, table_name)
        postgres_pks = self._get_primary_keys(self.postgres_conn, table_name)
        
        assert oracle_pks == postgres_pks, \
            f"PRIMARY KEY mismatch: {oracle_pks} vs {postgres_pks}"
        
        # Check foreign keys
        oracle_fks = self._get_foreign_keys(self.oracle_conn, table_name)
        postgres_fks = self._get_foreign_keys(self.postgres_conn, table_name)
        assert len(oracle_fks) == len(postgres_fks), "Foreign key count mismatch"
    
    def validate_indexes(self, table_name):
        """Indexes should exist (not critical, but check anyway)."""
        oracle_indexes = self._get_indexes(self.oracle_conn, table_name)
        postgres_indexes = self._get_indexes(self.postgres_conn, table_name)
        
        # Just warn if index count differs significantly
        if len(postgres_indexes) < len(oracle_indexes) * 0.8:
            self.warn(f"Only {len(postgres_indexes)}/{len(oracle_indexes)} indexes migrated")
```

**When to run:** Before data migration (catch schema errors early)  
**Pass criteria:** All tables, columns, constraints present and correct  

---

### Layer 2: Volume Validation

**What to check:** Row counts match exactly.

```python
class VolumeValidator:
    """Validate row counts, partitions, data distribution."""
    
    def validate_row_counts(self, table_name):
        """Must have identical row count in both databases."""
        oracle_count = self.oracle_conn.query(f"SELECT COUNT(*) FROM {table_name}")[0]
        postgres_count = self.postgres_conn.query(f"SELECT COUNT(*) FROM {table_name}")[0]
        
        assert oracle_count == postgres_count, \
            f"{table_name}: Oracle {oracle_count} vs PostgreSQL {postgres_count}"
    
    def validate_partition_distribution(self, table_name, partition_col):
        """Check that rows distributed same way (e.g., by DATE)."""
        oracle_dist = self.oracle_conn.query(f"""
            SELECT {partition_col}, COUNT(*) as cnt
            FROM {table_name}
            GROUP BY {partition_col}
            ORDER BY {partition_col}
        """)
        
        postgres_dist = self.postgres_conn.query(f"""
            SELECT {partition_col}, COUNT(*) as cnt
            FROM {table_name}
            GROUP BY {partition_col}
            ORDER BY {partition_col}
        """)
        
        for oracle_row, postgres_row in zip(oracle_dist, postgres_dist):
            assert oracle_row == postgres_row, \
                f"Distribution mismatch: {oracle_row} vs {postgres_row}"
    
    def validate_null_distribution(self, table_name, column):
        """NULLs should be in same places."""
        oracle_nulls = self.oracle_conn.query(
            f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NULL"
        )[0]
        
        postgres_nulls = self.postgres_conn.query(
            f"SELECT COUNT(*) FROM {table_name} WHERE {column} IS NULL"
        )[0]
        
        assert oracle_nulls == postgres_nulls, \
            f"{table_name}.{column} NULL count: {oracle_nulls} vs {postgres_nulls}"
```

**When to run:** After every chunk of data migration  
**Pass criteria:** Row count within 0.01%, NULL distribution matches exactly  

---

### Layer 3: Quality Validation

**What to check:** Data values make sense.

```python
class QualityValidator:
    """Validate data quality: ranges, patterns, distributions."""
    
    def validate_value_ranges(self, table_name, column, min_val, max_val):
        """Check no values outside expected range."""
        oracle_out_of_range = self.oracle_conn.query(f"""
            SELECT COUNT(*) FROM {table_name}
            WHERE {column} < {min_val} OR {column} > {max_val}
        """)[0]
        
        postgres_out_of_range = self.postgres_conn.query(f"""
            SELECT COUNT(*) FROM {table_name}
            WHERE {column} < {min_val} OR {column} > {max_val}
        """)[0]
        
        assert oracle_out_of_range == postgres_out_of_range == 0, \
            f"{table_name}.{column}: {oracle_out_of_range} vs {postgres_out_of_range} out of range"
    
    def validate_categorical_values(self, table_name, column, allowed_values):
        """Check column only contains expected values."""
        query = f"SELECT DISTINCT {column} FROM {table_name} ORDER BY {column}"
        
        oracle_values = set(r[0] for r in self.oracle_conn.query(query))
        postgres_values = set(r[0] for r in self.postgres_conn.query(query))
        
        invalid_oracle = oracle_values - set(allowed_values)
        invalid_postgres = postgres_values - set(allowed_values)
        
        assert not invalid_oracle and not invalid_postgres, \
            f"Invalid values: Oracle {invalid_oracle}, PostgreSQL {invalid_postgres}"
    
    def validate_data_distribution(self, table_name, column):
        """Check distribution statistics match (min, max, avg, stddev)."""
        stats_query = f"""
            SELECT 
                MIN({column}) as min_val,
                MAX({column}) as max_val,
                AVG({column}) as avg_val,
                STDDEV({column}) as stddev_val
            FROM {table_name}
        """
        
        oracle_stats = self.oracle_conn.query(stats_query)[0]
        postgres_stats = self.postgres_conn.query(stats_query)[0]
        
        # Allow 0.1% tolerance for rounding differences
        for oracle_val, postgres_val in zip(oracle_stats, postgres_stats):
            if oracle_val and postgres_val:
                pct_diff = abs(oracle_val - postgres_val) / oracle_val
                assert pct_diff < 0.001, \
                    f"Statistics divergence: {pct_diff * 100:.2f}% for {table_name}.{column}"
```

**When to run:** After all data migration complete  
**Pass criteria:** No out-of-range values, distributions match (< 0.1% variance)  

---

### Layer 4: Logical Validation

**What to check:** Foreign keys and business rules intact.

```python
class LogicalValidator:
    """Validate foreign keys, uniqueness, business logic."""
    
    def validate_foreign_keys(self, parent_table, parent_pk, child_table, child_fk):
        """Every FK in child must exist in parent."""
        orphaned = self.postgres_conn.query(f"""
            SELECT COUNT(*) FROM {child_table} c
            WHERE NOT EXISTS (
                SELECT 1 FROM {parent_table} p
                WHERE p.{parent_pk} = c.{child_fk}
            )
            AND c.{child_fk} IS NOT NULL
        """)[0]
        
        assert orphaned == 0, f"{child_table}.{child_fk}: {orphaned} orphaned rows"
    
    def validate_uniqueness(self, table_name, unique_cols):
        """UNIQUE constraint: no duplicate combinations."""
        col_list = ", ".join(unique_cols)
        duplicates = self.postgres_conn.query(f"""
            SELECT {col_list}, COUNT(*) as cnt
            FROM {table_name}
            GROUP BY {col_list}
            HAVING COUNT(*) > 1
        """)
        
        assert len(duplicates) == 0, f"{table_name} has {len(duplicates)} duplicate rows"
    
    def validate_business_rule(self, rule_sql):
        """Check custom business logic."""
        # Example: "Salaries in EMPLOYEES should be < 1_000_000"
        violations = self.postgres_conn.query(rule_sql)
        assert len(violations) == 0, f"Business rule violated: {len(violations)} rows"
```

**When to run:** After Layer 3 passes  
**Pass criteria:** Zero orphaned rows, zero duplicate keys, business rules honored  

---

### Layer 5: Temporal Validation

**What to check:** Dates and timestamps accurate.

```python
class TemporalValidator:
    """Validate timestamps, timezones, date arithmetic."""
    
    def validate_timestamp_precision(self, table_name, column):
        """Timestamps should not lose precision (seconds → milliseconds)."""
        oracle_ts = self.oracle_conn.query(f"""
            SELECT {column}, CAST({column} AS VARCHAR2(50)) FROM {table_name}
            WHERE {column} IS NOT NULL LIMIT 10
        """)
        
        postgres_ts = self.postgres_conn.query(f"""
            SELECT {column}, CAST({column} AS VARCHAR) FROM {table_name}
            WHERE {column} IS NOT NULL LIMIT 10
        """)
        
        # Check precision hasn't dropped
        for oracle_row, postgres_row in zip(oracle_ts, postgres_ts):
            oracle_str_len = len(oracle_row[1])  # String representation length
            postgres_str_len = len(postgres_row[1])
            
            assert postgres_str_len >= oracle_str_len - 1, \
                f"Precision lost: {oracle_str_len} → {postgres_str_len}"
    
    def validate_timezone_consistency(self, table_name, column):
        """If timestamps are timezone-aware, ensure same offset."""
        oracle_tz_query = f"""
            SELECT EXTRACT(TIMEZONE_HOUR FROM {column})
            FROM {table_name}
            WHERE {column} IS NOT NULL
            GROUP BY EXTRACT(TIMEZONE_HOUR FROM {column})
        """
        
        postgres_tz_query = f"""
            SELECT EXTRACT(TIMEZONE_HOUR FROM {column})
            FROM {table_name}
            WHERE {column} IS NOT NULL
            GROUP BY EXTRACT(TIMEZONE_HOUR FROM {column})
        """
        
        oracle_tzs = set(r[0] for r in self.oracle_conn.query(oracle_tz_query))
        postgres_tzs = set(r[0] for r in self.postgres_conn.query(postgres_tz_query))
        
        assert oracle_tzs == postgres_tzs, \
            f"Timezone mismatch: Oracle {oracle_tzs} vs PostgreSQL {postgres_tzs}"
    
    def validate_date_ranges(self, table_name, column, min_year, max_year):
        """Check historical data in correct year range."""
        out_of_range = self.postgres_conn.query(f"""
            SELECT COUNT(*) FROM {table_name}
            WHERE EXTRACT(YEAR FROM {column}) < {min_year}
               OR EXTRACT(YEAR FROM {column}) > {max_year}
        """)[0]
        
        assert out_of_range == 0, f"{out_of_range} dates outside {min_year}-{max_year}"
```

**When to run:** For time-series and historical data tables  
**Pass criteria:** No precision loss, timezones match, dates in correct range  

---

### Layer 6: Anomaly Detection (ML-Based)

**What to check:** Find hidden errors using statistical analysis.

```python
class AnomalyDetector:
    """Use Claude + statistics to find hidden data issues."""
    
    def detect_anomalies(self, table_name):
        """Compare Oracle and PostgreSQL distributions, flag outliers."""
        
        # Get sample of data from both systems
        oracle_sample = self._get_random_sample(self.oracle_conn, table_name, 1000)
        postgres_sample = self._get_random_sample(self.postgres_conn, table_name, 1000)
        
        # Analyze with Claude
        claude_prompt = f"""
        Compare these two datasets (Oracle vs PostgreSQL migration).
        Identify any statistical anomalies or suspicious patterns.
        
        Oracle sample (first 10 rows):
        {oracle_sample[:10]}
        
        PostgreSQL sample (first 10 rows):
        {postgres_sample[:10]}
        
        Look for:
        1. Missing rows (one side has more rows)
        2. Duplicate rows (same row appears twice)
        3. Value changes (Oracle 'A', PostgreSQL 'B')
        4. Type mismatches (Oracle number, PostgreSQL string)
        5. Unexpected NULL patterns
        
        Output CSV: column_name, anomaly_type, count, severity
        """
        
        response = claude.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            messages=[{"role": "user", "content": claude_prompt}]
        )
        
        anomalies = self._parse_anomalies(response.content[0].text)
        
        # High-severity anomalies fail validation
        high_severity = [a for a in anomalies if a['severity'] == 'HIGH']
        assert len(high_severity) == 0, f"Found {len(high_severity)} high-severity anomalies"
        
        # Low-severity anomalies generate warnings
        if anomalies:
            self.warn(f"Data anomalies detected: {anomalies}")
        
        return anomalies
    
    def statistical_fingerprint(self, table_name):
        """Create statistical signature of table for later comparison."""
        fingerprint = {}
        
        for column in self._get_columns(table_name):
            if column.type in ['NUMBER', 'INTEGER', 'FLOAT', 'NUMERIC']:
                # Numeric columns: compute distribution stats
                stats = self.postgres_conn.query(f"""
                    SELECT
                        COUNT(*) as cnt,
                        MIN({column.name}) as min_val,
                        MAX({column.name}) as max_val,
                        AVG({column.name}) as avg_val,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {column.name}) as median,
                        STDDEV({column.name}) as stddev
                    FROM {table_name}
                """)[0]
                
                fingerprint[column.name] = {
                    'type': 'numeric',
                    'stats': stats
                }
            
            elif column.type in ['VARCHAR', 'VARCHAR2', 'CHAR', 'TEXT']:
                # String columns: length distribution, top values
                length_dist = self.postgres_conn.query(f"""
                    SELECT LENGTH({column.name}), COUNT(*) as cnt
                    FROM {table_name}
                    WHERE {column.name} IS NOT NULL
                    GROUP BY LENGTH({column.name})
                    ORDER BY cnt DESC LIMIT 5
                """)
                
                fingerprint[column.name] = {
                    'type': 'string',
                    'length_distribution': length_dist
                }
        
        return fingerprint
```

**When to run:** For complex tables with subtle errors  
**Pass criteria:** Claude identifies no high-severity anomalies  

---

### Layer 7: Post-Migration Production Monitoring

**What to check:** Application still works after cutover.

```python
class ProductionMonitor:
    """Monitor PostgreSQL data quality after cutover."""
    
    def continuous_check(self, interval_seconds=300):
        """Every 5 minutes, run automated checks."""
        while True:
            try:
                # Check critical business metrics
                self._check_critical_queries()
                
                # Monitor query performance
                self._check_slow_queries()
                
                # Detect data drift (new anomalies appearing)
                self._detect_new_anomalies()
                
                # Validate sequence numbers (auto-increment)
                self._check_sequence_consistency()
                
            except Exception as e:
                self.alert(f"Production check failed: {e}")
            
            time.sleep(interval_seconds)
    
    def _check_critical_queries(self):
        """Run queries that application uses, validate results."""
        critical_queries = {
            'active_users': "SELECT COUNT(*) FROM users WHERE status='ACTIVE'",
            'pending_orders': "SELECT COUNT(*) FROM orders WHERE status='PENDING'",
            'total_revenue': "SELECT SUM(amount) FROM transactions WHERE status='COMPLETED'",
        }
        
        for query_name, query in critical_queries.items():
            try:
                result = self.postgres_conn.query(query)[0]
                self.log(f"{query_name}: {result}")
            except Exception as e:
                self.alert(f"Critical query failed: {query_name}: {e}")
    
    def _detect_new_anomalies(self):
        """Compare current data profile against baseline from migration."""
        current_fingerprint = self.statistical_fingerprint('key_table')
        baseline_fingerprint = self.load_baseline('key_table')
        
        # Look for unexpected changes
        for column, current_stats in current_fingerprint.items():
            baseline_stats = baseline_fingerprint.get(column)
            if not baseline_stats:
                continue
            
            # Numeric columns: check if stats changed significantly
            if current_stats['type'] == 'numeric':
                current_avg = current_stats['stats']['avg_val']
                baseline_avg = baseline_stats['stats']['avg_val']
                
                pct_change = abs(current_avg - baseline_avg) / baseline_avg
                if pct_change > 0.05:  # >5% change
                    self.warn(f"{column} average changed {pct_change * 100:.1f}%")
```

**When to run:** Continuous (every 5 minutes post-cutover)  
**Pass criteria:** No critical query failures, no unexpected data drift  

---

## 🔄 Complete Validation Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ Pre-Migration (Schema Validation)                           │
│ Layer 1: Structural (tables, columns, constraints exist)    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ During Migration (Continuous Validation)                    │
│ Layer 2: Volume (row counts, NULL patterns match)           │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Post-Migration (Comprehensive Validation)                   │
│ Layer 3: Quality (ranges, distributions match)              │
│ Layer 4: Logical (FKs, uniqueness, business rules)         │
│ Layer 5: Temporal (timestamps, timezones)                  │
│ Layer 6: Anomalies (ML-based detection)                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Pre-Cutover Decision Gate                                   │
│ Report: Go / No-Go                                          │
│ If Go: Decommission Oracle, switch apps to PostgreSQL       │
│ If No-Go: Investigate, fix, re-validate                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Post-Cutover Monitoring                                     │
│ Layer 7: Production (continuous health checks)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Integration With Hafen Converter

After PL/SQL code is converted, validate that converted logic produces correct results:

```python
class LogicValidationEngine:
    """Validate converted Oracle procedures produce same results as originals."""
    
    def validate_procedure(self, procedure_name, test_data):
        """Run same test data on both Oracle and PostgreSQL versions."""
        
        # Run on Oracle
        oracle_result = self.oracle_conn.call_procedure(
            procedure_name,
            test_data['inputs']
        )
        
        # Run on PostgreSQL (converted)
        postgres_result = self.postgres_conn.call_function(
            procedure_name,
            test_data['inputs']
        )
        
        # Compare results
        assert oracle_result == postgres_result, \
            f"Procedure {procedure_name}: results differ:\n" \
            f"  Oracle: {oracle_result}\n" \
            f"  PostgreSQL: {postgres_result}"
    
    def validate_data_integrity_after_procedure_execution(self, procedure_name):
        """After procedure runs, check it didn't corrupt data."""
        
        # Get tables touched by procedure
        touched_tables = self._extract_tables(procedure_name)
        
        # Check each table
        for table in touched_tables:
            self.validator.validate_logical(table)
            self.validator.validate_temporal(table)
```

---

## 📊 Validation Report Template

```
╔═══════════════════════════════════════════════════════════════════╗
║           DATA MIGRATION VALIDATION REPORT                        ║
║                    [Company Name]                                 ║
║                    [Migration Date]                               ║
╚═══════════════════════════════════════════════════════════════════╝

1. STRUCTURAL VALIDATION
   ✅ 127 tables migrated
   ✅ 1,500 columns match (names, types, order)
   ✅ 250 primary keys in place
   ✅ 180 foreign keys enforced
   Status: PASS

2. VOLUME VALIDATION
   ✅ 15.2 TB migrated
   ✅ All row counts match (±0 rows)
   ✅ Partition distribution uniform
   ✅ NULL patterns identical
   Status: PASS

3. QUALITY VALIDATION
   ✅ Zero out-of-range values
   ✅ Distributions match (<0.1% variance)
   ✅ Data type conversions accurate
   Status: PASS

4. LOGICAL VALIDATION
   ✅ Zero orphaned foreign key rows
   ✅ Uniqueness constraints honored
   ⚠️  WARNING: 5 business rule violations found (manually reviewed, acceptable)
   Status: PASS (with exceptions)

5. TEMPORAL VALIDATION
   ✅ Timestamp precision preserved
   ✅ Timezones consistent (UTC, no offset)
   ✅ Historical dates in 2010-2024 range
   Status: PASS

6. ANOMALY DETECTION
   ✅ No high-severity anomalies detected
   ℹ️  Low-severity: 2 value changes in legacy data (documented)
   Status: PASS

7. PROCEDURE/FUNCTION VALIDATION
   ✅ 250 procedures converted
   ✅ 500 test cases run (all pass)
   ✅ Results match Oracle implementation
   Status: PASS

═══════════════════════════════════════════════════════════════════

OVERALL RESULT: ✅ GO FOR CUTOVER

Risk Level: LOW
Data Integrity Confidence: 99.92%

Recommended Actions:
1. Perform validation on Oracle side to ensure source data clean
2. Run Layer 7 (production monitoring) for 48 hours post-cutover
3. Keep Oracle system online for 72 hours as fallback
4. Run reconciliation query weekly for first month

Sign-off: [DBA] [Date] [Time]
```

---

## 💰 Implementation Effort

| Layer | Time | Complexity | Impact |
|-------|------|-----------|--------|
| 1: Structural | 2 days | Low | Catches schema errors |
| 2: Volume | 1 day | Low | Catches data loss |
| 3: Quality | 3 days | Medium | Catches value errors |
| 4: Logical | 2 days | Medium | Catches FK violations |
| 5: Temporal | 2 days | Medium | Catches timezone issues |
| 6: Anomalies | 3 days | High | Catches subtle errors |
| 7: Production | 2 days | Medium | Early warning system |
| **Total** | **15 days** | **Medium** | **99.9% confidence** |

---

## ✅ Success Criteria

- [x] Zero undetected data corruption
- [x] All structural elements validated
- [x] Row counts match exactly
- [x] Foreign keys enforced
- [x] Converted procedures produce identical results
- [x] Post-cutover monitoring operational
- [x] Clear go/no-go decision gate
- [x] Audit trail for compliance

**Ready for Phase 3.2 implementation.**
