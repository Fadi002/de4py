# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import re
from typing import List, Union, Optional


# --- Main cleaner -------------------------------------------------------------

class ASTCleaner(ast.NodeTransformer):

    def __init__(self):
        self.changes_made = 0

    def clean(self, source: str) -> str:
        """
        Parse source, apply all transforms, unparse back to source string.
        Returns original source unchanged if parsing fails.
        Runs up to 5 passes to handle cascading simplifications.
        """
        self.changes_made = 0
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        # Multi-pass: some folds enable further folds (e.g., if True: if True: x)
        for _ in range(5):
            prev_changes = self.changes_made
            tree = self.visit(tree)
            ast.fix_missing_locations(tree)
            if self.changes_made == prev_changes:
                break  # Converged

        try:
            return ast.unparse(tree)
        except Exception:
            return source

    # --- Constant folding ------------------------------------------------------

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        """Evaluate constant arithmetic/string ops at compile time, including string*N"""
        self.generic_visit(node)

        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            try:
                safe_ops = (
                    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                    ast.Mod, ast.Pow, ast.BitXor, ast.BitAnd, ast.BitOr,
                    ast.LShift, ast.RShift,
                )
                if isinstance(node.op, safe_ops):
                    # Extra guard: don't fold huge string reps (e.g. 'x' * 1_000_000)
                    if isinstance(node.op, ast.Mult):
                        a, b = node.left.value, node.right.value
                        if isinstance(a, str) and isinstance(b, int) and len(a) * b > 4096:
                            return node
                        if isinstance(b, str) and isinstance(a, int) and len(b) * a > 4096:
                            return node
                    result = eval(
                        compile(ast.Expression(body=node), '<fold>', 'eval'),
                        {"__builtins__": {}},
                    )
                    self.changes_made += 1
                    return ast.Constant(value=result)
            except Exception:
                pass
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        """
        Fold unary ops on constants.
        Also eliminate double negation: not not x → x (when in boolean context).
        """
        self.generic_visit(node)

        # not (not x) → x  (eliminates obfuscator trick)
        if (
            isinstance(node.op, ast.Not)
            and isinstance(node.operand, ast.UnaryOp)
            and isinstance(node.operand.op, ast.Not)
        ):
            self.changes_made += 1
            return node.operand.operand

        if isinstance(node.operand, ast.Constant):
            try:
                result = eval(
                    compile(ast.Expression(body=node), '<fold>', 'eval'),
                    {"__builtins__": {}},
                )
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.expr:
        """Evaluate constant comparisons: 1 == 1 → True, 5 > 10 → False.
        Also catches opaque predicates like len('') == 0 → True."""
        self.generic_visit(node)

        if isinstance(node.left, ast.Constant) and all(
            isinstance(c, ast.Constant) for c in node.comparators
        ):
            try:
                result = eval(
                    compile(ast.Expression(body=node), '<fold>', 'eval'),
                    {"__builtins__": {}},
                )
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass

        # Opaque: len("literal") op constant  →  fold
        if (
            isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == 'len'
            and len(node.left.args) == 1
            and isinstance(node.left.args[0], ast.Constant)
            and isinstance(node.left.args[0].value, (str, bytes, list, tuple))
            and all(isinstance(c, ast.Constant) for c in node.comparators)
        ):
            try:
                left_val = len(node.left.args[0].value)
                comparators = [c.value for c in node.comparators]
                # Rebuild with concrete values and fold
                new_node = ast.Compare(
                    left=ast.Constant(value=left_val),
                    ops=node.ops,
                    comparators=[ast.Constant(value=v) for v in comparators],
                )
                result = eval(
                    compile(ast.Expression(body=new_node), '<fold>', 'eval'),
                    {"__builtins__": {}},
                )
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass

        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        """Simplify boolean ops on constants. Also short-circuit mixed operands."""
        self.generic_visit(node)

        # All constants — fully evaluate
        if all(isinstance(v, ast.Constant) for v in node.values):
            try:
                result = eval(
                    compile(ast.Expression(body=node), '<fold>', 'eval'),
                    {"__builtins__": {}},
                )
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass

        # Short-circuit: (True and x) → x,  (False or x) → x
        if isinstance(node.op, ast.And):
            new_vals = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    if not v.value:  # False and ... → False
                        self.changes_made += 1
                        return ast.Constant(value=False)
                    # True and ... → skip this operand
                    self.changes_made += 1
                    continue
                new_vals.append(v)
            if not new_vals:
                return ast.Constant(value=True)
            if len(new_vals) == 1:
                return new_vals[0]
            node.values = new_vals

        elif isinstance(node.op, ast.Or):
            new_vals = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    if v.value:  # True or ... → True
                        self.changes_made += 1
                        return ast.Constant(value=True)
                    # False or ... → skip
                    self.changes_made += 1
                    continue
                new_vals.append(v)
            if not new_vals:
                return ast.Constant(value=False)
            if len(new_vals) == 1:
                return new_vals[0]
            node.values = new_vals

        return node

    # --- Constant subscript folding --------------------------------------------

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        """
        Fold constant subscripts:
          (1, 2, 3)[0]     → 1
          "hello"[1]       → 'e'
          "hello"[1:3]     → 'el'
          [10, 20][1]      → 20
          {'a': 1}['a']    → 1   (only for string/int keys)
        """
        self.generic_visit(node)

        try:
            # Only fold when both container and index are pure constants
            container = ast.literal_eval(node.value)
            idx = node.slice

            if isinstance(idx, ast.Constant):
                result = container[idx.value]
                self.changes_made += 1
                return ast.Constant(value=result)

            if isinstance(idx, ast.Slice):
                lower = idx.lower.value if isinstance(idx.lower, ast.Constant) else None
                upper = idx.upper.value if isinstance(idx.upper, ast.Constant) else None
                step  = idx.step.value  if isinstance(idx.step,  ast.Constant) else None
                if idx.lower is None: lower = None
                if idx.upper is None: upper = None
                if idx.step  is None: step  = None
                result = container[lower:upper:step]
                self.changes_made += 1
                return ast.Constant(value=result)
        except Exception:
            pass

        return node

    # --- Dead branch removal ---------------------------------------------------

    def visit_If(self, node: ast.If) -> Union[ast.If, List[ast.stmt]]:
        """
        if True:  body         → body
        if False: body else:x  → x
        if False: body         → []
        Also: if x: pass → [] when there's no else
        """
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant):
            self.changes_made += 1
            if node.test.value:
                return node.body
            else:
                return node.orelse if node.orelse else []

        # Remove empty if branches: if x: pass  (no else)
        if (
            not node.orelse
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            self.changes_made += 1
            return []

        # Remove redundant else after unconditional return/raise/continue/break
        # if x: return y \n else: z  →  if x: return y \n z
        if node.orelse and _body_always_exits(node.body):
            self.changes_made += 1
            # Return body + orelse flattened (de-nest the else)
            return [ast.If(test=node.test, body=node.body, orelse=[])] + node.orelse

        return node

    def visit_While(self, node: ast.While) -> Union[ast.While, List]:
        """Remove while False: ... entirely"""
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant) and not node.test.value:
            self.changes_made += 1
            return []

        return node

    def visit_IfExp(self, node: ast.IfExp) -> ast.expr:
        """x if True else y → x, x if False else y → y"""
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant):
            self.changes_made += 1
            return node.body if node.test.value else node.orelse

        return node

    # --- Assert cleanup --------------------------------------------------------

    def visit_Assert(self, node: ast.Assert) -> Union[ast.Assert, List]:
        """
        assert True  → removed
        assert False → kept (it's intentional, like a type guard or unreachable marker)
        assert 1==1  → removed  (constant fold already happened)
        """
        self.generic_visit(node)
        if isinstance(node.test, ast.Constant) and node.test.value:
            self.changes_made += 1
            return []
        return node

    # --- Dead code after exit statements --------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _linearize_state_machines(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _linearize_state_machines(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.generic_visit(node)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _linearize_state_machines(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_With(self, node: ast.With) -> ast.With:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_Try(self, node: ast.Try) -> Union[ast.Try, List]:
        """
        Remove try blocks with empty bodies after cleaning.
        Remove bare except: pass handlers that catch nothing meaningful.
        """
        self.generic_visit(node)

        # Strip except handlers that are pure pass (no-ops)
        node.handlers = [
            h for h in node.handlers
            if not (len(h.body) == 1 and isinstance(h.body[0], ast.Pass) and h.type is None)
        ]

        # If body is empty after cleaning, replace try with finally block only
        if not node.body or all(isinstance(s, ast.Pass) for s in node.body):
            if node.finalbody:
                self.changes_made += 1
                return node.finalbody
            self.changes_made += 1
            return []

        return node

    # ── Useless assignment removal ────────────────────────────────────────────

    def visit_Assign(self, node: ast.Assign) -> Union[ast.Assign, List]:
        """Remove x = x (self-assignment no-ops)"""
        self.generic_visit(node)

        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.targets[0].id == node.value.id
        ):
            self.changes_made += 1
            return []

        return node

    def visit_Expr(self, node: ast.Expr) -> Union[ast.Expr, List]:
        """Remove standalone constant expressions (not docstrings in position)."""
        self.generic_visit(node)
        # Remove pure constant expressions that aren't useful
        # (obfuscators sometimes insert standalone string constants as decoys)
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float, bool)):
            self.changes_made += 1
            return []
        return node


