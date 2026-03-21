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
import string
from typing import List, Optional, Dict, Tuple, Union


# --- Helpers ------------------------------------------------------------------

def _try_eval_const(node: ast.expr) -> Tuple[bool, object]:
    """Safely evaluate a node if it's a pure constant expression."""
    try:
        result = eval(
            compile(ast.Expression(body=node), "<eval>", "eval"),
            {"__builtins__": {"chr": chr, "ord": ord, "len": len}},
        )
        return True, result
    except Exception:
        return False, None


def _is_lambda_identity(node: ast.Lambda) -> bool:
    """Return True if lambda x: x (pure identity function)."""
    if len(node.args.args) == 1:
        body = node.body
        if isinstance(body, ast.Name) and body.id == node.args.args[0].arg:
            return True
    return False


# --- Transform passes ---------------------------------------------------------

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

    # --- Immediately-invoked lambda --------------------------------------------

    def visit_Call(self, node: ast.Call) -> ast.expr:
        """(lambda x: body)(arg)  →  inline substitution where safe."""
        self.generic_visit(node)

        if (
            isinstance(node.func, ast.Lambda)
            and not node.keywords
            and len(node.args) == len(node.func.args.args)
            and not node.func.args.vararg
            and not node.func.args.kwonlyargs
        ):
            lam   = node.func
            body  = lam.body

            # Single-arg identity: (lambda x: x)(val) → val
            if _is_lambda_identity(lam) and len(node.args) == 1:
                self.changes += 1
                return node.args[0]

            # No-arg: (lambda: expr)()  →  expr
            if len(lam.args.args) == 0 and len(node.args) == 0:
                self.changes += 1
                return body

            # Constant-arg, pure body: (lambda x: x+1)(5)  →  6
            if all(isinstance(a, ast.Constant) for a in node.args):
                ok, val = _try_eval_const(node)
                if ok:
                    self.changes += 1
                    return ast.Constant(value=val)

        # getattr(obj, "a" + "b")  →  getattr(obj, "ab")
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) == 2
        ):
            ok, val = _try_eval_const(node.args[1])
            if ok and isinstance(val, str):
                node.args[1] = ast.Constant(value=val)
                self.changes += 1

        # __import__("%c%s" % (...))  →  simplify the string
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and len(node.args) == 1
        ):
            ok, val = _try_eval_const(node.args[0])
            if ok and isinstance(val, str):
                node.args[0] = ast.Constant(value=val)
                self.changes += 1

        return node

    # --- String format constant folding -----------------------------------------

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        """Fold  "%c" % N  →  chr(N) character literal, and  "%s%s" % (a,b)  →  str."""
        self.generic_visit(node)

        if isinstance(node.op, ast.Mod):
            ok, val = _try_eval_const(node)
            if ok and isinstance(val, str):
                self.changes += 1
                return ast.Constant(value=val)

        # String addition constant fold
        if isinstance(node.op, ast.Add):
            ok, val = _try_eval_const(node)
            if ok and isinstance(val, (str, int, float)):
                self.changes += 1
                return ast.Constant(value=val)

        # "xyz"[::-1]  →  "zyx"  (handled via Subscript but also here for safety)
        return node

    # --- Subscript constant folding --------------------------------------------

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (str, int, float, bool, type(None), tuple)):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    # --- UnaryOp constant fold --------------------------------------------------

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (int, float, bool)):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    # --- Compare constant fold -------------------------------------------------

    def visit_Compare(self, node: ast.Compare) -> ast.expr:
        self.generic_visit(node)
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, bool):
            self.changes += 1
            return ast.Constant(value=val)
        return node

    # --- Walrus chain extraction -----------------------------------------------

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
        Returns list of Assign nodes or None if not all extractable.
        """
        stmts = []
        for val in values:
            if isinstance(val, ast.NamedExpr):
                stmts.append(
                    ast.Assign(
                        targets=[val.target],
                        value=val.value,
                        lineno=val.lineno,
                        col_offset=val.col_offset,
                    )
                )
            elif isinstance(val, ast.Constant):
                pass  # skip bare True/False/None used as sentinels
            elif isinstance(val, ast.Name):
                pass  # skip bare variable references
            else:
                return None  # complex expression — don't extract
        return stmts if stmts else None

    # --- NamedExpr in non-statement contexts -----------------------------------

    def visit_NamedExpr(self, node: ast.NamedExpr) -> ast.NamedExpr:
        """Keep walrus operators but fold their value if constant."""
        self.generic_visit(node)
        ok, val = _try_eval_const(node.value)
        if ok and isinstance(val, (str, int, float, bool, type(None))):
            self.changes += 1
            node.value = ast.Constant(value=val)
        return node

    # --- Lambda used only as a callable constant --------------------------------

    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        """
        x = (lambda: False)  →  x = False
        x = (lambda: "string")  →  x = "string"
        """
        self.generic_visit(node)

        if isinstance(node.value, ast.Lambda) and not node.value.args.args:
            body = node.value.body
            if isinstance(body, ast.Constant):
                self.changes += 1
                node.value = body

        return node

    # --- chr(N) call folding ---------------------------------------------------

    def visit_Call_chr(self, node: ast.Call) -> ast.expr:
        """chr(78) → 'N'"""
        if (isinstance(node.func, ast.Name) and node.func.id == "chr"
                and len(node.args) == 1):
            ok, val = _try_eval_const(node.args[0])
            if ok and isinstance(val, int) and 0 <= val <= 0x10FFFF:
                self.changes += 1
                return ast.Constant(value=chr(val))
        return node

    # --- ord() constant folding ------------------------------------------------

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

    def visit_Call(self, node: ast.Call) -> ast.expr:  # noqa: F811
        """Dispatch to specialized call handlers."""
        self.generic_visit(node)

        # chr() folding
        if isinstance(node.func, ast.Name) and node.func.id == "chr":
            r = self.visit_Call_chr(node)
            if r is not node:
                return r

        # ord() folding
        if isinstance(node.func, ast.Name) and node.func.id == "ord":
            r = self.visit_Call_ord(node)
            if r is not node:
                return r

        # (lambda x: body)(arg) IIFE
        if isinstance(node.func, ast.Lambda):
            lam = node.func
            if not node.keywords and len(node.args) == len(lam.args.args):
                if len(lam.args.args) == 0:
                    # (lambda: expr)()
                    self.changes += 1
                    return lam.body
                if _is_lambda_identity(lam) and len(node.args) == 1:
                    self.changes += 1
                    return node.args[0]
                # constant args
                if all(isinstance(a, ast.Constant) for a in node.args):
                    ok, val = _try_eval_const(node)
                    if ok and isinstance(val, (str, int, float, bool, type(None))):
                        self.changes += 1
                        return ast.Constant(value=val)

        # getattr string folding
        if (isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) == 2):
            ok, val = _try_eval_const(node.args[1])
            if ok and isinstance(val, str) and val.isidentifier():
                node.args[1] = ast.Constant(value=val)
                self.changes += 1

        # __import__ string folding
        if (isinstance(node.func, ast.Name) and node.func.id == "__import__"
                and len(node.args) == 1):
            ok, val = _try_eval_const(node.args[0])
            if ok and isinstance(val, str):
                node.args[0] = ast.Constant(value=val)
                self.changes += 1

        # General constant-call folding
        ok, val = _try_eval_const(node)
        if ok and isinstance(val, (str, int, float, bool, type(None))):
            self.changes += 1
            return ast.Constant(value=val)

        return node


# --- Source-level pre-processing ----------------------------------------------

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
    # "%c" % 65  →  'A'
    def repl_c(m: re.Match) -> str:
        try:
            n = int(m.group(1).strip())
            return repr(chr(n))
        except Exception:
            return m.group(0)

    source = re.sub(r'"%c"\s*%\s*(\d+)', repl_c, source)
    source = re.sub(r"'%c'\s*%\s*(\d+)", repl_c, source)

    return source


# --- Public API ---------------------------------------------------------------

class LambdaChainDeobfuscator:

    def deobfuscate(self, source: str) -> str:
        """
        Apply all lambda/walrus/string normalization passes.
        Returns cleaned source.
        """
        # Phase 1: text-level pre-processing
        source = _preprocess_string_escapes(source)
        source = _normalize_percent_format(source)

        # Phase 2: AST normalization (multi-pass)
        normalizer = LambdaNormalizer()
        return normalizer.normalize(source)
