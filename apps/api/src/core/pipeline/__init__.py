"""Stage abstraction for transformation pipelines.

A migration is a sequence of stages: parse -> normalize -> transform -> emit ->
verify. Each stage takes a typed Context, mutates it, emits Diagnostics, and
hands off. Stages are pure where possible; side effects live at the edges
(connectors, AI calls).
"""
