"""ANTLR parse-tree -> canonical IR visitor.

Skeleton. Filled in once `make grammar` produces `_generated/`. The structure
mirrors the interim parser in `parser.py` so swapping the implementation is
a one-line change in `parser.parse()`:

    from ._generated.PlSqlLexer import PlSqlLexer
    from ._generated.PlSqlParser import PlSqlParser
    from ._generated.PlSqlParserVisitor import PlSqlParserVisitor

    class IRVisitor(PlSqlParserVisitor):
        # visitCreate_table, visitProcedure_body, visitMerge_statement, ...
        ...

    def parse_via_antlr(source: str, name: str) -> Module:
        stream = InputStream(source)
        lexer = PlSqlLexer(stream)
        tokens = CommonTokenStream(lexer)
        parser = PlSqlParser(tokens)
        tree = parser.sql_script()
        v = IRVisitor()
        return v.visit(tree)

The interim parser stays in place behind the same `parse()` facade. Do not
import this module from production code until `_generated/` exists.
"""
