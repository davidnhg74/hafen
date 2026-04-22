"""PostgreSQL target dialect.

Emits SQL/PL-pgSQL from canonical IR. Capabilities are version-gated (PG 14
lacks MERGE; PG 15+ has it; PG 16 adds MERGE...RETURNING; etc.). The emitter
must never produce text the targeted PG version cannot run.
"""
