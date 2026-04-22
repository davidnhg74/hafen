"""Static analysis over IR.

Complexity scoring, semantic risk detection, dependency graphs, permission
mapping. These run on parsed IR and produce structured findings (Diagnostics,
reports) — they do not transform code or talk to the target DB.
"""
