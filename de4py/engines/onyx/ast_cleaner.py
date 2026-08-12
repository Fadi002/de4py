# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
from typing import List, Union

from de4py.engines.onyx.safe_eval import safe_eval_scalar


def _is_safe_block(stmts) -> bool:
    """True when the block has no calls or raises (safe to strip bare except:pass)."""
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call):
                return False
            if isinstance(node, (ast.Raise, ast.Assert)):
                return False
    return True


class ASTCleaner(ast.NodeTransformer):

    def __init__(self):
        self.changes_made = 0

    def clean(self, source: str) -> str:
        """Parse, transform, and unparse; source is returned unchanged on failure."""
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
                    break

            tree = _ensure_valid_bodies(tree)
            ast.fix_missing_locations(tree)
            return ast.unparse(tree)
        except RecursionError:
            return source
        except Exception:
            return source

    def visit_BinOp(self, node: ast.BinOp) -> ast.expr:
        self.generic_visit(node)

        if isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            try:
                safe_ops = (
                    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                    ast.Mod, ast.Pow, ast.BitXor, ast.BitAnd, ast.BitOr,
                    ast.LShift, ast.RShift,
                )
                if isinstance(node.op, safe_ops):
                    # Guard against huge string repeats (e.g. 'x' * 1_000_000)
                    if isinstance(node.op, ast.Mult):
                        a, b = node.left.value, node.right.value
                        if isinstance(a, str) and isinstance(b, int) and len(a) * b > 4096:
                            return node
                        if isinstance(b, str) and isinstance(a, int) and len(b) * a > 4096:
                            return node
                    ok, result = safe_eval_scalar(node)
                    if ok:
                        self.changes_made += 1
                        return ast.Constant(value=result)
            except Exception:
                pass
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.expr:
        self.generic_visit(node)

        if (
            isinstance(node.op, ast.Not)
            and isinstance(node.operand, ast.UnaryOp)
            and isinstance(node.operand.op, ast.Not)
        ):
            self.changes_made += 1
            return node.operand.operand

        if isinstance(node.operand, ast.Constant):
            try:
                ok, result = safe_eval_scalar(node)
                if not ok:
                    return node
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass
        return node

    def visit_Compare(self, node: ast.Compare) -> ast.expr:
        self.generic_visit(node)

        # Opaque predicates: type(CONST) == TYPENAME  →  bool
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
                ok, result = safe_eval_scalar(node)
                if not ok:
                    return node
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass

        # Opaque predicates: len("literal") op constant  →  fold
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
                new_node = ast.Compare(
                    left=ast.Constant(value=left_val),
                    ops=node.ops,
                    comparators=[ast.Constant(value=v) for v in comparators],
                )
                ok, result = safe_eval_scalar(new_node)
                if not ok:
                    return node
                self.changes_made += 1
                return ast.Constant(value=result)
            except Exception:
                pass

        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.expr:
        self.generic_visit(node)

        # A failed fold falls through to the short-circuit rules below.
        if all(isinstance(v, ast.Constant) for v in node.values):
            ok, result = safe_eval_scalar(node)
            if ok:
                self.changes_made += 1
                return ast.Constant(value=result)

        # A walrus operand binds a name as a side effect, so a deciding
        # constant can trim the node but never collapse it.
        has_named_expr = any(isinstance(v, ast.NamedExpr) for v in node.values)

        if isinstance(node.op, ast.And):
            new_vals = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    if not v.value:
                        if has_named_expr:
                            new_vals.append(v)
                            break
                        self.changes_made += 1
                        return ast.Constant(value=False)
                    self.changes_made += 1
                    continue
                new_vals.append(v)
            if not new_vals:
                return ast.Constant(value=True)
            if len(new_vals) == 1 and not has_named_expr:
                return new_vals[0]
            if new_vals != node.values:
                node.values = new_vals

        elif isinstance(node.op, ast.Or):
            new_vals = []
            for v in node.values:
                if isinstance(v, ast.Constant):
                    if v.value:
                        if has_named_expr:
                            new_vals.append(v)
                            break
                        self.changes_made += 1
                        return ast.Constant(value=True)
                    self.changes_made += 1
                    continue
                new_vals.append(v)
            if not new_vals:
                return ast.Constant(value=False)
            if len(new_vals) == 1 and not has_named_expr:
                return new_vals[0]
            if new_vals != node.values:
                node.values = new_vals

        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.expr:
        self.generic_visit(node)

        try:
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

    def visit_If(self, node: ast.If) -> Union[ast.If, List[ast.stmt]]:
        self.generic_visit(node)
        # Do NOT run _remove_unused_junk_assignments on branch bodies: they are
        # sub-scopes, and a variable used outside the branch would look locally
        # unused.

        if isinstance(node.test, ast.Constant):
            self.changes_made += 1
            if node.test.value:
                return node.body
            else:
                return node.orelse if node.orelse else []

        # Deduplicate: if cond: X else: X  →  X
        if (node.orelse
                and len(node.body) == len(node.orelse)
                and all(ast.dump(a) == ast.dump(b)
                        for a, b in zip(node.body, node.orelse))):
            self.changes_made += 1
            return node.body

        if (
            not node.orelse
            and len(node.body) == 1
            and isinstance(node.body[0], ast.Pass)
        ):
            self.changes_made += 1
            return []

        # Else after an unconditional exit is dead; de-nest it.
        if node.orelse and _body_always_exits(node.body):
            self.changes_made += 1
            return [ast.If(test=node.test, body=node.body, orelse=[])] + node.orelse

        return node

    def visit_While(self, node: ast.While) -> Union[ast.While, List]:
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant) and not node.test.value:
            self.changes_made += 1
            return []

        node.body = _remove_dead_code(node.body)
        node.body = _remove_unused_junk_assignments(node.body)
        node.body = _strip_redundant_pass(node.body)
        return node

    def visit_IfExp(self, node: ast.IfExp) -> ast.expr:
        self.generic_visit(node)

        if isinstance(node.test, ast.Constant):
            self.changes_made += 1
            return node.body if node.test.value else node.orelse

        return node

    def visit_Assert(self, node: ast.Assert) -> Union[ast.Assert, List]:
        # assert False stays: it is an intentional guard, not dead code.
        self.generic_visit(node)
        if isinstance(node.test, ast.Constant) and node.test.value:
            self.changes_made += 1
            return []
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.body = _remove_dead_code(node.body)
        node.body = _propagate_local_constants(node.body)
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
        node.body = _propagate_local_constants(node.body)
        node.body = _linearize_state_machines(node.body)
        # Do NOT run _remove_unused_junk_assignments on the module body: a
        # top-level binding is still payload the analyst reads, and an importer
        # may read it.
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
        self.generic_visit(node)

        for h in node.handlers:
            h.body = _remove_dead_code(h.body)
            h.body = _remove_unused_junk_assignments(h.body)
            h.body = _strip_redundant_pass(h.body)

        # Only strip a bare except:pass when the try body has no calls, so real
        # error-suppression patterns survive.
        body_is_safe = _is_safe_block(node.body)
        node.handlers = [
            h for h in node.handlers
            if not (body_is_safe
                    and len(h.body) == 1
                    and isinstance(h.body[0], ast.Pass)
                    and h.type is None
                    and not h.name)
        ]

        # Stripping every handler can leave a try with neither except nor
        # finally, which is invalid syntax; unwrap to the body instead.
        if not node.handlers and not getattr(node, 'finalbody', None):
            self.changes_made += 1
            return node.body

        if not node.body or all(isinstance(s, ast.Pass) for s in node.body):
            if getattr(node, 'finalbody', None):
                self.changes_made += 1
                return node.finalbody
            self.changes_made += 1
            return []

        return node

    def visit_Assign(self, node: ast.Assign) -> Union[ast.Assign, List]:
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
        self.generic_visit(node)
        # Strip pure numeric/bool decoys, but keep strings (possible
        # docstrings), Ellipsis, and None (used as sentinels).
        if isinstance(node.value, ast.Constant):
            val = node.value.value
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                self.changes_made += 1
                return []
        # Short lowercase bare names are obfuscation padding.
        if isinstance(node.value, ast.Name):
            name = node.value.id
            if len(name) <= 2 and name.isidentifier() and name.islower():
                self.changes_made += 1
                return []
        return node


