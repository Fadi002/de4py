# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Unbinder for gio54321/lambdifier output (MIT).

Inverts the let-binding shells ``(lambda f: f(expr))(lambda x: BODY)``
into ``x = expr`` plus BODY, iteratively and order-preserving.
Ported from transformers/unbind.py of the reference tool."""

import ast
import copy as _copy
import sys


def _is_bind_shell(value):
    """Expr-value shape (lambda f: f(expr))(lambda x: BODY) -> components."""
    if not isinstance(value, ast.Call):
        return None
    fn = value.func
    if not isinstance(fn, ast.Lambda):
        return None
    fargs = fn.args.args
    if len(fargs) != 1 or not isinstance(fn.body, ast.Call):
        return None
    fname = fargs[0].arg
    inner = fn.body
    if not (isinstance(inner.func, ast.Name) and inner.func.id == fname
            and len(inner.args) == 1):
        return None
    outer_arg = value.args[0] if value.args else None
    if not (isinstance(outer_arg, ast.Lambda) and outer_arg.args.args):
        return None
    bind_name = outer_arg.args.args[0].arg
    expr = inner.args[0]
    return bind_name, expr, outer_arg.body


def unbind_module(tree: ast.Module, max_ops: int = 500_000):
    """Unwrap binding shells across module top-level expressions.

    Returns (bound_count, emitted_statements). The input tree is NOT
    modified; callers rebuild module bodies from the emitted statements.
    """
    bound = 0
    ops = max_ops
    out: list = []

    def burn(cost):
        nonlocal ops
        ops -= cost
        if ops <= 0:
            raise _Bail()

    class _Bail(Exception):
        pass

    for stmt in tree.body:
        if isinstance(stmt, ast.Expr):
            value = stmt.value
            try:
                while True:
                    shell = _is_bind_shell(value)
                    if shell is None:
                        break
                    bind_name, expr, rest = shell
                    cost = min(2000, _rough_size(expr))
                    burn(cost)
                    out.append(ast.Assign(
                        targets=[ast.Name(id=bind_name, ctx=ast.Store())],
                        value=expr))
                    ast.copy_location(out[-1], stmt)
                    bound += 1
                    value = rest
            except _Bail:
                pass
            if bound and ops < max_ops:
                pass
            residual = ast.Expr(value=value)
            ast.copy_location(residual, stmt)
            out.append(residual)
        else:
            out.append(stmt)

    return bound, out


def _rough_size(node):
    count = 0
    stack = [node]
    while stack:
        n = stack.pop()
        count += 1
        stack.extend(ast.iter_child_nodes(n))
        if count > 2000:
            break
    return count


def unbind_tree(tree: ast.Module):
    """Convenience wrapper: returns (new_tree, bound_count).

    Runs under a boosted recursion limit because the RESULTING tree may
    still be deeply nested for downstream unparsers.
    """
    old = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(max(old, 400_000))
        work = ast.parse(ast.unparse(ast.fix_missing_locations(
            _copy.deepcopy(tree))))
        bound, body = unbind_module(work)
        work.body = body
        ast.fix_missing_locations(work)
        return work, bound
    finally:
        sys.setrecursionlimit(old)
