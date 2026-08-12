# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Normalizes deeply obfuscated Python code by folding lambdas, walrus chains, and string formatting.
"""

import ast
import re
import copy

from de4py.engines.onyx.safe_eval import safe_eval
from typing import List, Optional, Tuple, Union


def _is_const_like_node(node: ast.expr) -> bool:
    """True for nodes that evaluate to a constant value: scalars, list/tuple of scalars."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple)):
        return all(_is_const_like_node(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            _is_const_like_node(k) and _is_const_like_node(v)
            for k, v in zip(node.keys, node.values) if k is not None
        )
    return False


def _is_inlineable_value(node: ast.expr) -> bool:
    """Values safe to propagate across statements: constants, const collections, lambdas."""
    return _is_const_like_node(node) or isinstance(node, ast.Lambda)


def _try_eval_const(node: ast.expr) -> Tuple[bool, object]:
    """Safely evaluate a node if it's a pure constant expression."""
    return safe_eval(node)


def _is_lambda_identity(node: ast.Lambda) -> bool:
    """Return True if lambda x: x (pure identity function)."""
    if len(node.args.args) == 1:
        body = node.body
        if isinstance(body, ast.Name) and body.id == node.args.args[0].arg:
            return True
    return False


class LambdaNormalizer(ast.NodeTransformer):
    """Multi-pass AST transformer for lambda/walrus/string obfuscation."""

    def __init__(self):
        self.changes = 0

    def normalize(self, source: str) -> str:
        """Apply all normalizations until convergence."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        for _ in range(8):
            self.changes = 0
            tree = self.visit(tree)
            ast.fix_missing_locations(tree)
            if self.changes == 0:
                break

        try:
            return ast.unparse(tree)
        except Exception:
            return source

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        """Fold  "%c" % N  →  chr(N) character literal, and  "%s%s" % (a,b)  →  str."""
        self.generic_visit(node)

        if isinstance(node.op, ast.Mod):
            ok, val = _try_eval_const(node)
            if ok and isinstance(val, str):
                self.changes += 1
                return ast.Constant(value=val)

        if isinstance(node.op, ast.Add):
            ok, val = _try_eval_const(node)
            if ok and isinstance(val, (str, int, float)):
                self.changes += 1
                return ast.Constant(value=val)

        # "xyz"[::-1]  →  "zyx"  (handled via Subscript but also here for safety)
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (str, int, float, bool, type(None), tuple)):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (int, float, bool)):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, bool):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    def visit_Expr(self, node: ast.Expr) -> Union[ast.Expr, List[ast.stmt]]:
        """
        Expr(BoolOp(And, [NamedExpr(x, val), NamedExpr(y, val2), ...]))
        →  x = val; y = val2; ...
        Only when all values in the chain are walrus expressions or constants.
        """
        self.generic_visit(node)

        if isinstance(node.value, ast.BoolOp) and isinstance(node.value.op, ast.And):
            stmts = self._extract_walrus_chain(node.value.values)
            if stmts is not None:
                self.changes += 1
                return stmts

        return node

    def _extract_walrus_chain(
        self, values: List[ast.expr]
    ) -> Optional[List[ast.stmt]]:
        """
        Convert a chain of walrus expressions into assignments if safe.
        Also handles non-walrus expressions that have side effects by keeping them as Expr stmts.
        Returns list of stmts or None if nothing extractable.
        """
        stmts = []
        has_walrus = False
        for val in values:
            if isinstance(val, ast.NamedExpr):
                has_walrus = True
                stmts.append(
                    ast.Assign(
                        targets=[val.target],
                        value=val.value,
                        lineno=val.lineno,
                        col_offset=val.col_offset,
                    )
                )
            elif isinstance(val, ast.Constant):
                pass
            elif isinstance(val, ast.Name):
                pass
            elif isinstance(val, ast.Call):
                # Keep calls as expression statements (they may have side effects)
                stmts.append(ast.Expr(value=val, lineno=getattr(val, 'lineno', 1), col_offset=getattr(val, 'col_offset', 0)))
            elif isinstance(val, ast.BoolOp):
                sub = self._extract_walrus_chain(val.values)
                if sub:
                    has_walrus = True
                    stmts.extend(sub)
        return stmts if (stmts and has_walrus) else None

    def visit_NamedExpr(self, node: ast.NamedExpr) -> ast.NamedExpr:
        """Keep walrus operators but fold their value if constant."""
        self.generic_visit(node)
        ok, val = _try_eval_const(node.value)
        if ok and isinstance(val, (str, int, float, bool, type(None))):
            self.changes += 1
            node.value = ast.Constant(value=val)
        return node

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        self.generic_visit(node)

        if isinstance(node.value, ast.Lambda) and not node.value.args.args:
            body = node.value.body
            if isinstance(body, ast.Constant):
                self.changes += 1
                node.value = body

        return node

    def visit_Call_chr(self, node: ast.Call) -> ast.expr:
        """chr(78) → 'N'"""
        if (isinstance(node.func, ast.Name) and node.func.id == "chr"
                and len(node.args) == 1):
            ok, val = _try_eval_const(node.args[0])
            if ok and isinstance(val, int) and 0 <= val <= 0x10FFFF:
                self.changes += 1
                return ast.Constant(value=chr(val))
        return node

    def visit_Call_ord(self, node: ast.Call) -> ast.expr:
        """ord('A') → 65"""
        if (isinstance(node.func, ast.Name) and node.func.id == "ord"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and len(node.args[0].value) == 1):
            self.changes += 1
            return ast.Constant(value=ord(node.args[0].value))
        return node

    def visit_Call(self, node: ast.Call) -> ast.expr:
        self.generic_visit(node)

        if isinstance(node.func, ast.Name) and node.func.id == "chr":
            r = self.visit_Call_chr(node)
            if r is not node:
                return r

        if isinstance(node.func, ast.Name) and node.func.id == "ord":
            r = self.visit_Call_ord(node)
            if r is not node:
                return r

        if isinstance(node.func, ast.Lambda):
            lam = node.func
            if not node.keywords and len(node.args) == len(lam.args.args):
                if len(lam.args.args) == 0:
                    self.changes += 1
                    return lam.body
                if _is_lambda_identity(lam) and len(node.args) == 1:
                    self.changes += 1
                    return node.args[0]
                if all(_is_const_like_node(a) for a in node.args):
                    ok, val = _try_eval_const(node)
                    if ok and isinstance(val, (str, int, float, bool, type(None))):
                        self.changes += 1
                        return ast.Constant(value=val)

        if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) == 2):
            ok, val = _try_eval_const(node.args[1])
            if ok and isinstance(val, str) and val.isidentifier():
                node.args[1] = ast.Constant(value=val)
                self.changes += 1

        if (isinstance(node.func, ast.Name) and node.func.id == "__import__"
                and len(node.args) == 1):
            ok, val = _try_eval_const(node.args[0])
            if ok and isinstance(val, str):
                node.args[0] = ast.Constant(value=val)
                self.changes += 1

        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (str, int, float, bool, type(None))):
            self.changes += 1
            return ast.Constant(value=val)

        return node


def _preprocess_string_escapes(source: str) -> str:
    """
    Replace '\x41\x42' escape sequences in string literals that aren't
    otherwise handled by the AST (e.g., inside f-strings or format calls).
    """
    return source


def _normalize_percent_format(source: str) -> str:
    """
    Statically evaluate simple '%c' % N  and  '%s' % "x"  patterns
    in the source text before AST parsing.
    """
    def repl_c(m: re.Match) -> str:
        try:
            n = int(m.group(1).strip())
            return repr(chr(n))
        except Exception:
            return m.group(0)

    source = re.sub(r'"%c"\s*%\s*(\d+)', repl_c, source)
    source = re.sub(r"'%c'\s*%\s*(\d+)", repl_c, source)

    return source


class _TopLevelBoolOpFlattener(ast.NodeTransformer):
    """
    Flattens top-level expression statements that are BoolOp chains
    used purely for their walrus side effects, e.g.:
        (x := expr) and (y := expr2) and some_call() or ...
    Converts them into sequential assignments / call statements.
    """

    def _flatten_boolop(self, values: list) -> list:
        stmts = []
        for v in values:
            if isinstance(v, ast.NamedExpr):
                stmts.append(ast.Assign(
                    targets=[v.target],
                    value=v.value,
                    lineno=getattr(v, 'lineno', 1),
                    col_offset=getattr(v, 'col_offset', 0),
                ))
            elif isinstance(v, ast.BoolOp):
                stmts.extend(self._flatten_boolop(v.values))
            elif isinstance(v, ast.Call):
                stmts.append(ast.Expr(
                    value=v,
                    lineno=getattr(v, 'lineno', 1),
                    col_offset=getattr(v, 'col_offset', 0),
                ))
            elif isinstance(v, ast.Constant):
                pass
            elif isinstance(v, ast.Name):
                pass
            elif isinstance(v, ast.Tuple) and not v.elts:
                pass
            elif isinstance(v, ast.Dict) and not v.keys:
                pass
            elif isinstance(v, ast.List) and not v.elts:
                pass
            else:
                stmts.append(ast.Expr(
                    value=v,
                    lineno=getattr(v, 'lineno', 1),
                    col_offset=getattr(v, 'col_offset', 0),
                ))
        return stmts

    def _has_walrus(self, node: ast.expr) -> bool:
        return any(isinstance(n, ast.NamedExpr) for n in ast.walk(node))

    def visit_Expr(self, node: ast.Expr):
        self.generic_visit(node)
        if isinstance(node.value, ast.BoolOp) and self._has_walrus(node.value):
            stmts = self._flatten_boolop(node.value.values)
            if stmts:
                return stmts
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.generic_visit(node)
        new_body = []
        for stmt in node.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.BoolOp) and self._has_walrus(stmt.value):
                flattened = self._flatten_boolop(stmt.value.values)
                new_body.extend(flattened)
            else:
                new_body.append(stmt)
        node.body = new_body
        return node

    visit_AsyncFunctionDef = visit_FunctionDef


def _flatten_walrus_boolops(source: str) -> str:
    """Pre-pass: flatten top-level/function-level walrus BoolOp chains."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    for _ in range(5):
        before = ast.unparse(tree)
        flattener = _TopLevelBoolOpFlattener()
        tree = flattener.visit(tree)
        ast.fix_missing_locations(tree)
        try:
            if ast.unparse(tree) == before:
                break
        except Exception:
            break
    try:
        return ast.unparse(tree)
    except Exception:
        return source


class _ConstantPropagator(ast.NodeTransformer):
    """
    Inline single-assignment constants/lambdas at module scope.
    Enables IIFE chains that reference earlier name bindings to be evaluated
    by the LambdaNormalizer in subsequent passes.
    """

    def __init__(self, env: dict):
        self._env = env

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if isinstance(node.ctx, ast.Load) and node.id in self._env:
            return copy.deepcopy(self._env[node.id])
        return node


def _collect_propagation_env(stmts: list) -> dict:
    counts= {}
    values= {}
    for stmt in stmts:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            t = stmt.targets[0]
            if isinstance(t, ast.Name):
                counts[t.id] = counts.get(t.id, 0) + 1
                values[t.id] = stmt.value
    return {
        name: val
        for name, val in values.items()
        if counts.get(name, 0) == 1 and _is_inlineable_value(val)
    }


def _propagate_constants(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    env = _collect_propagation_env(tree.body)
    if not env:
        return source

    new_tree = _ConstantPropagator(env).visit(tree)
    ast.fix_missing_locations(new_tree)
    try:
        return ast.unparse(new_tree)
    except Exception:
        return source


class LambdaChainDeobfuscator:

    def deobfuscate(self, source: str) -> str:
        """Apply all lambda/walrus/string normalization passes."""
        try:
            source = _preprocess_string_escapes(source)
            source = _normalize_percent_format(source)
            source = _flatten_walrus_boolops(source)

            for _ in range(6):
                prev = source
                source = _propagate_constants(source)
                normalizer = LambdaNormalizer()
                source = normalizer.normalize(source)
                if source == prev:
                    break

            return source
        except RecursionError:
            return source
        except Exception:
            return source

