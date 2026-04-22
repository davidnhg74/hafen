"""Re-export for the new layout. Real module lives at src/migration/checkpoint.py
until the migration/ -> migrate/ move completes in the data-movement pass.
"""

from ..migration.checkpoint import CheckpointManager, _to_uuid, MigrationCheckpoint  # noqa: F401
