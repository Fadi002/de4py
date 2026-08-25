# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import copy as _copy

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule
from de4py.engines.onyx.transforms.cps_deflate import (
    deflate_expression,
    deflate_function_call,
    flatten_spine,
)
from de4py.engines.onyx.transforms.cps_shapes import recognize_stmt, church_value
from de4py.engines.onyx.transforms.cps_unbind import _is_bind_shell


def _find_cps_site(node):
    stack = [node]
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Call):
            info = deflate_function_call(n)
            if info is not None:
                return n, info
        stack.extend(ast.iter_child_nodes(n))
    return None, None


class CpsFunctionDeflateRule(Rule):

    name = "cps_function_deflate"
    safety = "probably_safe"
    event_category = "CPS-DEFLATE"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if not isinstance(stmt, (ast.Expr, ast.Assign)):
                    continue
                site, info = _find_cps_site(stmt)
                if site is not None:
                    yield Match(node=stmt,
                                data={"site": site, "info": info})
                    continue
                if isinstance(stmt, ast.Expr):
                    root, flat = flatten_spine(stmt.value)
                    info2 = recognize_stmt(root)
                    if info2 and len(flat) >= 2 \
                            and church_value(flat[0]) == "true":
                        yield Match(node=stmt, data={"chain": True})

    def transform(self, ctx, match):
        if match.data.get("chain"):
            stmts = deflate_expression(match.node.value)
            if not stmts:
                return None
            ctx.count("cps_chains_deflated")
            return Patch(target=match.node, replacement=stmts,
                         detail=f"deflated CPS chain ({len(stmts)} stmts)")

        site = match.data["site"]
        info = match.data["info"]

        fn_def = ast.FunctionDef(
            name=info["fname"],
            args=ast.arguments(
                args=[ast.arg(arg=p) for p in info["params"]],
                posonlyargs=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=info["body"],
            decorator_list=[])
        ast.fix_missing_locations(fn_def)

        class _Swap(ast.NodeTransformer):
            def visit_Call(self, inner):
                if inner is site:
                    return ast.copy_location(
                        ast.Name(id=info["fname"], ctx=ast.Load()), inner)
                self.generic_visit(inner)
                return inner

        stmt = match.node
        swapped = _Swap().visit(_copy.deepcopy(stmt))
        if isinstance(swapped, ast.Expr):
            new_call_stmt = ast.Expr(value=swapped.value)
        else:
            new_call_stmt = swapped
        ast.copy_location(new_call_stmt, stmt)
        ast.fix_missing_locations(new_call_stmt)
        ctx.count("cps_functions_deflated")
        return Patch(target=stmt,
                     replacement=[fn_def, new_call_stmt],
                     detail=f"deflated CPS function '{info['fname']}'")


class CpsUnbindRule(Rule):

    name = "cps_unbind"
    safety = "probably_safe"
    event_category = "CPS-DEFLATE"

    def applies(self, ctx):
        for stmt in ctx.tree.body:
            if isinstance(stmt, ast.Expr) and _is_bind_shell(stmt.value):
                yield Match(node=stmt)
                return

    def transform(self, ctx, match):
        from de4py.engines.onyx.transforms.cps_unbind import unbind_tree

        new_tree, bound = unbind_tree(ctx.tree)
        if not bound:
            return None
        ctx.tree.body = new_tree.body
        ctx.count("cps_bindings_removed", bound)
        return Patch(target=match.node,
                     replacement=match.node,
                     detail=f"unbound {bound} lambda bindings")
