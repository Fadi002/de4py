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
from typing import Any, Dict, List, Optional, Set, Tuple


# ─── Detection ────────────────────────────────────────────────────────────────

def _is_state_machine(while_node: ast.While) -> bool:
    test = while_node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotEq)
        and isinstance(test.left, ast.Name)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
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


# ─── Simulator ────────────────────────────────────────────────────────────────

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

        # Build a live variable environment from context assignments
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
        try:
            return eval(
                compile(ast.Expression(body=copy.deepcopy(node)), "<sim>", "eval"),
                {"__builtins__": {"chr": chr, "str": str, "int": int}},
                dict(env),
            )
        except Exception:
            return _FAIL

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
        return False

    def _apply_body(self, body: List[ast.stmt], state: int) -> int:
        """
        Execute a case body:
        - Update env for all non-state-var assignments
        - Return the new state value
        """
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
                        # Regular variable update
                        val = self._eval(stmt.value)
                        if val is not _FAIL:
                            self.env[t.id] = val

                elif isinstance(t, ast.Subscript):
                    # jump_table[key] = val — update env table
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
                    # Update other variables
                    cur = self.env.get(stmt.target.id, 0)
                    val = self._eval(stmt.value)
                    if val is not _FAIL:
                        try:
                            if isinstance(stmt.op, ast.Add):   self.env[stmt.target.id] = cur + val
                            elif isinstance(stmt.op, ast.Sub): self.env[stmt.target.id] = cur - val
                        except Exception:
                            pass

        # Update env with new state so future lookups work
        if next_state is not None:
            self.env[self.sv] = next_state
        return next_state

    def _apply_wildcard(self, state: int) -> int:
        """Apply the wildcard case and return next state."""
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


# ─── Transformer ──────────────────────────────────────────────────────────────

class _SMTransformer(ast.NodeTransformer):

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
        terminal  = test.comparators[0].value

        # Find initial state
        initial = None
        for stmt in reversed(context):
            if (isinstance(stmt, ast.Assign)
                    and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and stmt.targets[0].id == sv
                    and isinstance(stmt.value, ast.Constant)):
                initial = stmt.value.value
                break

        if initial is None:
            return None

        # Build case map
        cases: Dict[int, List[ast.stmt]] = {}
        wildcard = None
        for case in while_node.body[0].cases:
            pat = case.pattern
            if isinstance(pat, ast.MatchValue) and isinstance(pat.value, ast.Constant):
                cases[pat.value.value] = case.body
            elif isinstance(pat, ast.MatchAs) and pat.name is None:
                wildcard = case.body

        sim = _Simulator(sv, initial, terminal, cases, wildcard, context)
        ordered = sim.simulate()

        if not ordered:
            return None

        new_stmts = []
        for _, real in ordered:
            new_stmts.extend(real)

        return new_stmts or None

    # ── Node visitors ──────────────────────────────────────────────────────────

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

    def visit_With(self, node: ast.With) -> ast.With:
        self.generic_visit(node)
        node.body = self._deobfuscate_block(node.body)
        return node


class MatchCaseDeobfuscator:

    def deobfuscate(self, source: str) -> str:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

        for _ in range(6):
            before = ast.unparse(tree)
            transformer = _SMTransformer()
            tree = transformer.visit(tree)
            ast.fix_missing_locations(tree)
            if ast.unparse(tree) == before:
                break

        try:
            return ast.unparse(tree)
        except Exception:
            return source
