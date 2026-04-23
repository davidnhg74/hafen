"""Add migration_schedules table + spawned_from_schedule_id on migrations.

Schedules are 1:1 with a migration for v1 — the migration row acts as
the template, the schedule says "run this on a cron." Each fire
clones the template into a fresh migration row (new id, reset status
/ timing / counts) and enqueues it through the existing arq path.
`spawned_from_schedule_id` on migrations gives operators a reverse
lookup: "show me all past runs of this schedule".

Revision ID: 011
Revises: 010
Create Date: 2026-04-23 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "migration_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "migration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migrations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cron_expr", sa.String(length=120), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'UTC'"),
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column(
            "last_run_migration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migrations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_run_status", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_migration_schedules_next_run_at",
        "migration_schedules",
        ["next_run_at"],
    )

    op.add_column(
        "migrations",
        sa.Column(
            "spawned_from_schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_migrations_spawned_from_schedule_id",
        "migrations",
        ["spawned_from_schedule_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_migrations_spawned_from_schedule_id", table_name="migrations")
    op.drop_column("migrations", "spawned_from_schedule_id")
    op.drop_index(
        "ix_migration_schedules_next_run_at", table_name="migration_schedules"
    )
    op.drop_table("migration_schedules")
