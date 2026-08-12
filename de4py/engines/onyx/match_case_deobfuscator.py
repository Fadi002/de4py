# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Deobfuscates Cyron-style state machine obfuscation.

    state_var = INITIAL
    jump_table = {K: V, ...}
    while state_var != TERMINAL:
        match state_var:
            case N:
                <real code>
                state_var = next_state  # or +=/-= N, = table[var]
            case _:
                jump_table[str(state_var)] = state_var + delta
                state_var -= step

Fully simulates the state machine tracking ALL variable mutations,
including mid-execution updates to delta/step values.
"""

import ast
import copy

from de4py.engines.onyx.safe_eval import safe_eval
from typing import Any, Dict, List, Optional, Set, Tuple


def _literal_number(node: ast.expr) -> Tuple[bool, Any]:
    """
    ``ast.Constant`` for a positive literal, but ``-1`` parses as
    ``UnaryOp(USub, Constant(1))`` — a very common terminal/initial-state
    sentinel in flattened state machines, so it must be unwrapped here rather
    than only in the (separate) runtime evaluator.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return True, node.value
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd))
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))):
        value = node.operand.value
        return True, (-value if isinstance(node.op, ast.USub) else value)
    return False, None


def _is_state_machine(while_node: ast.While) -> bool:
    test = while_node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotEq)
        and isinstance(test.left, ast.Name)
        and len(test.comparators) == 1
        and _literal_number(test.comparators[0])[0]
    ):
        return False
    if not (len(while_node.body) == 1 and isinstance(while_node.body[0], ast.Match)):
        return False
    m = while_node.body[0]
    if not (isinstance(m.subject, ast.Name) and m.subject.id == test.left.id):
        return False
    return True


def _find_jump_table(stmts: List[ast.stmt]) -> Optional[str]:
    """Return the name of the first literal-dict assignment in stmts."""
    for stmt in stmts:
        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Dict)):
            return stmt.targets[0].id
    return None


def _names_in(node: Optional[ast.AST]) -> Set[str]:
    if node is None:
        return set()
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _control_names(while_node: ast.While, sv: str, wildcard) -> Set[str]:
    """
    Names the dispatcher itself reads or writes to decide the next state.

    A name qualifies only through evidence: it feeds a state transition, it is
    the jump table being mutated, or it lives in the wildcard branch whose sole
    job is computing the next state. Nothing here is inferred from naming.
    """
    names = {sv}
    match_node = while_node.body[0]

    for case in match_node.cases:
        for stmt in case.body:
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == sv):
                names |= _names_in(stmt.value)
            elif (isinstance(stmt, ast.AugAssign)
                    and isinstance(stmt.target, ast.Name)
                    and stmt.target.id == sv):
                names |= _names_in(stmt.value)
            elif (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Subscript)):
                names |= _names_in(stmt.targets[0])
                names |= _names_in(stmt.value)

    for stmt in (wildcard or []):
        names |= _names_in(stmt)

    return names


