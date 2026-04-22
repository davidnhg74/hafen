"""Oracle source dialect.

Parser, live-DB connector, and schema catalog. The parser is ANTLR-based and
emits canonical IR; the connector and catalog query Oracle data dictionary
views to produce IR-shaped objects (Table, Column, Index, Constraint, etc.).
"""