class _ConstSubstituter(ast.NodeTransformer):
    def __init__(self, const_map: dict):
        self._map = const_map

    def visit_Name(self, node: ast.Name) -> ast.expr:
        if isinstance(node.ctx, ast.Load) and node.id in self._map:
            return ast.copy_location(ast.Constant(value=self._map[node.id]), node)
        return node

    # Do NOT substitute into nested scopes
    def visit_FunctionDef(self, node): return node
    visit_AsyncFunctionDef = visit_FunctionDef
    visit_ClassDef = visit_FunctionDef
    visit_Lambda = visit_FunctionDef


def _assigned_names(node: ast.AST) -> set:
    names: set = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                names.update(_target_names(target))
        elif isinstance(child, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            names.update(_target_names(child.target))
        elif isinstance(child, (ast.For, ast.comprehension)):
            names.update(_target_names(child.target))
        elif isinstance(child, ast.Nonlocal):
            # nonlocal rebinds the enclosing scope, not a local.
            names.update(child.names)
    return names


def _target_names(target: ast.AST) -> set:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        found: set = set()
        for elt in target.elts:
            found |= _target_names(elt)
        return found
    return set()


def _propagate_local_constants(stmts: list) -> list:
    """Forward-propagate constant assignments, invalidating on reassignment."""
    if not stmts:
        return stmts

    const_map = {}
    result = []
    for stmt in stmts:
        if const_map and not isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            active = const_map
            if isinstance(stmt, (ast.While, ast.For, ast.If, ast.Try, ast.With,
                                 ast.AsyncFor, ast.AsyncWith)):
                # A value that holds on entry need not hold at every point
                # inside: a compound statement may rebind the name in one
                # branch before a later branch reads it. Substituting there
                # rewrites an accumulated value back to its initializer.
                reassigned = _assigned_names(stmt)
                active = {k: v for k, v in const_map.items() if k not in reassigned}
            if active:
                stmt = _ConstSubstituter(active).visit(stmt)
                ast.fix_missing_locations(stmt)

        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            name = stmt.targets[0].id
            if isinstance(stmt.value, ast.Constant):
                const_map[name] = stmt.value.value
            else:
                const_map.pop(name, None)
        elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)):
            t = getattr(stmt, 'target', None)
            if t and isinstance(t, ast.Name):
                const_map.pop(t.id, None)
        elif isinstance(stmt, (ast.While, ast.For, ast.If, ast.Try, ast.With)):
            for name in _assigned_names(stmt):
                const_map.pop(name, None)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # A nested def's locals shadow; only `nonlocal` names can
            # invalidate this scope's map.
            nonlocal_names: set = set()
            for child in ast.walk(stmt):
                if isinstance(child, ast.Nonlocal):
                    nonlocal_names.update(child.names)
            for name in nonlocal_names:
                const_map.pop(name, None)

        result.append(stmt)
    return result