class _Simulator:
    """Evaluates a Cyron state machine by tracking all variable values."""

    MAX_STEPS = 500

    def __init__(
        self,
        state_var:    str,
        initial:      int,
        terminal:     int,
        cases:        Dict[int, List[ast.stmt]],
        wildcard:     Optional[List[ast.stmt]],
        context:      List[ast.stmt],
    ):
        self.sv       = state_var
        self.initial  = initial
        self.terminal = terminal
        self.cases    = cases
        self.wildcard = wildcard

        self.env: Dict[str, Any] = {}
        for stmt in context:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                name = stmt.targets[0].id if isinstance(stmt.targets[0], ast.Name) else None
                if name:
                    val = self._eval(stmt.value, prior_env=self.env)
                    if val is not _FAIL:
                        self.env[name] = val

    def _eval(self, node: ast.expr, prior_env: Optional[Dict] = None) -> Any:
        env = prior_env if prior_env is not None else self.env
        ok, value = safe_eval(node, env)
        return value if ok else _FAIL

    def _is_state_manip(self, stmt: ast.stmt) -> bool:
        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and stmt.targets[0].id == self.sv):
            return True
        if (isinstance(stmt, ast.AugAssign)
                and isinstance(stmt.target, ast.Name)
                and stmt.target.id == self.sv):
            return True
        # Jump-table subscript assignment
        if (isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Subscript)):
            return True
        # A bare break/continue inside a case body of this dispatcher shape can
        # only be the flattener's own synthetic "end of program" marker: any
        # block containing a REAL break/continue could not have been flattened
        # in the first place without first proving where control resumes, which
        # is exactly what a generic flattener cannot do — a genuine loop-exit is
        # always left in an unflattened block by construction (verified against
        # Dor-CFF's DCFF.py: FlBody refuses to flatten a block containing one).
        if isinstance(stmt, (ast.Break, ast.Continue)):
            return True
        return False

    def _apply_body(self, body: List[ast.stmt], state: int) -> int:
        """Execute a case body, updating env and returning the new state."""
        next_state = None

        for stmt in body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]

                if isinstance(t, ast.Name):
                    if t.id == self.sv:
                        # State transition — evaluate but DON'T update env yet
                        # (so other stmts in this body still see old state value)
                        val = self._eval(stmt.value)
                        if val is not _FAIL:
                            next_state = val
                    else:
                        val = self._eval(stmt.value)
                        if val is not _FAIL:
                            self.env[t.id] = val

                elif isinstance(t, ast.Subscript):
                    tbl_name = ast.unparse(t.value)
                    key = self._eval(t.slice)
                    val = self._eval(stmt.value)
                    if key is not _FAIL and val is not _FAIL:
                        if tbl_name not in self.env or not isinstance(self.env[tbl_name], dict):
                            self.env[tbl_name] = {}
                        self.env[tbl_name][key] = val

            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                if stmt.target.id == self.sv:
                    val = self._eval(stmt.value)
                    if val is not _FAIL and isinstance(val, (int, float)):
                        if isinstance(stmt.op, ast.Add):
                            next_state = state + val
                        elif isinstance(stmt.op, ast.Sub):
                            next_state = state - val
                else:
                    cur = self.env.get(stmt.target.id, 0)
                    val = self._eval(stmt.value)
                    if val is not _FAIL:
                        try:
                            if isinstance(stmt.op, ast.Add):   self.env[stmt.target.id] = cur + val
                            elif isinstance(stmt.op, ast.Sub): self.env[stmt.target.id] = cur - val
                        except Exception:
                            pass

            elif isinstance(stmt, (ast.Break, ast.Continue)):
                # The flattener's own synthetic exit (see _is_state_manip) — end
                # the simulated run here, nothing after it can execute.
                next_state = self.terminal
                break

        if next_state is not None:
            self.env[self.sv] = next_state
        return next_state

    def _apply_wildcard(self, state: int) -> int:
        if self.wildcard:
            return self._apply_body(self.wildcard, state)
        return None

    def simulate(self) -> List[Tuple[int, List[ast.stmt]]]:
        """
        Returns ordered list of (state, real_stmts) in execution order.
        """
        result: List[Tuple[int, List[ast.stmt]]] = []
        state  = self.initial
        self.env[self.sv] = state
        visited_states: Set[int] = set()
        steps = 0

        while state != self.terminal and steps < self.MAX_STEPS:
            steps += 1

            if state in self.cases:
                if state in visited_states:
                    # Loop detected — linearization done
                    break
                visited_states.add(state)

                body = self.cases[state]
                real = [s for s in body if not self._is_state_manip(s)]
                if real:
                    result.append((state, real))

                next_s = self._apply_body(body, state)
                if next_s is None:
                    break
                state = next_s

            elif self.wildcard:
                next_s = self._apply_wildcard(state)
                if next_s is None:
                    break
                state = next_s
            else:
                break

        return result


_FAIL = object()


