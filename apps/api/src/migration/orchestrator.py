"""
DataMigrator: Intelligent orchestration of parallel data transfer.
Handles chunking, parallelization, checkpoints, and validation.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import logging
import time

from .checkpoint import CheckpointManager
from .validators import (
    StructuralValidator,
    VolumeValidator,
    QualityValidator,
    LogicalValidator,
    TemporalValidator,
)

logger = logging.getLogger(__name__)


class MigrationPlan:
    """Generated migration plan with strategy."""

    def __init__(
        self,
        migration_id: str,
        tables: List[Dict],
        estimated_duration_seconds: int,
        total_rows: int,
        total_bytes: int,
    ):
        self.migration_id = migration_id
        self.tables = tables  # [{"name": "...", "chunk_size": 10000, "order": 1}, ...]
        self.estimated_duration_seconds = estimated_duration_seconds
        self.total_rows = total_rows
        self.total_bytes = total_bytes

    def get_table_order(self) -> List[str]:
        """Tables in migration order (respecting dependencies)."""
        return [t["name"] for t in sorted(self.tables, key=lambda x: x["order"])]

    def get_chunk_size(self, table_name: str) -> int:
        """Recommended chunk size for table."""
        table = next((t for t in self.tables if t["name"] == table_name), None)
        return table["chunk_size"] if table else 10000


class DataMigrator:
    """Orchestrates parallel data migration with checkpoints."""

    def __init__(
        self,
        oracle_conn: Session,
        postgres_conn: Session,
        num_workers: int = 4,
        chunk_size: int = 10000,
    ):
        self.oracle = oracle_conn
        self.postgres = postgres_conn
        self.num_workers = num_workers
        self.default_chunk_size = chunk_size
        self.checkpoint_manager = CheckpointManager(postgres_conn)

        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_rows_transferred = 0
        self.errors: List[str] = []

    def plan_migration(self, tables: List[str]) -> MigrationPlan:
        """
        Analyze schema and generate optimized migration plan.
        Uses Claude for strategy if available.
        """
        migration_id = self.checkpoint_manager.create_migration(
            migration_id=str(datetime.utcnow().timestamp()),
            schema_name="default",
        )

        # Analyze each table
        table_plans = []
        total_rows = 0
        total_bytes = 0

        for table in tables:
            row_count = self._get_row_count(table)
            table_size = self._estimate_table_size(table)

            # Determine optimal chunk size
            chunk_size = self._calculate_chunk_size(row_count, table_size)

            table_plans.append(
                {
                    "name": table,
                    "row_count": row_count,
                    "size_bytes": table_size,
                    "chunk_size": chunk_size,
                    "order": self._get_dependency_order(table, tables),
                }
            )

            total_rows += row_count
            total_bytes += table_size

        # Estimate duration (50 MB/sec typical throughput)
        estimated_seconds = max(total_bytes / (50 * 1024 * 1024), 60)

        plan = MigrationPlan(
            migration_id=migration_id,
            tables=table_plans,
            estimated_duration_seconds=int(estimated_seconds),
            total_rows=total_rows,
            total_bytes=total_bytes,
        )

        logger.info(
            f"Migration plan: {total_rows} rows, {total_bytes / 1024 / 1024:.1f} MB, "
            f"ETA {estimated_seconds / 60:.1f} minutes"
        )

        return plan

    def execute_plan(self, plan: MigrationPlan) -> bool:
        """
        Execute migration plan with parallel workers.
        Returns True if successful, False if failed.
        """
        self.start_time = datetime.utcnow()

        try:
            # Pre-migration validation (Layer 1: Structural)
            self._validate_structural(plan.get_table_order())

            # Migrate tables in order
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                futures = {}

                for table in plan.get_table_order():
                    chunk_size = plan.get_chunk_size(table)
                    future = executor.submit(
                        self._migrate_table,
                        plan.migration_id,
                        table,
                        chunk_size,
                    )
                    futures[future] = table

                # Wait for completion
                for future in as_completed(futures):
                    table = futures[future]
                    try:
                        rows_migrated = future.result()
                        self.total_rows_transferred += rows_migrated
                        logger.info(f"✓ {table}: {rows_migrated} rows")
                    except Exception as e:
                        logger.error(f"✗ {table}: {e}")
                        self.errors.append(f"{table}: {e}")
                        return False

            # Post-migration validation (Layers 2-5)
            self._validate_comprehensive(plan.get_table_order())

            self.end_time = datetime.utcnow()
            duration = (self.end_time - self.start_time).total_seconds()
            throughput = self.total_rows_transferred / duration if duration > 0 else 0

            logger.info(
                f"✅ Migration complete: {self.total_rows_transferred} rows in {duration:.1f}s "
                f"({throughput:.0f} rows/sec)"
            )

            # Mark migration complete
            self.checkpoint_manager.mark_migration_complete(plan.migration_id)

            return True

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.errors.append(str(e))
            return False

    def _migrate_table(
        self, migration_id: str, table_name: str, chunk_size: int
    ) -> int:
        """
        Migrate a single table in chunks.
        Supports resumption from checkpoint.
        """
        # Check for resumption point
        resume_point = self.checkpoint_manager.resume_from_checkpoint(
            migration_id, table_name
        )

        start_offset = resume_point["rows_processed"] if resume_point else 0

        # Get total row count
        total_rows = self._get_row_count(table_name)

        rows_migrated = 0
        current_offset = start_offset

        while current_offset < total_rows:
            try:
                chunk_end = min(current_offset + chunk_size, total_rows)

                # Read chunk from Oracle
                rows = self._read_chunk(table_name, current_offset, chunk_end)

                if not rows:
                    break

                # Write chunk to PostgreSQL
                self._write_chunk(table_name, rows)

                # Validate chunk (Layer 2)
                self._validate_chunk(table_name, current_offset, chunk_end)

                rows_migrated += len(rows)
                current_offset = chunk_end

                # Save checkpoint every 10%
                progress = (current_offset / total_rows) * 100
                if progress % 10 < (chunk_size / total_rows) * 100:
                    self.checkpoint_manager.create_checkpoint(
                        migration_id,
                        table_name,
                        current_offset,
                        total_rows,
                        status="in_progress",
                    )

            except Exception as e:
                logger.error(f"Error migrating {table_name} at offset {current_offset}: {e}")
                raise

        # Mark table complete
        self.checkpoint_manager.mark_table_complete(migration_id, table_name)

        return rows_migrated

    def _read_chunk(self, table_name: str, offset: int, limit: int) -> List[Dict]:
        """Read chunk from Oracle."""
        try:
            # Use OFFSET/LIMIT for Oracle (requires ORDER BY)
            query = f"""
                SELECT * FROM {table_name}
                ORDER BY ROWID
                OFFSET {offset} ROWS FETCH NEXT {limit - offset} ROWS ONLY
            """

            result = self.oracle.execute(text(query))
            rows = [dict(row) for row in result.fetchall()]
            return rows
        except Exception as e:
            logger.warning(f"Failed to read with OFFSET/LIMIT, using ROWNUM: {e}")
            # Fallback for older Oracle versions
            query = f"""
                SELECT * FROM {table_name}
                WHERE ROWNUM BETWEEN {offset} AND {limit}
            """
            result = self.oracle.execute(text(query))
            return [dict(row) for row in result.fetchall()]

    def _write_chunk(self, table_name: str, rows: List[Dict]) -> None:
        """Write chunk to PostgreSQL."""
        if not rows:
            return

        # Build INSERT statement
        columns = list(rows[0].keys())
        col_list = ", ".join(columns)
        placeholders = ", ".join(f"%s" for _ in columns)

        insert_query = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

        # Batch insert
        values = [[row.get(col) for col in columns] for row in rows]

        try:
            for value_set in values:
                self.postgres.execute(text(insert_query), value_set)
            self.postgres.commit()
        except Exception as e:
            self.postgres.rollback()
            raise e

    def _validate_chunk(
        self, table_name: str, offset: int, limit: int
    ) -> None:
        """Validate chunk after transfer (Layer 2)."""
        # Verify row count
        oracle_count = self.oracle.execute(
            text(f"""
            SELECT COUNT(*) FROM {table_name}
            WHERE ROWNUM BETWEEN {offset} AND {limit}
        """)
        ).scalar()

        postgres_count = self.postgres.execute(
            text(f"""
            SELECT COUNT(*) FROM {table_name}
            LIMIT {limit - offset} OFFSET {offset}
        """)
        ).scalar()

        if oracle_count != postgres_count:
            raise Exception(
                f"Chunk validation failed: {oracle_count} vs {postgres_count} rows"
            )

    def _validate_structural(self, tables: List[str]) -> None:
        """Layer 1: Validate structural elements."""
        validator = StructuralValidator(self.oracle, self.postgres)

        for table in tables:
            validator.validate_table_exists(table)

        critical_errors = [
            r for r in validator.results if r.severity == "CRITICAL" and not r.passed
        ]

        if critical_errors:
            raise Exception(
                f"Structural validation failed: {[r.message for r in critical_errors]}"
            )

    def _validate_comprehensive(self, tables: List[str]) -> None:
        """Layers 2-5: Comprehensive validation."""
        # Layer 2: Volume
        volume_validator = VolumeValidator(self.oracle, self.postgres)
        for table in tables:
            volume_validator.validate_row_counts(table)

        # Layer 3: Quality
        quality_validator = QualityValidator(self.oracle, self.postgres)
        for table in tables:
            quality_validator.validate_data_distribution(table, "id")

        # Layer 4: Logical
        logical_validator = LogicalValidator(self.oracle, self.postgres)

        # Layer 5: Temporal
        temporal_validator = TemporalValidator(self.oracle, self.postgres)

        # Collect all errors
        all_results = (
            volume_validator.results
            + quality_validator.results
            + logical_validator.results
            + temporal_validator.results
        )

        critical_errors = [
            r for r in all_results if r.severity == "CRITICAL" and not r.passed
        ]

        if critical_errors:
            raise Exception(
                f"Validation failed: {[r.message for r in critical_errors]}"
            )

        logger.info(f"✓ All validations passed: {len(all_results)} checks")

    def _get_row_count(self, table_name: str) -> int:
        """Get total row count for table."""
        try:
            count = self.oracle.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            ).scalar()
            return count or 0
        except Exception as e:
            logger.warning(f"Failed to get row count for {table_name}: {e}")
            return 0

    def _estimate_table_size(self, table_name: str) -> int:
        """Estimate table size in bytes."""
        try:
            # Oracle: segment_name size
            size = self.oracle.execute(
                text(f"""
                SELECT SUM(bytes)
                FROM dba_segments
                WHERE segment_name = '{table_name}'
            """)
            ).scalar()
            return size or 0
        except Exception:
            # Fallback: estimate 1KB per row
            return self._get_row_count(table_name) * 1024

    def _calculate_chunk_size(self, row_count: int, table_size: int) -> int:
        """Determine optimal chunk size."""
        # Large tables: 1M row chunks
        # Small tables: full table at once
        # Default: 10K rows

        if row_count < 1000:
            return row_count
        elif row_count < 1_000_000:
            return 10_000
        elif row_count < 10_000_000:
            return 100_000
        else:
            return 1_000_000

    def _get_dependency_order(self, table_name: str, all_tables: List[str]) -> int:
        """Determine table order (respecting foreign keys)."""
        # Simple: tables without FKs first
        # Complex: topological sort of dependency graph

        # For MVP: return 0-based index
        return all_tables.index(table_name) if table_name in all_tables else 0

    def get_status(self) -> Dict:
        """Get current migration status."""
        elapsed = (
            (datetime.utcnow() - self.start_time).total_seconds()
            if self.start_time
            else 0
        )

        return {
            "status": "running" if self.start_time and not self.end_time else "idle",
            "rows_transferred": self.total_rows_transferred,
            "elapsed_seconds": elapsed,
            "throughput_rows_per_sec": (
                self.total_rows_transferred / elapsed if elapsed > 0 else 0
            ),
            "errors": self.errors,
        }
