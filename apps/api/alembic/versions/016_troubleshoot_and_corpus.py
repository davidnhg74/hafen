"""Two-plane storage for the troubleshoot service.

* `troubleshoot_analyses` (Plane 1) — per-user, per-call records.
  Holds the input excerpt, the AI-generated diagnosis, and the
  user's thumbs feedback. user_id is FK to `users.id`, nullable so
  anonymous (unauthenticated) calls still record (anonymous opt-in
  per the privacy policy). Tenant-scoped reads on this table use
  the same pattern as `migrations` — filter by `caller.id` in the
  router.

* `corpus_entries` (Plane 2) — anonymized aggregated learnings.
  No user_id, no DSNs, no raw schema/table names. Holds error
  signature hashes, the constructs detected, and outcome thumbs.
  This is what the future RAG retrieval reads from when looking up
  "have we seen something like this before?" — and what fine-tuning
  data eventually comes from.

Both tables get written in a single transaction per opt-in policy
(Plane 2 write is skipped for users on the Enterprise tier or any
user who toggled the opt-out).

Revision ID: 016
Revises: 015
Create Date: 2026-04-23 19:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "troubleshoot_analyses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        # Nullable: anonymous calls leave it NULL. Cloud-mode
        # authenticated calls populate it for tenant-scoped reads.
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        # Truncated + redacted — the input the analyzer actually fed
        # to Claude (post-truncation, post-redaction). NOT the raw
        # operator paste; that's discarded after the analyze call.
        sa.Column("input_excerpt", sa.Text(), nullable=False),
        sa.Column("input_byte_count", sa.Integer(), nullable=False),
        sa.Column("extracted_line_count", sa.Integer(), nullable=False),
        # Optional context the operator supplied (stage, free-text).
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("stage", sa.String(32), nullable=True),
        # Structured diagnosis from Claude — likely_cause,
        # recommended_action, code_suggestion, confidence,
        # escalate_if. JSON for flexibility; the response model is
        # owned by the service layer.
        sa.Column("diagnosis_json", postgresql.JSONB(), nullable=False),
        # Thumbs feedback. NULL = not yet rated. Populated by the
        # follow-up POST /troubleshoot/{id}/feedback endpoint.
        sa.Column("thumbs", sa.SmallInteger(), nullable=True),
    )
    op.create_table(
        "corpus_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, index=True),
        # SHA-256 of the canonicalized error signature. Lets us
        # cluster "same problem, different customer" without storing
        # the original error verbatim.
        sa.Column("error_signature_hash", sa.String(64), nullable=False, index=True),
        # Comma-joined list of error codes (ORA-01017,ORA-00942)
        # extracted from the input. Codes are universal — same for
        # everyone — so safe to keep verbatim.
        sa.Column("error_codes", sa.String(255), nullable=False),
        # Coarse signature of the affected table shape: column type
        # composition, PK arity, presence of LOB/BFILE/JSON. NO
        # actual table or column names.
        sa.Column("table_shape_signature", sa.String(255), nullable=True),
        # The recommended_action category that Claude returned —
        # used to weight which fix patterns work for this signature.
        sa.Column("fix_pattern", sa.String(255), nullable=True),
        # Outcome — null until the user rates it. Drives RAG ordering
        # for future similar queries (positive outcomes outrank
        # negative).
        sa.Column("outcome_thumbs", sa.SmallInteger(), nullable=True),
        # Where this entry came from — "troubleshoot" today; future:
        # "convert", "advise" if we extend Plane 2 to those features.
        sa.Column("source_feature", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("corpus_entries")
    op.drop_table("troubleshoot_analyses")
