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


def _is_zero(node):
    return isinstance(node, ast.Constant) and node.value == 0 \
        and not isinstance(node.value, bool)


def _is_one(node):
    return isinstance(node, ast.Constant) and node.value == 1 \
        and not isinstance(node.value, bool)


def _is_neg_one(node):
    return isinstance(node, ast.Constant) and node.value == -1


class _IdentityFolder(ast.NodeTransformer):

    folded = 0

    def visit_BinOp(self, node):
        self.generic_visit(node)
        op = type(node.op)

        if op is ast.Add or op is ast.BitOr or op is ast.BitXor:
            if _is_zero(node.left):
                self.folded += 1
                return node.right
            if _is_zero(node.right):
                self.folded += 1
                return node.left
        elif op is ast.Sub:
            if _is_zero(node.right):
                self.folded += 1
                return node.left
        elif op is ast.Mult:
            if _is_one(node.right):
                self.folded += 1
                return node.left
            if _is_one(node.left):
                self.folded += 1
                return node.right
        elif op is ast.Div or op is ast.FloorDiv:
            if _is_one(node.right):
                self.folded += 1
                return node.left
        elif op is ast.BitAnd:
            if _is_neg_one(node.right):
                self.folded += 1
                return node.left
            if _is_neg_one(node.left):
                self.folded += 1
                return node.right

        return node


class IdentityOpRule(Rule):

    name = "identity_ops"
    safety = "safe"
    event_category = "FOLD"

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                for n in ast.walk(stmt):
                    if isinstance(n, ast.BinOp) \
                            and isinstance(n.op, (
                                ast.Add, ast.Sub, ast.Mult,
                                ast.BitOr, ast.BitXor, ast.BitAnd,
                                ast.Div, ast.FloorDiv)):
                        has_const_operand = (
                            _is_zero(n.left) or _is_zero(n.right)
                            or _is_one(n.left) or _is_one(n.right)
                            or _is_neg_one(n.left) or _is_neg_one(n.right))
                        if has_const_operand:
                            yield Match(node=stmt)
                            break

    def transform(self, ctx, match):
        folder = _IdentityFolder()
        new = folder.visit(_copy.deepcopy(match.node))
        if not folder.folded:
            return None
        ast.fix_missing_locations(new)
        ctx.count("identity_ops_folded", folder.folded)
        return Patch(target=match.node, replacement=new,
                     detail=f"folded {folder.folded} identity op(s)")


class TautologyCompareRule(Rule):

    name = "tautology_compare"
    safety = "probably_safe"
    event_category = "FLOW"

    @staticmethod
    def _is_square_nonneg(test):
        return (isinstance(test, ast.Compare) and len(test.ops) == 1
                and isinstance(test.ops[0], (ast.GtE,))
                and isinstance(test.left, ast.BinOp)
                and isinstance(test.left.op, ast.Mult)
                and ast.dump(test.left.left) == ast.dump(test.left.right))

    @staticmethod
    def _is_abs_nonneg(test):
        return (isinstance(test, ast.Compare) and len(test.ops) == 1
                and isinstance(test.ops[0], (ast.GtE,))
                and isinstance(test.left, ast.Call)
                and isinstance(test.left.func, ast.Name)
                and test.left.func.id == "abs")

    def applies(self, ctx):
        for stmts in statement_lists(ctx.tree):
            for stmt in stmts:
                if not isinstance(stmt, ast.If):
                    continue
                if self._is_square_nonneg(stmt.test) \
                        or self._is_abs_nonneg(stmt.test):
                    yield Match(node=stmt)

    def transform(self, ctx, match):
        body_stmts = list(match.node.body)
        ctx.count("opaque_predicates_resolved")
        return Patch(target=match.node, replacement=body_stmts,
                     detail="resolved tautological predicate")


def default_identity_rules():
    return [IdentityOpRule(), TautologyCompareRule()]