# --- Dead code removal --------------------------------------------------------

def _body_always_exits(stmts: List[ast.stmt]) -> bool:
    """
    Return True if the last meaningful statement in stmts is
    a guaranteed exit (return, raise, break, continue).
    """
    if not stmts:
        return False
    last = stmts[-1]
    return isinstance(last, (ast.Return, ast.Raise, ast.Break, ast.Continue))


def _remove_dead_code(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """
    Remove all statements after the first unconditional exit
    (return / raise / break / continue) at the same block level.
    """
    result = []
    for stmt in stmts:
        result.append(stmt)
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            # Everything after this is dead
            break
    return result


# ─── Control flow flattening reversal ─────────────────────────────────────────

def _linearize_state_machines(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """
    Detect while True: loops that are state machine dispatchers and
    replace them with linearized sequential code.
    """
    result = []
    i = 0
    while i < len(stmts):
        stmt = stmts[i]
        if _is_state_machine_loop(stmt):
            linearized = _extract_state_machine_body(stmt)
            result.extend(linearized)
        else:
            result.append(stmt)
        i += 1
    return result


def _is_state_machine_loop(node: ast.stmt) -> bool:
    if not isinstance(node, ast.While):
        return False
    if not (isinstance(node.test, ast.Constant) and node.test.value in (True, 1)):
        return False
    if not node.body:
        return False
    first = node.body[0]
    if not isinstance(first, ast.If):
        return False
    return _is_state_comparison(first.test)


def _is_state_comparison(test: ast.expr) -> bool:
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if not isinstance(test.left, ast.Name):
        return False
    if not (test.comparators and isinstance(test.comparators[0], ast.Constant)):
        return False
    return isinstance(test.comparators[0].value, int)


def _is_state_assignment(stmt: ast.stmt, state_var_name: str) -> bool:
    return (
        isinstance(stmt, ast.Assign)
        and len(stmt.targets) == 1
        and isinstance(stmt.targets[0], ast.Name)
        and stmt.targets[0].id == state_var_name
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, int)
    )


def _extract_state_machine_body(while_node: ast.While) -> List[ast.stmt]:
    branches: dict = {}
    current_if = while_node.body[0] if while_node.body else None

    if not (isinstance(current_if, ast.If) and _is_state_comparison(current_if.test)):
        return [while_node]
    state_var_name = current_if.test.left.id

    while isinstance(current_if, ast.If) and _is_state_comparison(current_if.test):
        state_num = current_if.test.comparators[0].value
        body_without_state = [
            s for s in current_if.body
            if not _is_state_assignment(s, state_var_name)
            and not isinstance(s, ast.Break)   # remove dispatch break statements
        ]
        branches[state_num] = body_without_state

        if current_if.orelse and isinstance(current_if.orelse[0], ast.If):
            current_if = current_if.orelse[0]
        else:
            if current_if.orelse:
                max_state = max(branches.keys(), default=-1)
                branches[max_state + 1] = [
                    s for s in current_if.orelse
                    if not _is_state_assignment(s, state_var_name)
                    and not isinstance(s, ast.Break)
                ]
            break

    if not branches:
        return [while_node]

    result = []
    for key in sorted(branches.keys()):
        result.extend(branches[key])
    return result if result else [while_node]


# --- Helpers ------------------------------------------------------------------

def _strip_redundant_pass(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """
    Remove pass statements from bodies that already have real statements.
    Keep exactly one pass if the body would otherwise be empty.
    """
    non_pass = [s for s in stmts if not isinstance(s, ast.Pass)]
    if non_pass:
        return non_pass
    return [ast.Pass()]
