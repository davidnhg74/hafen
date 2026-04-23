# CDC Design — Zero-Downtime Cutover

**Status:** design, not yet implemented.
**Owner of implementation:** whoever picks this up next session.
**License tier:** Pro (`ongoing_cdc` feature flag is already reserved in
`src/license/verifier.py`).

---

## What problem does this solve?

The current migration flow is a point-in-time snapshot: run the Runner,
data lands on the target, done. If the source DB keeps taking writes
during the migration or during cutover, those writes are lost unless the
operator freezes the source.

**Zero-downtime cutover** — keep the source live, stream every change
to the target, drain the stream at cutover, swap the app pointer with
~seconds of downtime instead of hours.

This is a known-shape feature with known-shape competitors (Oracle
GoldenGate, Debezium, AWS DMS, Striim). We don't need to invent
anything; we need to pick *which* implementation of the shape matches
our constraints: self-hosted, Oracle → Postgres, operator-friendly.

---

## Decisions that matter

### 1. Source-side capture: LogMiner (v1), not XStream or GoldenGate

| Option | Cost | Pros | Cons |
|---|---|---|---|
| **Oracle LogMiner** | Free (Standard + Enterprise) | No extra license; works on every Oracle version we support; well-documented | Query-based polling; ~seconds of latency; can't trail archive logs on Standard without careful setup |
| **Oracle XStream Outbound** | ~$23K/processor Extra Cost Option | Real streaming, <1s latency | Paid license kills our "free tier of Oracle works" promise; won't install on RDS |
| **Oracle GoldenGate** | Separate expensive product | Industry standard | Customer would replace *us* with GG if they're going to pay for GG |
| **Trigger-based capture** | Zero | Works on any DB | Production triggers on the source are a non-starter for compliance — customers will reject it |

**Pick LogMiner.** It's the only option that works for customers on
Standard Edition or RDS without forcing a license purchase that's more
expensive than our entire product.

LogMiner has a well-known query shape:

```sql
BEGIN
  DBMS_LOGMNR.START_LOGMNR(
    STARTSCN => :last_scn,
    OPTIONS  => DBMS_LOGMNR.DICT_FROM_ONLINE_CATALOG
                + DBMS_LOGMNR.COMMITTED_DATA_ONLY
                + DBMS_LOGMNR.CONTINUOUS_MINE
  );
END;
/
SELECT SCN, OPERATION, SEG_OWNER, TABLE_NAME, SQL_REDO
  FROM V$LOGMNR_CONTENTS
 WHERE SCN > :last_scn
   AND OPERATION IN ('INSERT','UPDATE','DELETE')
   AND SEG_OWNER = :schema;
```

### 2. Change stream format (v1): parsed redo, not raw

LogMiner gives you `SQL_REDO` — a string like
`UPDATE "HR"."EMP" SET "SALARY" = '5000' WHERE "ID" = '42'`. We have two
choices:

- **Re-execute SQL_REDO on the target as-is.** Wrong. Oracle and
  Postgres disagree on quoting, dialect, identifier case, date
  formatting, etc. Breaks in 30 seconds.
- **Parse SQL_REDO into a structured `Change` record.** Right. We
  reuse our existing Oracle parser (ANTLR) which already handles
  `INSERT`, `UPDATE`, `DELETE`, and reasonable SQL.

Parsed change shape:

```python
@dataclass
class Change:
    scn: int                # Oracle system change number (ordering)
    source_schema: str      # "HR"
    source_table: str       # "EMP"
    op: Literal["I", "U", "D"]
    pk: dict                # {"ID": 42}
    before: dict | None     # {"SALARY": 4500}  (UPDATE/DELETE only)
    after: dict | None      # {"SALARY": 5000}  (INSERT/UPDATE only)
    committed_at: datetime  # from V$LOGMNR_CONTENTS.TIMESTAMP
```

### 3. Persistence: Postgres table, not Kafka

For a self-hosted enterprise product, adding Kafka as a required
dependency is a deal-breaker. Operators don't want to run Kafka just
to migrate their database.

**Decision:** persist the change stream to a Postgres table on the
same DB that already holds `migrations`. Schema:

```sql
CREATE TABLE migration_cdc_changes (
  id            BIGSERIAL PRIMARY KEY,
  migration_id  UUID NOT NULL REFERENCES migrations(id) ON DELETE CASCADE,
  scn           BIGINT NOT NULL,
  source_schema TEXT NOT NULL,
  source_table  TEXT NOT NULL,
  op            CHAR(1) NOT NULL,   -- I/U/D
  pk_json       JSONB NOT NULL,
  before_json   JSONB,
  after_json    JSONB,
  committed_at  TIMESTAMPTZ NOT NULL,
  captured_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  applied_at    TIMESTAMPTZ,
  apply_error   TEXT
);

CREATE INDEX ix_cdc_migration_scn
  ON migration_cdc_changes (migration_id, scn);

CREATE INDEX ix_cdc_unapplied
  ON migration_cdc_changes (migration_id, applied_at)
  WHERE applied_at IS NULL;
```

Size concern: a busy source doing 1k changes/sec for an hour is 3.6M
rows. With UUID migration_id (~40 bytes) + JSONB payload (~200 bytes)
that's ~900 MB/hour. Auto-delete applied rows older than 24h to keep
the table bounded.

