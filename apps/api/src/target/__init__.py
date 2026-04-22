"""Target dialects.

Each subpackage implements TargetDialect: `emit(IRNode) -> str`,
`connect(...)`, `capabilities() -> Capabilities`. Capabilities lets transforms
query e.g. "does the target support MERGE?" and pick the right lowering.
"""
