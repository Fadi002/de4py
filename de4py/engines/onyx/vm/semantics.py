# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Handler semantic inference.

The previous lifter classified an opcode by searching its unparsed handler text
for substrings, which is order-dependent and wrong in practice: ``push(fn(*args))``
contains ``*`` so a call reads as a multiply, and ``vglobals`` contains ``globals``
so building a nested VM reads as a global store.

This module instead abstractly interprets each handler body over a tiny symbolic
domain — stack slots, the const/name pools, the operand register — and reads the
opcode's meaning off the resulting effect. Classification then depends on what the
handler *does*, so it survives renaming, reordering and formatting changes.
"""

import ast
from typing import Dict, List, Optional, Tuple

from de4py.engines.onyx.vm.ir import (
    BINARY_SYMBOLS,
    COMPARE_SYMBOLS,
    UNARY_SYMBOLS,
    OpcodeSpec,
    VMModel,
    VOp,
)

# Each is a tuple whose first element tags the kind, so they compare cheaply.

POP = "pop"            # ("pop", ordinal)
CONST = "const"        # ("const",)   -> consts[operand]
NAME = "name"          # ("name",)    -> names[operand]
LOCAL = "local"        # ("local", key)
GLOBAL = "global"      # ("global", key)
OPERAND = "operand"    # ("operand", index)
BINOP = "binop"        # ("binop", symbol, left, right)
UNOP = "unop"          # ("unop", symbol, value)
CALLV = "call"         # ("call", func, argspec)
IMPORTV = "import"     # ("import", arg)
VMV = "vm"             # ("vm", arg)
ATTR = "attr"          # ("attr", obj, name)
TUPLEV = "tuple"       # ("tuple", countexpr)
LISTV = "list"         # ("list", countexpr)
SLICEV = "slice"       # ("slice",)
SUBV = "sub"           # ("sub", obj, index)
COLLECT = "collect"    # ("collect",) -> list built by popping `operand` times
OTHER = "other"

class _HandlerState:
    """Abstract machine state while walking one handler body."""

    def __init__(self, names: "VMNames"):
        self.names = names
        self.env: Dict[str, tuple] = {}
        self.pops = 0
        self.pushes: List[tuple] = []
        self.stores: List[Tuple[str, tuple]] = []   # (scope, value)
        self.returns: List[tuple] = []
        self.pc_writes: List[tuple] = []
        self.conditional_pc = False
        self.negated_condition = False
        self.compare_table: Dict[int, str] = {}
        self.collects = 0

    def fresh_pop(self) -> tuple:
        value = (POP, self.pops)
        self.pops += 1
        return value

class VMNames:
    """Identifier bindings recovered from the interpreter loop's prologue."""

    def __init__(self):
        self.stack: Optional[str] = None
        self.push: Optional[str] = None
        self.pop: Optional[str] = None
        self.pc: Optional[str] = None
        self.bytecode: Optional[str] = None
        self.consts: Optional[str] = None
        self.names: Optional[str] = None
        self.locals: Optional[str] = None
        self.globals: Optional[str] = None
        self.opcode_var: Optional[str] = None
        self.operand_vars: List[str] = []
        self.vm_class: Optional[str] = None