def _remove_unused_junk_assignments(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """
    Remove trivially-pure constant assignments to names never read in the same
    statement list. Never touches names read via f-strings, returns, or nested
    scopes.
    """
    if not stmts:
        return stmts

    read_names: set = set()
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                read_names.add(node.id)
            # `acc += x` reads the old value, but its target is a Store, so the
            # scan above misses it. Dropping the initializer of an accumulator
            # leaves an unbound name and silently changes the program.
            elif isinstance(node, ast.AugAssign):
                for sub in ast.walk(node.target):
                    if isinstance(sub, ast.Name):
                        read_names.add(sub.id)
            # `obj[i] = v` and `obj.attr = v` read `obj` in order to mutate it.
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (node.targets if isinstance(node, ast.Assign)
                           else [node.target])
                for target in targets:
                    for sub in ast.walk(target):
                        if isinstance(sub, (ast.Subscript, ast.Attribute)):
                            for inner in ast.walk(sub.value):
                                if isinstance(inner, ast.Name):
                                    read_names.add(inner.id)
            # `nonlocal x` / `global x` makes an assignment visible to another
            # scope, so this scan cannot prove the name dead.
            elif isinstance(node, (ast.Nonlocal, ast.Global)):
                read_names.update(node.names)

    def _has_side_effects(val_node) -> bool:
        """True if val_node contains any function call (conservative)."""
        for n in ast.walk(val_node):
            if isinstance(n, ast.Call):
                return True
        return False

    def _is_trivial_const(val_node) -> bool:
        if isinstance(val_node, ast.Constant):
            return True
        if isinstance(val_node, ast.Name):
            return True  # bare name read — no side effects
        if isinstance(val_node, ast.UnaryOp) and isinstance(val_node.op, ast.USub):
            return isinstance(val_node.operand, ast.Constant)
        if isinstance(val_node, (ast.Tuple, ast.List)):
            return all(_is_trivial_const(e) for e in val_node.elts)
        if isinstance(val_node, ast.IfExp) and not _has_side_effects(val_node):
            return True
        if isinstance(val_node, ast.Attribute) and not _has_side_effects(val_node):
            return True
        return False

    result = []
    for stmt in stmts:
        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and _is_trivial_const(stmt.value)
                and stmt.targets[0].id not in read_names):
            continue
        result.append(stmt)
    # Keep at least one pass so no body becomes empty
    return result if result else stmts


