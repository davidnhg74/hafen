"""Source dialects.

Each subpackage (`oracle/`, future `mysql/`, `mssql/`, ...) implements the
SourceDialect protocol from `source.base`: `parse(text) -> IRNode`,
`introspect(connection) -> Catalog`. The rest of the platform never branches
on dialect — it dispatches through the protocol.
"""
