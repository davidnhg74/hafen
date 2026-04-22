"""Dialect-agnostic primitives.

Nothing in this package may import from `source/`, `target/`, `transforms/`, or
any other layer. The dependency direction is: source/target/transforms/ai/...
import core; core imports nothing from us. This is what makes adding a new
source dialect (MySQL, MSSQL) or target (anything) cheap.
"""
