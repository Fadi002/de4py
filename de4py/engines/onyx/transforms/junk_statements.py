# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast

from de4py.engines.onyx.constant_eval import _is_pure_expr
from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule


class JunkStatementsRule(Rule):

    name = "junk_statements"
    safety = "safe"
    event_category = "DEAD-CODE"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if (isinstance(stmt, ast.Expr)
                        and not isinstance(stmt.value,
                                           (ast.Yield, ast.YieldFrom, ast.Await))
                        and _is_pure_expr(stmt.value)
                        and not isinstance(stmt.value, ast.Constant)):
                    yield Match(node=stmt)

    def transform(self, ctx, match):
        return Patch(target=match.node, replacement=None,
                     detail="removed no-op expression")