def _attr_chain(node) -> Optional[str]:
    """``self.bytecode`` -> 'bytecode'; a bare name -> the name."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None

class HandlerInterpreter:
    """Walks one handler body and records its effect on VM state."""

    def __init__(self, names: VMNames):
        self.n = names

    def run(self, body: List[ast.stmt]) -> _HandlerState:
        state = _HandlerState(self.n)
        self._block(body, state)
        return state

    def _block(self, body, state):
        for stmt in body:
            self._stmt(stmt, state)

    def _stmt(self, node, state):
        if isinstance(node, ast.Assign):
            value = self._expr(node.value, state)
            for target in node.targets:
                self._assign(target, value, state)
        elif isinstance(node, ast.AugAssign):
            symbol = BINARY_SYMBOLS.get(type(node.op).__name__)
            current = self._expr(node.target, state)
            operand = self._expr(node.value, state)
            self._assign(node.target, (BINOP, symbol, current, operand), state)
        elif isinstance(node, ast.Expr):
            self._expr(node.value, state)
        elif isinstance(node, ast.Return):
            state.returns.append(
                self._expr(node.value, state) if node.value is not None else (OTHER,)
            )
        elif isinstance(node, ast.If):
            # `if not pop(): pc = target` — the branch condition consumes a slot.
            before = state.pops
            test = self._expr(node.test, state)
            if state.pops > before or self._mentions_pop(test):
                state.conditional_pc = True
                state.negated_condition = self._is_negated(node.test)
            self._block(node.body, state)
            self._block(node.orelse, state)
        elif isinstance(node, ast.For):
            # `for _ in range(operand): values.insert(0, pop())`
            if self._is_operand_range(node.iter, state):
                state.collects += 1
                self._block(node.body, _CollectSink(state))
            else:
                self._block(node.body, state)
        elif isinstance(node, ast.While):
            self._block(node.body, state)
        elif isinstance(node, ast.Match):
            self._match(node, state)
        elif isinstance(node, (ast.Continue, ast.Break, ast.Pass)):
            pass

    def _match(self, node, state):
        """A nested match on the operand selects a comparison/operator variant."""
        subject = self._expr(node.subject, state)
        if subject[0] != OPERAND:
            for case in node.cases:
                self._block(case.body, state)
            return
        for case in node.cases:
            pattern = case.pattern
            if not (isinstance(pattern, ast.MatchValue)
                    and isinstance(pattern.value, ast.Constant)
                    and isinstance(pattern.value.value, int)):
                continue
            sub = _HandlerState(self.n)
            sub.env = dict(state.env)
            sub.pops = state.pops
            self._block(case.body, sub)
            symbol = None
            for pushed in sub.pushes:
                if pushed[0] in (BINOP, UNOP):
                    symbol = pushed[1]
                    break
            if symbol:
                state.compare_table[pattern.value.value] = symbol

    def _assign(self, target, value, state):
        if isinstance(target, ast.Name):
            if self.n.pc and target.id == self.n.pc:
                state.pc_writes.append(value)
            else:
                state.env[target.id] = value
            return
        if isinstance(target, ast.Subscript):
            scope = self._scope_of(target.value)
            if scope:
                state.stores.append((scope, value))
                return
            state.env.setdefault("_sub", value)
            return
        if isinstance(target, ast.Attribute):
            state.env[target.attr] = value

    def _scope_of(self, node) -> Optional[str]:
        name = _attr_chain(node)
        if name is None:
            return None
        if self.n.locals and name == self.n.locals:
            return "local"
        if self.n.globals and name == self.n.globals:
            return "global"
        return None

    def _expr(self, node, state) -> tuple:
        if node is None:
            return (OTHER,)

        if isinstance(node, ast.Call):
            return self._call(node, state)

        if isinstance(node, ast.Name):
            if node.id in state.env:
                return state.env[node.id]
            if node.id in self.n.operand_vars:
                return (OPERAND, self.n.operand_vars.index(node.id))
            if self.n.vm_class and node.id == self.n.vm_class:
                return (OTHER,)
            return (OTHER,)

        if isinstance(node, ast.Attribute):
            name = node.attr
            if name in state.env:
                return state.env[name]
            if self.n.consts and name == self.n.consts:
                return (CONST,)
            if self.n.names and name == self.n.names:
                return (NAME,)
            return (ATTR, self._expr(node.value, state), name)

        if isinstance(node, ast.Subscript):
            base = self._expr(node.value, state)
            index = self._expr(node.slice, state)
            if base[0] == CONST:
                return (CONST,)
            if base[0] == NAME:
                return (NAME,)
            scope = self._scope_of(node.value)
            if scope == "local":
                return (LOCAL, index)
            if scope == "global":
                return (GLOBAL, index)
            return (SUBV, base, index)

        if isinstance(node, ast.BinOp):
            symbol = BINARY_SYMBOLS.get(type(node.op).__name__)
            return (BINOP, symbol,
                    self._expr(node.left, state), self._expr(node.right, state))

        if isinstance(node, ast.UnaryOp):
            symbol = UNARY_SYMBOLS.get(type(node.op).__name__)
            return (UNOP, symbol, self._expr(node.operand, state))

        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            symbol = COMPARE_SYMBOLS.get(type(node.ops[0]).__name__)
            return (BINOP, symbol,
                    self._expr(node.left, state),
                    self._expr(node.comparators[0], state))

        if isinstance(node, ast.BoolOp):
            symbol = "and" if isinstance(node.op, ast.And) else "or"
            values = [self._expr(v, state) for v in node.values]
            result = values[0]
            for nxt in values[1:]:
                result = (BINOP, symbol, result, nxt)
            return result

        if isinstance(node, ast.Constant):
            return (OTHER,)

        if isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self._expr(elt, state)
            return (OTHER,)

        return (OTHER,)

    def _call(self, node, state) -> tuple:
        func = node.func
        fname = _attr_chain(func)

        # stack.pop() / pop()
        if fname == self.n.pop or (
            isinstance(func, ast.Attribute) and func.attr == "pop"
            and _attr_chain(func.value) == self.n.stack
        ):
            return state.fresh_pop()

        # push(x) / stack.append(x)
        if fname == self.n.push or (
            isinstance(func, ast.Attribute) and func.attr == "append"
            and _attr_chain(func.value) == self.n.stack
        ):
            if node.args:
                state.pushes.append(self._expr(node.args[0], state))
            return (OTHER,)

        # values.insert(0, pop()) inside a collect loop
        if isinstance(func, ast.Attribute) and func.attr in ("insert", "append"):
            for arg in node.args:
                self._expr(arg, state)
            return (OTHER,)

        if isinstance(func, ast.Name):
            if func.id == "__import__":
                arg = self._expr(node.args[0], state) if node.args else (OTHER,)
                return (IMPORTV, arg)
            if self.n.vm_class and func.id == self.n.vm_class:
                arg = self._expr(node.args[0], state) if node.args else (OTHER,)
                return (VMV, arg)
            if func.id == "getattr":
                obj = self._expr(node.args[0], state) if node.args else (OTHER,)
                attr = self._expr(node.args[1], state) if len(node.args) > 1 else (OTHER,)
                return (ATTR, obj, attr)
            if func.id == "tuple":
                inner = self._expr(node.args[0], state) if node.args else (OTHER,)
                return (TUPLEV, inner)
            if func.id == "list":
                inner = self._expr(node.args[0], state) if node.args else (OTHER,)
                return (LISTV, inner)
            if func.id == "slice":
                for arg in node.args:
                    self._expr(arg, state)
                return (SLICEV,)
            if func.id == "range":
                for arg in node.args:
                    self._expr(arg, state)
                return (OTHER,)

        # generic call: `function(*args)` — the callee itself came off the stack
        callee = self._expr(func, state)
        starred = any(isinstance(a, ast.Starred) for a in node.args)
        for arg in node.args:
            self._expr(arg.value if isinstance(arg, ast.Starred) else arg, state)
        return (CALLV, callee, "star" if starred else str(len(node.args)))

    def _is_operand_range(self, node, state) -> bool:
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "range"
                and node.args):
            return False
        return self._expr(node.args[0], state)[0] == OPERAND

    def _is_negated(self, node) -> bool:
        return isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)

    def _mentions_pop(self, value) -> bool:
        if not isinstance(value, tuple):
            return False
        if value and value[0] == POP:
            return True
        return any(self._mentions_pop(v) for v in value if isinstance(v, tuple))

class _CollectSink(_HandlerState):
    """Proxy that counts pops performed inside an operand-controlled loop."""

    def __init__(self, parent: _HandlerState):
        self.__dict__ = parent.__dict__

def classify(state: _HandlerState, number: int, source: str) -> OpcodeSpec:
    """Turn an interpreted handler effect into an :class:`OpcodeSpec`."""
    spec = OpcodeSpec(number=number, source=source)

    # Control flow first: a write to the program counter dominates everything.
    if state.pc_writes:
        target_is_operand = any(v[0] == OPERAND for v in state.pc_writes)
        spec.operand_role = "target" if target_is_operand else "none"
        if state.conditional_pc:
            spec.op = VOp.JUMP_IF_FALSE if state.negated_condition else VOp.JUMP_IF_TRUE
        else:
            spec.op = VOp.JUMP
        return spec

    if state.returns:
        spec.op = VOp.RETURN
        return spec

    if state.compare_table:
        spec.op = VOp.COMPARE
        spec.operand_role = "selector"
        spec.compare_table = dict(state.compare_table)
        return spec

    # Stores land in a scope dict keyed by the name pool.
    if state.stores:
        scope, value = state.stores[-1]
        if value[0] == VMV:
            spec.op = VOp.MAKE_VM
            spec.operand_role = "name"
            return spec
        if value[0] == IMPORTV:
            spec.op = VOp.IMPORT
            spec.operand_role = "name"
            return spec
        spec.op = VOp.STORE_LOCAL if scope == "local" else VOp.STORE_GLOBAL
        spec.operand_role = "name"
        return spec

    if not state.pushes:
        spec.op = VOp.NOP
        return spec

    pushed = state.pushes[-1]
    kind = pushed[0]

    if kind == CONST:
        spec.op = VOp.LOAD_CONST
        spec.operand_role = "const"
        return spec

    if kind == LOCAL:
        spec.op = VOp.LOAD_LOCAL
        spec.operand_role = "name"
        return spec

    if kind == GLOBAL:
        spec.op = VOp.LOAD_GLOBAL
        spec.operand_role = "name"
        return spec

    if kind == CALLV:
        spec.op = VOp.CALL
        spec.operand_role = "count" if state.collects else "none"
        return spec

    if kind == ATTR:
        spec.op = VOp.LOAD_ATTR
        return spec

    if kind == TUPLEV:
        spec.op = VOp.BUILD_TUPLE
        spec.operand_role = "count"
        return spec

    if kind == SLICEV:
        spec.op = VOp.BUILD_SLICE
        return spec

    if kind == SUBV:
        spec.op = VOp.SUBSCRIPT
        return spec

    if kind == BINOP:
        symbol = pushed[1]
        if symbol in ("and", "or"):
            spec.op = VOp.BOOL
        elif symbol in COMPARE_SYMBOLS.values():
            spec.op = VOp.COMPARE
        else:
            spec.op = VOp.BINARY
        spec.symbol = symbol
        return spec

    if kind == UNOP:
        spec.op = VOp.UNARY
        spec.symbol = pushed[1]
        return spec

    # A push of a value assembled by an operand-controlled pop loop is a list
    # build; `tuple(...)` already matched above, so the bare form is a list.
    if state.collects:
        spec.op = VOp.BUILD_LIST
        spec.operand_role = "count"
        return spec

    if kind == POP:
        spec.op = VOp.NOP
        return spec

    spec.op = VOp.UNKNOWN
    return spec