def _ensure_valid_bodies(tree: ast.AST) -> ast.AST:
    """Insert Pass() into any compound body that would otherwise be empty."""
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


def _body_always_exits(stmts: List[ast.stmt]) -> bool:
    if not stmts:
        return False
    last = stmts[-1]
    return isinstance(last, (ast.Return, ast.Raise, ast.Break, ast.Continue))


def _remove_dead_code(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """Drop everything after the first unconditional exit at this block level."""
    result = []
    for stmt in stmts:
        result.append(stmt)
        if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            break
    return result


def _linearize_state_machines(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """Replace while True: state-machine dispatchers with linearized code."""
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
    """Collect {state_int: (real_stmts, next_state_or_None)} from the if/elif chain."""
    branches = {}
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

        if real_stmts and isinstance(real_stmts[-1], (ast.Return, ast.Raise)):
            break

        if next_state is None:
            break
        state = next_state

    return result


def _extract_state_machine_body(while_node: ast.While) -> List[ast.stmt]:
    body = while_node.body

    state_var_name = None
    for s in body:
        if isinstance(s, ast.If) and _is_state_comparison(s.test):
            state_var_name = s.test.left.id
            break
    if state_var_name is None:
        return [while_node]

    # Collect branches from both patterns:
    # Pattern A: elif chain starting from first stmt
    # Pattern B: multiple separate if-statements in the body
    branches = {}

    first = body[0]
    if isinstance(first, ast.If) and _is_state_comparison(first.test):
        branches = _collect_if_elif_branches(first, state_var_name)

    # Pattern B may add states missing from the elif chain (or replace it).
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

    # Prefer sep_branches when they cover more states.
    if len(sep_branches) >= len(branches):
        branches = sep_branches

    if not branches:
        return [while_node]

    init_state = 0 if 0 in branches else min(branches.keys())
    result = _simulate_state_machine(branches, init_state)

    return result if result else [while_node]


def _strip_redundant_pass(stmts: List[ast.stmt]) -> List[ast.stmt]:
    """Drop pass statements unless the body would otherwise be empty."""
    non_pass = [s for s in stmts if not isinstance(s, ast.Pass)]
    if non_pass:
        return non_pass
    return [ast.Pass()]
