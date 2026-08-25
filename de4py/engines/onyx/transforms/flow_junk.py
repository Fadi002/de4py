# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Statement-level flow/junk rules.

Constant-branch resolution, unreachable-code truncation after terminators,
self-assignment removal and redundant-pass removal. All are semantics-
preserving by construction: branch tests are only resolved when they fold to
a literal scalar through the sandboxed evaluator.
"""

import ast

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule
from de4py.engines.onyx.safe_eval import safe_eval_scalar

class ConstantBranchRule(Rule):
    """Resolve ``if`` statements whose test folds to a literal scalar.
    ``while`` loops are only removed for a constant falsy test - a truthy
    constant test may be a real infinite loop whose body can ``break``."""

    name = "constant_branches"
    safety = "safe"
    event_category = "FLOW"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if isinstance(stmt, ast.If):
                    ok, value = safe_eval_scalar(stmt.test)
                    if not ok:
                        continue
                    yield Match(node=stmt, data={"taken": bool(value)})
                elif isinstance(stmt, ast.While):
                    ok, value = safe_eval_scalar(stmt.test)
                    if ok and not value and not stmt.orelse:
                        yield Match(node=stmt, data={"dead_while": True})

    def transform(self, ctx, match):
        node = match.node
        if match.data.get("dead_while"):
            return Patch(target=node, replacement=None,
                         detail="removed dead while loop")
        taken = match.data["taken"]
        branch = node.body if taken else node.orelse
        detail = "kept always-taken branch" if taken else "removed never-taken branch"
        if not branch:
            return Patch(target=node, replacement=None, detail=detail)
        return Patch(target=node, replacement=list(branch), detail=detail)


class UnreachableAfterTerminatorRule(Rule):

    name = "unreachable_after_terminator"
    safety = "safe"
    event_category = "DEAD-CODE"

    _TERMINATORS = (ast.Return, ast.Raise)

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for index, stmt in enumerate(stmts[:-1]):
                if isinstance(stmt, self._TERMINATORS):
                    yield Match(node=stmts[index + 1],
                                data={"count": len(stmts) - index - 1})
                    break

    def transform(self, ctx, match):
        count = max(1, int(match.data.get("count", 1)))
        return Patch(target=match.node, replacement=None,
                     detail=f"removed unreachable statement"
                            f"{'s' if count > 1 else ''}")


class SelfAssignmentRule(Rule):

    name = "self_assignments"
    safety = "safe"
    event_category = "DEAD-CODE"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)
                        and isinstance(stmt.value, ast.Name)
                        and stmt.targets[0].id == stmt.value.id):
                    yield Match(node=stmt)

    def transform(self, ctx, match):
        return Patch(target=match.node, replacement=None,
                     detail="removed self assignment")


class RedundantPassRule(Rule):

    name = "redundant_pass"
    safety = "safe"
    event_category = "DEAD-CODE"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            if len(stmts) <= 1:
                continue
            for stmt in stmts:
                if isinstance(stmt, ast.Pass):
                    yield Match(node=stmt)

    def transform(self, ctx, match):
        return Patch(target=match.node, replacement=None,
                     detail="removed redundant pass")


def default_flow_rules():
    return [
        ConstantBranchRule(),
        UnreachableAfterTerminatorRule(),
        SelfAssignmentRule(),
        RedundantPassRule(),
    ]
