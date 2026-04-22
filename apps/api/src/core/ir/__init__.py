"""Canonical Intermediate Representation for database objects and PL.

Every source dialect parses INTO IR; every target dialect emits FROM IR.
Transforms operate IR -> IR. AI rewrites operate IR -> IR via prompts that
serialize a node and deserialize the response back into IR.

Filled in during the ANTLR parser pass. The contract here is intentionally
empty until the first real consumer needs a node type — we add nodes
demand-driven, not speculatively.
"""
