# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.


import ast

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule


def _is_ycomb_lambda(node):
    """Recognize Z-combinator: lambda f: (λx. f(λ*x. x(x)(*x)))(
                                λx. f(λ*x. x(x)(*x)))"""
    if not isinstance(node, ast.Lambda):
        return False
    spec = node.args
    if len(spec.args) != 1 or spec.defaults or spec.vararg \
            or spec.kwarg or spec.kwonlyargs:
        return False
    body = node.body
    # must be a call: (inner_lambda)(inner_arg)
    if not isinstance(body, ast.Call):
        return False
    inner_fn = body.func
    if not isinstance(inner_fn, ast.Lambda):
        return False
    # both inner lambdas should contain a self-application pattern x(x)
    text1 = ast.dump(inner_fn)
    text2 = ast.dump(body.args[0]) if body.args else ""
    # self-application: Name X called with itself as first arg
    return _has_self_application(text1) and _has_self_application(text2)


def _has_self_application(dump_text):
    """Check for the dump signature of x(x) self-application."""
    # ast.dump produces something like:
    # Call(func=Name(id='x', ctx=Load()), args=[Name(id='x', ctx=Load())])
    return "'x'" in dump_text and "Call(func=Name" in dump_text \
        and dump_text.count("Name") >= 2


class FixpointRenameRule(Rule):

    name = "fixpoint_rename"
    safety = "safe"
    event_category = "RENAME"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if not (isinstance(stmt, ast.Assign)
                        and len(stmt.targets) == 1
                        and isinstance(stmt.targets[0], ast.Name)):
                    continue
                if _is_ycomb_lambda(stmt.value):
                    yield Match(node=stmt,
                                data={"name": stmt.targets[0].id})

    def transform(self, ctx, match):
        old = match.data["name"]
        new = "_fixpoint"

        for other_stmts in statement_lists(ctx.tree):
            for other in other_stmts:
                for n in ast.walk(other):
                    if isinstance(n, ast.Name) and n.id == new and n.id != old:
                        return None

        class _Renamer(ast.NodeTransformer):
            changed = 0

            def visit_Name(self, n):
                if n.id == old:
                    self.changed += 1
                    return ast.copy_location(ast.Name(id=new, ctx=n.ctx), n)
                return n

        renamer = _Renamer()
        for stmts in statement_lists(ctx.tree):
            for i, s in enumerate(stmts):
                new_s = renamer.visit(s)
                stmts[i] = new_s
        ast.fix_missing_locations(ctx.tree)

        ctx.count("fixpoints_renamed")
        ctx.log("RENAME", f"renamed '{old}' -> '{new}' "
                f"({renamer.changed} refs)", rule=self.name)
        return None