class _SMTransformer(ast.NodeTransformer):

    def __init__(self) -> None:
        super().__init__()
        self.control_names: Set[str] = set()

    def _deobfuscate_block(self, stmts: List[ast.stmt]) -> List[ast.stmt]:
        result = []
        i = 0
        while i < len(stmts):
            stmt = stmts[i]
            if isinstance(stmt, ast.While) and _is_state_machine(stmt):
                linearized = self._linearize(stmt, result)  # result = context so far
                if linearized is not None:
                    result.extend(linearized)
                    i += 1
                    continue
            result.append(stmt)
            i += 1
        return result

    def _linearize(
        self, while_node: ast.While, context: List[ast.stmt]
    ) -> Optional[List[ast.stmt]]:
        test      = while_node.test
        sv        = test.left.id
        _, terminal = _literal_number(test.comparators[0])

        initial = None
        for stmt in reversed(context):
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == sv):
                found, value = _literal_number(stmt.value)
                if found:
                    initial = value
                break

        if initial is None:
            return None

        cases: Dict[int, List[ast.stmt]] = {}
        wildcard = None
        for case in while_node.body[0].cases:
            pat = case.pattern
            if isinstance(pat, ast.MatchValue):
                found, value = _literal_number(pat.value)
                if found:
                    cases[value] = case.body
            elif isinstance(pat, ast.MatchAs) and pat.name is None:
                wildcard = case.body

        sim = _Simulator(sv, initial, terminal, cases, wildcard, context)
        ordered = sim.simulate()

        if not ordered:
            return None

        new_stmts = []
        for _, real in ordered:
            new_stmts.extend(real)

        if not new_stmts:
            return None

        self.control_names |= _control_names(while_node, sv, wildcard)
        return new_stmts

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.ClassDef:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node

    def visit_If(self, node: ast.If) -> ast.If:
        self.generic_visit(node)
        node.body   = self._deobfuscate_block(node.body)
        node.orelse = self._deobfuscate_block(node.orelse)
        return node

    def visit_For(self, node: ast.For) -> ast.For:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node

    def visit_While(self, node: ast.While) -> ast.While:
        # A genuine (non-flattened) while-loop can itself contain a nested
        # synthetic dispatcher in its body — e.g. the flattener left this
        # loop's own control flow alone (it has a real break) but still
        # flattened the straight-line body of an inner loop/branch. Without
        # this visitor, nothing ever block-scans that body for one.
        self.generic_visit(node)
        node.body   = self._deobfuscate_block(node.body)
        node.orelse = self._deobfuscate_block(node.orelse)
        return node

    def visit_With(self, node: ast.With) -> ast.With:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node

    visit_AsyncWith = visit_With

    def visit_Try(self, node: ast.Try) -> ast.Try:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        for handler in node.handlers:
            handler.body = self._deobfuscate_block(handler.body)
        node.orelse    = self._deobfuscate_block(node.orelse)
        node.finalbody = self._deobfuscate_block(node.finalbody)
        return node


_DYNAMIC_SCOPE_CALLS = {"globals", "locals", "vars", "eval", "exec", "compile"}


def _is_pure_value(node: ast.expr) -> bool:
    for n in ast.walk(node):
        if isinstance(n, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom,
                          ast.NamedExpr, ast.Subscript, ast.Attribute)):
            return False
    return True


def _reads_scope_dynamically(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in _DYNAMIC_SCOPE_CALLS):
            return True
    return False


def _loaded_names(tree: ast.AST) -> Set[str]:
    loaded: Set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Store):
            loaded.add(n.id)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            loaded.update(n.names)
    return loaded


class _DeadControlRemover(ast.NodeTransformer):
    """
    Drop assignments to dispatcher control names that nothing reads.

    Removal requires three independent proofs: the simulator identified the name
    as machine state, no Load of it survives anywhere in the tree, and the value
    being discarded cannot have a side effect.
    """

    def __init__(self, dead: Set[str]):
        super().__init__()
        self.dead = dead

    def _filter(self, stmts: List[ast.stmt]) -> List[ast.stmt]:
        kept = []
        for stmt in stmts:
            target = None
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)):
                target = stmt.targets[0].id
            elif (isinstance(stmt, (ast.AugAssign, ast.AnnAssign))
                    and isinstance(stmt.target, ast.Name)):
                target = stmt.target.id

            value = getattr(stmt, "value", None)
            if (target in self.dead and value is not None
                    and _is_pure_value(value)):
                continue
            kept.append(stmt)
        return kept

    def _visit_body(self, node):
        self.generic_visit(node)
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block:
                filtered = self._filter(block)
                if not filtered and not isinstance(node, ast.Module):
                    filtered = [ast.Pass()]
                setattr(node, field, filtered)
        return node

    visit_Module = _visit_body
    visit_FunctionDef = _visit_body
    visit_AsyncFunctionDef = _visit_body
    visit_ClassDef = _visit_body
    visit_If = _visit_body
    visit_For = _visit_body
    visit_AsyncFor = _visit_body
    visit_While = _visit_body
    visit_With = _visit_body
    visit_AsyncWith = _visit_body
    visit_Try = _visit_body


def _drop_dead_control_bindings(tree: ast.AST, control: Set[str]) -> ast.AST:
    if not control or _reads_scope_dynamically(tree):
        return tree
    dead = control - _loaded_names(tree)
    if not dead:
        return tree
    tree = _DeadControlRemover(dead).visit(tree)
    ast.fix_missing_locations(tree)
    return tree


class MatchCaseDeobfuscator:

    def deobfuscate(self, source: str) -> str:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        try:
            control: Set[str] = set()
            for _ in range(6):
                before = ast.unparse(tree)
                transformer = _SMTransformer()
                tree = transformer.visit(tree)
                ast.fix_missing_locations(tree)
                control |= transformer.control_names
                if ast.unparse(tree) == before:
                    break

            tree = _drop_dead_control_bindings(tree, control)
            return ast.unparse(tree)
        except RecursionError:
            return source
        except Exception:
            return source
