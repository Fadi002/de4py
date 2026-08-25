# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Structural CPS chain deflater.

Inverts the lambda-obfuscator statement encoding back into plain Python
without executing anything:

    stmt = lambda s, d: s(branch(sc, value), branch(FALSE, d))
    branch = lambda n: n(should_continue, value)
    chain = stmt1(TRUE, None)(stmt2)...(final_continuation)

Supported v1: expression statements, walrus assignments, early returns
(FALSE propagation truncates the tail). If / While / FIX-function hoisting
arrive in later phases; unsupported shapes make the whole chain return None
so callers fall back instead of emitting wrong code.
"""

import ast

from de4py.engines.onyx.transforms.cps_shapes import (
    _is_name_load,
    _lam_params,
    church_value,
    recognize_branch,
    recognize_fix,
    recognize_ret_none,
    recognize_stmt,
)


class DeflateError(Exception):
    pass


class Scope:
    """Param bindings along one spine (church values + data values)."""

    def __init__(self, parent=None):
        self.parent = parent
        self.church: dict = {}
        self.values: dict = {}

    def resolve_church(self, node):
        lit = church_value(node)
        if lit:
            return lit
        if isinstance(node, ast.Name):
            scope = self
            while scope is not None:
                if node.id in scope.church:
                    return scope.church[node.id]
                scope = scope.parent
        return None

    def resolve_value(self, node):
        if isinstance(node, ast.Name):
            scope = self
            while scope is not None:
                if node.id in scope.values:
                    return scope.values[node.id]
                scope = scope.parent
        return None

    def child(self):
        return Scope(self)


def flatten_spine(node):
    """Call(a)(b)...(z) -> (root_fn, flat_args) in application order."""
    groups = []
    fn = node
    while isinstance(fn, ast.Call):
        groups.append(list(fn.args))
        fn = fn.func
    groups.reverse()
    return fn, [a for g in groups for a in g]


def deflate_expression(expr):
    """Deflate one spine -> list[ast.stmt] | None."""
    try:
        return _deflate(expr)
    except (DeflateError, RecursionError):
        return None


def deflate_function_call(node):
    """Recognize FIX()(lambda fname: lambda params: CHAIN)(args...).

    Returns dict(fname, params, body_statements) or None. Recursive
    self-reference bails - Y-combinator support lands in a later phase.
    """
    if not (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Call)):
        return None
    fix_call = node.func

    def _is_fix(x):
        if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) \
                and x.func.id == "FIX" and not x.args:
            return True
        return isinstance(x, ast.Lambda) and recognize_fix(x)

    if not (_is_fix(fix_call.func) and len(fix_call.args) == 1):
        return None
    wrapped = fix_call.args[0]
    if not isinstance(wrapped, ast.Lambda):
        return None
    w_params = _lam_params(wrapped)
    if not w_params or len(w_params) != 1:
        return None
    fname = w_params[0]
    fn_lambda = wrapped.body
    if not isinstance(fn_lambda, ast.Lambda):
        return None
    fn_params = _lam_params(fn_lambda)
    if fn_params is None:
        return None
    chain = fn_lambda.body
    ret_none = False
    if isinstance(chain, ast.Call) and chain.args \
            and isinstance(chain.args[-1], ast.Lambda) \
            and recognize_ret_none(chain.args[-1]):
        ret_none = True
        chain = chain.func
    try:
        stmts = _deflate(chain)
    except (DeflateError, RecursionError):
        return None
    if stmts is None:
        return None
    for n in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(n, ast.Name) and n.id == fname:
            return None  # recursive self-reference - later phase
    return {"fname": fname, "params": fn_params, "body": stmts,
            "has_ret_none": ret_none}


def _deflate(expr):
    # Descend through pure wrapper applications ((lambda a: f(a))(real))
    # until the real statement-chain root appears.
    node = expr
    for _ in range(10_000):
        root, applied = flatten_spine(node)
        if recognize_stmt(root):
            break
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Lambda) \
                and len(node.args) == 1:
            node = node.args[0]
            continue
        return None
    else:
        return None
    info = recognize_stmt(root)
    _, s_name, d_name, bT, bF = info

    scope = Scope()
    if len(applied) >= 3 and church_value(applied[0]) in ('true', 'false'):
        # legacy protocol: (TRUE, initial_d)(cont)(cont)...
        church = scope.resolve_church(applied[0])
        if church != 'true':
            return None
        d_value = applied[1]
        conts = applied[2:]
    else:
        # current protocol: every application passes one continuation
        d_value = ast.Constant(value=None)
        conts = list(applied)

    out = []
    return _walk(bT, bF, d_value, conts, scope, out)


def _walk(bT, bF, d_value, rest, scope, out):
    while True:
        fail = recognize_branch(bF, scope)
        if fail is None:
            raise DeflateError("bad fail branch")
        _, f_sc, f_val = fail
        f_sel = scope.resolve_church(f_sc)
        if f_sel not in (None, "false"):
            raise DeflateError("unexpected fail flag")

        success = recognize_branch(bT, scope)
        if success is None:
            raise DeflateError("bad success branch")
        _, sc_node, value_node = success
        sc = scope.resolve_church(sc_node)
        if sc is None:
            raise DeflateError("unresolved continue flag")

        pair = _walrus_split(value_node)

        if not rest:
            _append(out, pair, value_node, scope)
            return out

        nxt = rest[0]
        rest = rest[1:]

        _append(out, pair, value_node, scope)

        nxt_info = recognize_stmt(nxt)
        if nxt_info is None:
            if recognize_ret_none(nxt):
                return out
            # terminal continuation (e.g. identity pair) - end of chain
            tail = church_value(nxt)
            if tail in ("true", "false"):
                return out
            pair_tail = _lam_params(nxt)
            if pair_tail and len(pair_tail) == 1 \
                    and isinstance(nxt.body, ast.Lambda):
                return out
            raise DeflateError("unknown continuation")
        _, ns, nd, nbT, nbF = nxt_info
        child = scope.child()
        child.church[ns] = sc
        if nd:
            child.values[nd] = value_node
        bT, bF = nbT, nbF
        d_value = value_node
        scope = child


def _walrus_split(node):
    if isinstance(node, ast.NamedExpr) and isinstance(node.target, ast.Name):
        return node.target.id, node.value
    return None


def _append(out, pair, value_node, scope):
    if pair:
        name, expr = pair
        assign = ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())],
                            value=expr)
        ast.copy_location(assign, value_node)
        out.append(assign)
    else:
        out.append(ast.Expr(value=value_node))