### 4. Apply strategy on the target: idempotent per-PK upsert

Apply each change by PK:

- **INSERT** → `INSERT ... ON CONFLICT (pk) DO UPDATE SET ...`
- **UPDATE** → `INSERT ... ON CONFLICT (pk) DO UPDATE SET ...`
- **DELETE** → `DELETE FROM ... WHERE pk = ...`

This means applying the same change twice is a no-op, which makes
failure-and-retry trivial. No need for XA transactions or cross-DB
two-phase commit.

**Apply ordering:** strictly by SCN per source table. SCN gives us
total ordering within an Oracle instance, which is all we need. Apply
workers pick up batches of `applied_at IS NULL` rows for a single
table, process in SCN order, mark `applied_at = NOW()`.

### 5. Cutover orchestration

Cutover is a UX problem more than an engineering problem. The
sequence:

1. Operator clicks "Start CDC" after the initial snapshot completes.
2. Background worker starts capturing changes from `last_scn`
   (persisted on MigrationRecord).
3. Apply worker drains the queue continuously. Lag is surfaced on
   the migration detail UI: "captured through SCN X, applied
   through SCN Y, lag 45s."
4. When the operator is ready to cutover, they click "Prepare
   cutover." The product:
   a. Stops accepting new app connections to the source *(this is
      the operator's job — we can't enforce it; we surface a
      prominent instruction and a "I've done it" confirm button).*
   b. Waits for capture to catch up to the latest source SCN
      (typically <5s once writes stop).
   c. Runs a final merkle-verify pass over the largest tables
      (configurable subset — full verify of a 500GB table isn't
      feasible).
   d. Reports "ready to cutover" or "still X% behind."
5. Operator points their app at the target. Cutover complete.

### 6. Failure modes + restart

- **Capture worker crashes mid-batch:** no partial rows committed
  because each batch insert is a single transaction. Restart from
  last persisted SCN.
- **Apply worker crashes mid-batch:** `applied_at` is per-row, so
  restart applies whatever wasn't marked. Idempotent upsert means
  re-applying a row is safe.
- **Source SCN rolls over:** realistic only if the source DB itself
  is reset. Product policy: abort the CDC run, require a fresh
  snapshot.
- **Target schema drift:** a new column added on the target after
  CDC started means our apply logic doesn't know about it. We skip
  silently and the target column stays at its default. Log a
  warning.
- **Source schema drift:** Oracle DDL during CDC shows up in
  LogMiner as `OPERATION='DDL'`. v1: abort the run and tell the
  operator to restart. v2: handle ADD COLUMN transparently, still
  abort on anything else.

### 7. Scope boundaries (v1 vs future)

**v1 ships:**
- LogMiner capture (Oracle source only; Postgres source via
  logical replication is a follow-up)
- Postgres-table-backed change queue
- Idempotent PK-based apply
- Manual cutover (operator-initiated)
- UI showing capture/apply lag
- SCN restart on worker crash

**v1 explicitly does NOT ship:**
- DDL replication (abort-and-restart instead)
- Multi-master / bi-directional sync
- Non-PK tables (skip with a warning; the snapshot path also requires
  PKs so this matches)
- Automatic cutover (too dangerous — must be operator-gated)
- BLOB/CLOB streaming over a certain size (cap at 4KB per value;
  larger values fetched as "SELECT on demand" from source, which is
  slow but correct)
- Oracle RAC gap-detection across nodes (v2)

### 8. Code shape (skeleton for the next session)

```
apps/api/src/services/cdc/
  __init__.py
  capture_service.py   # LogMiner polling + insert into the queue table
  apply_service.py     # pulls unapplied rows, upserts to target
  cutover.py           # "ready to cutover?" logic
  worker.py            # arq task entry points

apps/api/src/models.py
  # new: MigrationCdcChange (ORM mirror of migration_cdc_changes)
  # extend: MigrationRecord.last_captured_scn, last_applied_scn

apps/api/src/routers/cdc.py
  # POST   /api/v1/migrations/{id}/cdc/start
  # GET    /api/v1/migrations/{id}/cdc/status  → lag + counts
  # POST   /api/v1/migrations/{id}/cdc/prepare-cutover
  # POST   /api/v1/migrations/{id}/cdc/stop

apps/web/app/migrations/[id]/CdcPanel.tsx
  # Lag dashboard + Start/Prepare-cutover/Stop buttons
```

---

## What the next session should do

1. Confirm these decisions with David. The biggest is LogMiner vs.
   pursuing XStream for customers who have it licensed — I
   recommend "LogMiner only in v1, XStream in v2 as a performance
   upgrade."
2. Write alembic 013: `migration_cdc_changes` table + new SCN
   columns on `migrations`.
3. Build `capture_service.py` against a live Oracle fixture (the
   `hafen_oracle` container in docker-compose) — the LogMiner
   queries need real Oracle to test; they don't work on Postgres.
4. Build `apply_service.py` with end-to-end tests that snapshot a
   small schema, capture a few changes, apply, and verify the
   target matches.
5. UI last — the backend contract must be stable first.

Time budget for a realistic v1: **one focused multi-day session**,
maybe two. Not a single-afternoon feature.
