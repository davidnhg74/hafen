"""IR -> IR transformations.

Each transform is a Visitor that rewrites the IR tree. Transforms are
dialect-aware via the (SourceDialect, TargetDialect) pair in Context but
operate on the canonical IR — they never call source-specific or
target-specific code directly.

Examples: type_map (NUMBER -> NUMERIC), function_map (NVL -> COALESCE),
connect_by (CONNECT BY -> recursive CTE), package (PACKAGE -> schema +
functions + GUC for state).
"""
