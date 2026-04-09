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


# --- Local helper for try/except safety checking ----------------------------

def _is_safe_block(stmts) -> bool:
    """Return True if the block has no function calls (safe to strip bare except:pass)."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                return False
            if isinstance(node, (ast.Raise, ast.Assert)):
                return False
    return True


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

        try:
            # Multi-pass: some folds enable further folds (e.g., if True: if True: x)
            for _ in range(5):
                prev_changes = self.changes_made
                tree = self.visit(tree)
                ast.fix_missing_locations(tree)
                if self.changes_made == prev_changes:
                    break  # Converged

            tree = _ensure_valid_bodies(tree)
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except RecursionError:
            return source
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
        Also catches opaque predicates like len('') == 0 → True,
        and type(N) == str → False, type(N) == int → True, etc."""
        self.generic_visit(node)

        # Opaque: type(CONSTANT) == TYPENAME  →  fold to bool
        if (len(node.ops) == 1
                and isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.Is, ast.IsNot))
                and isinstance(node.left, ast.Call)
                and isinstance(node.left.func, ast.Name)
                and node.left.func.id == 'type'
                and len(node.left.args) == 1
                and isinstance(node.left.args[0], ast.Constant)
                and len(node.comparators) == 1
                and isinstance(node.comparators[0], ast.Name)):
            type_name = node.comparators[0].id
            actual_type = type(node.left.args[0].value).__name__
            _TYPE_NAMES = {'int', 'str', 'float', 'bool', 'bytes', 'list', 'dict',
                           'set', 'tuple', 'type', 'NoneType'}
            if type_name in _TYPE_NAMES:
                match = (actual_type == type_name)
                if isinstance(node.ops[0], (ast.NotEq, ast.IsNot)):
                    match = not match
                self.changes_made += 1
                return ast.Constant(value=match)

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
        # NOTE: do NOT run _remove_unused_junk_assignments on branch bodies here.
        # Branch bodies are sub-scopes; the return/use of a variable may be outside
        # the branch, making it appear unused locally when it is not.

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
        """Remove while False: ... entirely. Also clean junk from while True bodies."""
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant) and not node.test.value:
            self.changes_made += 1
            return []

        node.body = _remove_dead_code(node.body)
        node.body = _remove_unused_junk_assignments(node.body)
        node.body = _strip_redundant_pass(node.body)
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
        node.body = _remove_unused_junk_assignments(node.body)
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
        node.body = _remove_unused_junk_assignments(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _remove_unused_junk_assignments(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_With(self, node: ast.With) -> ast.With:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _remove_unused_junk_assignments(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_Try(self, node: ast.Try) -> Union[ast.Try, List]:
        """
        Remove try blocks with empty bodies after cleaning.
        Remove bare except: pass handlers that catch nothing meaningful.
        Clean dead code inside handler bodies.
        """
        self.generic_visit(node)

        # Clean dead code inside each handler body
        for h in node.handlers:
            h.body = _remove_dead_code(h.body)
            h.body = _remove_unused_junk_assignments(h.body)
            h.body = _strip_redundant_pass(h.body)

        # Strip except handlers that are pure pass AND only when the try body is safe
        # (no function calls). This prevents stripping legitimate error-suppression patterns.
        body_is_safe = _is_safe_block(node.body)
        node.handlers = [
            h for h in node.handlers
            if not (body_is_safe
                    and len(h.body) == 1
                    and isinstance(h.body[0], ast.Pass)
                    and h.type is None
                    and not h.name)
        ]

        # If body is empty after cleaning, replace try with finally block only
        if not node.body or all(isinstance(s, ast.Pass) for s in node.body):
            if getattr(node, 'finalbody', None):
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
        # Remove pure numeric/bool constant expressions (obfuscator decoys)
        # But keep strings (possible docstrings), Ellipsis, and None (used as sentinels)
        if isinstance(node.value, ast.Constant):
            val = node.value.value
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                self.changes_made += 1
                return []
        # Remove bare Name expressions that are just variable references with no effect
        # EXCEPT when they could have side effects — only strip simple names that are
        # clearly obfuscation padding (single/double char, pure obfuscated names)
        if isinstance(node.value, ast.Name):
            name = node.value.id
            # Only strip if it looks like an obfuscated padding variable (e.g. bare `a;a;a;`)
            if len(name) <= 2 and name.isidentifier() and name.islower():
                self.changes_made += 1
                return []
        return node


# --- Junk assignment removal --------------------------------------------------

def _remove_unused_junk_assignments(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """
    Remove assignments of the form: name = constant
    where `name` is never read anywhere in the same statement list.
    Only removes trivially-pure constant assignments (int, float, str, bool, None, tuple of consts).
    Never removes assignments to names that appear in f-strings, returns, or nested scopes.
    """
    if not stmts:
        return stmts

    # Collect all names that are READ anywhere in the block (including nested expressions)
    read_names: set = set()
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                read_names.add(node.id)

    # Find trivial constant assignments where the name is never read
    def _is_trivial_const(val_node) -> bool:
        if isinstance(val_node, ast.Constant):
            return True
        if isinstance(val_node, ast.UnaryOp) and isinstance(val_node.op, ast.USub):
            return isinstance(val_node.operand, ast.Constant)
        if isinstance(val_node, (ast.Tuple, ast.List)):
            return all(_is_trivial_const(e) for e in val_node.elts)
        return False

    result = []
    for stmt in stmts:
        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and _is_trivial_const(stmt.value)
                and stmt.targets[0].id not in read_names):
            continue  # Drop the junk assignment
        result.append(stmt)
    # Never return an empty body - keep at least one pass to maintain valid structure
    return result if result else stmts


# --- Body validity guard ------------------------------------------------------

def _ensure_valid_bodies(tree: ast.AST) -> ast.AST:
    """
    Walk the AST and ensure no compound statement has an empty body.
    Empty bodies (if/while/for/with/try/except/def/class) are invalid Python —
    insert Pass() to prevent SyntaxError in ast.unparse().
    """
    for node in ast.walk(tree):
        for field in ('body', 'orelse', 'finalbody'):
            val = getattr(node, field, None)
            if isinstance(val, list) and len(val) == 0:
                needs_body = isinstance(node, (
                    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                    ast.If, ast.While, ast.For, ast.With,
                    ast.Try, ast.ExceptHandler,
                ))
                if needs_body and field == 'body':
                    val.append(ast.Pass())
    return tree


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
    """Detect while True: loops used as state machine dispatchers."""
    if not isinstance(node, ast.While):
        return False
    if not (isinstance(node.test, ast.Constant) and node.test.value in (True, 1)):
        return False
    if not node.body:
        return False
    # Pattern 1: first stmt is an if with state comparison (elif chain style)
    first = node.body[0]
    if isinstance(first, ast.If) and _is_state_comparison(first.test):
        return True
    # Pattern 2: body has multiple sequential `if state_var == N:` blocks
    state_ifs = [s for s in node.body if isinstance(s, ast.If) and _is_state_comparison(s.test)]
    if len(state_ifs) >= 2:
        return True
    return False


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


def _get_state_next(body: List[ast.stmt], state_var_name: str):
    """Return the integer constant the state var is set to in body, or None."""
    for s in reversed(body):
        if (isinstance(s, ast.Assign)
                and len(s.targets) == 1
                and isinstance(s.targets[0], ast.Name)
                and s.targets[0].id == state_var_name
                and isinstance(s.value, ast.Constant)
                and isinstance(s.value.value, int)):
            return s.value.value
    return None


def _collect_if_elif_branches(if_node: ast.If, state_var_name: str) -> dict:
    """
    Walk the if/elif chain and collect {state_int: (real_stmts, next_state_or_None)}.
    """
    branches: dict = {}
    current = if_node

    while isinstance(current, ast.If) and _is_state_comparison(current.test):
        state_num = current.test.comparators[0].value
        body = current.body
        next_state = _get_state_next(body, state_var_name)
        real_stmts = [
            s for s in body
            if not _is_state_assignment(s, state_var_name)
            and not isinstance(s, (ast.Continue, ast.Break))
        ]
        branches[state_num] = (real_stmts, next_state)

        if current.orelse and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
        else:
            break

    return branches


def _simulate_state_machine(branches: dict, init_state: int) -> List[ast.stmt]:
    """Follow state transitions and return linearised statements."""
    result: List[ast.stmt] = []
    visited: set = set()
    state = init_state

    for _ in range(200):
        if state not in branches:
            break
        if state in visited:
            break
        visited.add(state)

        real_stmts, next_state = branches[state]
        result.extend(real_stmts)

        # If the real stmts end with an unconditional exit, stop linearising
        if real_stmts and isinstance(real_stmts[-1], (ast.Return, ast.Raise)):
            break

        if next_state is None:
            break
        state = next_state

    return result


def _extract_state_machine_body(while_node: ast.While) -> List[ast.stmt]:
    body = while_node.body

    # Determine state var name from first state-comparison if
    state_var_name = None
    for s in body:
        if isinstance(s, ast.If) and _is_state_comparison(s.test):
            state_var_name = s.test.left.id
            break
    if state_var_name is None:
        return [while_node]

    # Collect branches from BOTH patterns:
    # Pattern A: elif chain starting from first stmt
    # Pattern B: multiple separate if-statements in the body
    branches = {}

    first = body[0]
    if isinstance(first, ast.If) and _is_state_comparison(first.test):
        # Try elif chain first
        branches = _collect_if_elif_branches(first, state_var_name)

    # Also scan for separate if-stmts (Pattern B) — they may add states
    # missing from the elif chain (or replace it entirely)
    sep_branches = {}
    for s in body:
        if isinstance(s, ast.If) and _is_state_comparison(s.test):
            state_num = s.test.comparators[0].value
            next_state = _get_state_next(s.body, state_var_name)
            real_stmts = [
                stmt for stmt in s.body
                if not _is_state_assignment(stmt, state_var_name)
                and not isinstance(stmt, (ast.Continue, ast.Break))
            ]
            sep_branches[state_num] = (real_stmts, next_state)

    # Merge: prefer sep_branches when they have more coverage
    if len(sep_branches) >= len(branches):
        branches = sep_branches

    if not branches:
        return [while_node]

    init_state = 0 if 0 in branches else min(branches.keys())
    result = _simulate_state_machine(branches, init_state)

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
