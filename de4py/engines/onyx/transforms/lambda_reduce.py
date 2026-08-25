# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Beta-reduces ``(lambda p: BODY)(args)`` shells.

Keyword/starred/defaulted calls are never touched. An argument used more
than once must be pure, otherwise reduction would duplicate side effects.
Runs under a boosted recursion limit inside the caller's big-stack thread;
RecursionError leaves the match for a later pass instead of corrupting
output."""

import ast
import copy as _copy
import sys
import time

from de4py.engines.onyx.framework.governor import statement_lists
from de4py.engines.onyx.framework.rules import Match, Patch, Rule

_MAX_SHELLS_PER_PASS = 2000
_MAX_SUBSTITUTION_OPS = 25_000
_SMALL_LAMBDA_NODES = 25


class PeelBail(Exception):
    """Per-pass substitution budget exhausted; partial result is kept."""


def _is_pure(node: ast.AST) -> bool:
    from de4py.engines.onyx.constant_eval import _is_pure_expr
    # Small lambda DEFINITIONS (curried primitives like λa:λb:a+b, ~10
    # nodes) are safely duplicable and must count as pure - blocking them
    # freezes the primitive-binding shells of every CPS obfuscator. Big
    # continuation lambdas stay impure: duplicating them explodes.
    if isinstance(node, ast.Lambda):
        return _node_count(node, _SMALL_LAMBDA_NODES) <= _SMALL_LAMBDA_NODES
    return _is_pure_expr(node)


def _node_count(node: ast.AST, cap: int = 500_000) -> int:
    count = 0
    stack = [node]
    while stack:
        n = stack.pop()
        count += 1
        stack.extend(ast.iter_child_nodes(n))
        if count > cap:
            return count
    return count


class _Peel(ast.NodeTransformer):
    def __init__(self, budget: dict):
        self.reduced = 0
        self.budget = budget

    def visit_Call(self, node):
        try:
            self.generic_visit(node)
        except RecursionError:
            # Depth blew up in this branch - prune it (keep as-is) and let
            # shallower shells still reduce.
            return node
        fn = node.func
        if not isinstance(fn, ast.Lambda):
            return node
        bound = self._map_args(node, fn)
        if bound is None:
            return node
        params, arg_nodes = bound

        # multi-use parameters require pure arguments (reduction duplicates)
        usage: dict = {}
        for n in ast.walk(fn.body):
            if isinstance(n, ast.Name) and n.id in params \
                    and isinstance(n.ctx, ast.Load):
                usage[n.id] = usage.get(n.id, 0) + 1
        # Reduction duplicates args for multi-use params and deletes args
        # for unused params - both require argument purity. Only the exact
        # single-use case accepts arbitrary arguments.
        for param, arg in zip(params, arg_nodes):
            if usage.get(param, 0) != 1 and not _is_pure(arg):
                return node
        try:
            body = _copy.deepcopy(fn.body)
        except RecursionError:
            return node
        mapping = dict(zip(params, arg_nodes))

        class _Sub(ast.NodeTransformer):
            def __init__(self, budget):
                self.budget = budget

            def visit_Name(self, inner):
                if inner.id in mapping and isinstance(inner.ctx, ast.Load):
                    self.burn(mapping[inner.id])
                    return ast.copy_location(
                        _copy.deepcopy(mapping[inner.id]), inner)
                return inner

            def burn(self, source):
                self.budget["ops"] -= _node_count(source)
                if self.budget["ops"] <= 0:
                    raise PeelBail()

        new = _Sub(self.budget).visit(body)
        self.budget["ops"] -= 10
        self.reduced += 1
        return ast.copy_location(new, node)

    @staticmethod
    def _map_args(call: ast.Call, fn: ast.Lambda):
        spec = fn.args
        if call.keywords or any(isinstance(a, ast.Starred) for a in call.args):
            return None
        if spec.vararg or spec.kwarg or spec.kwonlyargs or spec.posonlyargs:
            return None
        params = [a.arg for a in spec.args]
        defaults = list(spec.defaults or [])
        if len(call.args) > len(params):
            return None
        if len(call.args) < len(params) - len(defaults):
            return None
        args = list(call.args)
        tail_defaults = defaults[len(params) - len(args):] if len(args) < len(params) else []
        args.extend(tail_defaults)
        return params, args


class LambdaIifeReduceRule(Rule):

    name = "lambda_iife_reduce"
    safety = "probably_safe"
    event_category = "LAMBDA"

    def applies(self, ctx):
        for stmts in statement_lists_safe(ctx.tree):
            for stmt in stmts:
                if not isinstance(stmt, (ast.Expr, ast.Assign)):
                    continue
                found = any(
                    isinstance(n, ast.Call) and isinstance(n.func, ast.Lambda)
                    for n in ast.walk(stmt)
                )
                if found:
                    yield Match(node=stmt)

    def transform(self, ctx, match):
        old_limit = sys.getrecursionlimit()
        start = time.monotonic()
        budget = {"ops": _MAX_SUBSTITUTION_OPS}
        try:
            sys.setrecursionlimit(min(old_limit + 250_000, 400_000))
            current_node = _copy.deepcopy(match.node)
            base_size = _node_count(current_node)
            # Beta-reduction can duplicate subtrees exponentially when a
            # multi-use parameter receives a large lambda argument. Bound
            # every pass by substitution ops, size growth and wall clock.
            max_size = max(600_000, base_size * 8)
            total = 0
            bailed = False
            for _ in range(_MAX_SHELLS_PER_PASS):
                peeler = _Peel(budget)
                try:
                    candidate = peeler.visit(current_node)
                except PeelBail:
                    # visit mutates current_node in place as it descends, so
                    # partial progress is already applied - keep it.
                    bailed = True
                    total += peeler.reduced
                    break
                if not peeler.reduced:
                    break
                size = _node_count(candidate)
                if size > max_size or time.monotonic() - start > 30.0:
                    break
                current_node = candidate
                total += peeler.reduced
        except RecursionError:
            ctx.log("LAMBDA", "tree too deep for full peel this pass",
                    rule=self.name, confidence=0.5)
            # fall through: partial progress below is still valid
        except PeelBail:
            pass
        finally:
            sys.setrecursionlimit(old_limit)
        if not total:
            return None
        ast.fix_missing_locations(current_node)
        ctx.count("lambdas_reduced", total)
        return Patch(target=match.node, replacement=current_node,
                     detail=f"beta-reduced {total} lambda shell(s)")


def statement_lists_safe(tree):
    return statement_lists(tree)


def default_lambda_rules():
    return [LambdaIifeReduceRule()]
