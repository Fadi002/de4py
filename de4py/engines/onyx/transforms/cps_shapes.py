# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Shape recognizers for the lambda-obfuscator CPS protocol.
"""

import ast


def _lam_params(node):
    """Flat positional params of a Lambda, or None."""
    if not isinstance(node, ast.Lambda):
        return None
    spec = node.args
    if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs \
            or spec.defaults:
        return None
    return [a.arg for a in spec.args]


def _is_name_load(node, name):
    return isinstance(node, ast.Name) and node.id == name \
        and isinstance(node.ctx, ast.Load)


def _is_nested_identity_pair(node):
    """True for ``lambda x: lambda y: x`` (TRUE) / ``(y)`` (FALSE).

    Also matches single-expression ``lambda x, y: x`` spellings produced by
    some astor round-trips.
    """
    params = _lam_params(node)
    if params is None:
        return None
    body = node.body

    if len(params) == 2 and isinstance(body, ast.Name) and \
            isinstance(body.ctx, ast.Load) and body.id == params[0]:
        return "true"
    if len(params) == 2 and isinstance(body, ast.Name) and \
            isinstance(body.ctx, ast.Load) and body.id == params[1]:
        return "false"

    if len(params) == 1 and isinstance(body, ast.Lambda):
        inner_params = _lam_params(body)
        if inner_params and len(inner_params) == 1 and \
                isinstance(body.body, ast.Name) and \
                isinstance(body.body.ctx, ast.Load):
            if body.body.id == params[0]:
                return "true"
            if body.body.id == inner_params[0]:
                return "false"
    return None


def church_value(node) -> str | None:
    """'true' | 'false' | None - recognizes TRUE/FALSE literals."""
    return _is_nested_identity_pair(node)


class _Scope:
    """Tracks param -> church-value along the current spine."""

    def __init__(self, parent=None):
        self.parent = parent
        self.map: dict = {}

    def resolve(self, name):
        scope = self
        while scope is not None:
            if name in scope.map:
                return scope.map[name]
            scope = scope.parent
        return None

    def child(self):
        return _Scope(self)


def recognize_branch(node, scope):
    """branch = lambda n: n(sc, v) -> ('branch', sc_node, value_node)."""
    params = _lam_params(node)
    if not params or len(params) != 1:
        return None
    n = params[0]
    body = node.body
    if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Name)
            and body.func.id == n and len(body.args) == 2
            and not body.keywords):
        return None
    return "branch", body.args[0], body.args[1]


def recognize_stmt(node, scope=None):
    """stmt = lambda s, d: s(bT, bF) -> ('stmt', s_name, bT, bF)."""
    params = _lam_params(node)
    if not params or len(params) != 2:
        return None
    s_name, d_name = params
    body = node.body
    if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Name)
            and body.func.id == s_name and len(body.args) == 2
            and not body.keywords):
        return None
    return "stmt", s_name, d_name, body.args[0], body.args[1]


def recognize_ret_none(node):
    """RET_NONE = lambda cond, k: cond(None, k)."""
    params = _lam_params(node)
    if not params or len(params) != 2:
        return None
    cond, k = params
    body = node.body
    if not (isinstance(body, ast.Call) and isinstance(body.func, ast.Name)
            and body.func.id == cond and len(body.args) == 2
            and not body.keywords):
        return None
    first, second = body.args
    if _const_is(first, None) and _is_name_load(second, k):
        return True
    return False


def _const_is(node, value):
    return isinstance(node, ast.Constant) and node.value is value \
        if value is None else (isinstance(node, ast.Constant)
                               and node.value == value)


def recognize_fix(node):
    """FIX = lambda f: (lambda x: f(lambda *y: x(x)(*y)))(lambda x: ...)."""
    params = _lam_params(node)
    if not params or len(params) != 1:
        return None
    f = params[0]
    body = node.body
    if not (isinstance(body, ast.Call) and len(body.args) == 1):
        return None
    inner_call_func = body.func
    if not isinstance(inner_call_func, ast.Lambda):
        return None
    inner_params = _lam_params(inner_call_func)
    if not inner_params or len(inner_params) != 1:
        return None
    x = inner_params[0]
    inner_arg = body.args[0]
    if not isinstance(inner_arg, ast.Lambda):
        return None
    arg_params = _lam_params(inner_arg)
    if not arg_params or arg_params != [x]:
        return None
    star_body = inner_arg.body
    # expect f(lambda *y: x(x)(*y))
    if not (isinstance(star_body, ast.Call)
            and isinstance(star_body.func, ast.Name)
            and star_body.func.id == f and len(star_body.args) == 1
            and isinstance(star_body.args[0], ast.Lambda)):
        return None
    return True
