"""Data migration package.

The orchestrator, validators, claude_planner, and tasks modules were deleted
in the dialect-agnostic refactor — they were broken in ways that made them
unsafe to ship (silent data loss in the orchestrator, SQL-injection-shaped
validators, planner running on placeholder row counts).

Real data movement is being rebuilt on top of COPY + keyset pagination +
Merkle-hash batch verification, and will land at `src/migrate/` with
`migration/checkpoint.py` re-exported for back-compat until callers move.
"""

from .checkpoint import CheckpointManager  # noqa: F401

__all__ = ["CheckpointManager"]
