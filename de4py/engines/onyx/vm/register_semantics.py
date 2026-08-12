# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Semantics for register-machine handlers.

A table-dispatch VM hands each opcode a lambda over the instruction's operands,
so a handler is one expression rather than a statement body. Everything it does
is therefore encoded in expression idioms, and this module reads them back:

* ``[None for regs[a] in [value]]`` — a comprehension used as an assignment,
  because a lambda cannot contain a statement.
* ``bool(x := ...) & bool(...)`` — sequencing, because a lambda cannot contain
  two statements either. Each conjunct is one step, left to right.
* ``self.decode(regs[a]) or self.field`` — a call whose result is read back off
  an attribute. What such a wrapper *means* is decided by what it is given: a
  register read is a value fetch, a bare operand is a pool lookup. That rule
  comes from the argument's shape, so it survives any renaming of the methods.

Classification therefore depends on handler structure, never on identifiers,
which is what lets the same code lift a VM whose every name is generated.
"""

import ast
from typing import Any, Dict, List, Optional, Tuple

from de4py.engines.onyx.vm.ir import (
    BINARY_SYMBOLS,
    COMPARE_SYMBOLS,
    UNARY_SYMBOLS,
    OpcodeSpec,
    VOp,
)

REG = "reg"          # ("reg", index)      -> the register file at an index
OPERAND = "operand"  # ("operand", i)      -> raw instruction operand i
POOL = "pool"        # ("pool", i)         -> a pool entry named by operand i
SCOPE = "scope"      # ("scope", key, expr)-> a namespace dict lookup
BINOP = "binop"      # ("binop", symbol, left, right)
UNOP = "unop"        # ("unop", symbol, value)
CALLV = "call"       # ("call", callee, args)
IMPORTV = "import"   # ("import", arg)
VMV = "vm"           # ("vm", arg)
SUBV = "sub"         # ("sub", obj, index)
ATTRV = "attrv"      # ("attrv", obj, name)
CMPTABLE = "cmptable"  # ("cmptable", selector, left, right)
FIELD = "field"        # ("field", name) -> interpreter state, not a register
SLICEV = "slice"     # ("slice", parts)
SEQV = "seq"         # ("seq", kind, source)
DICTV = "dict"       # ("dict",)
CONSTV = "const"     # ("const", value)
OTHER = "other"

class RegisterState:
    """What one handler does, recorded as it is interpreted."""

    def __init__(self) -> None:
        self.env: Dict[str, tuple] = {}
        self.stores: List[Tuple[tuple, tuple]] = []     # (destination, value)
        self.pc_writes: List[tuple] = []
        self.returns: List[tuple] = []
        self.conditional: Optional[tuple] = None
        self.negated = False
        self.reads: List[tuple] = []
        #: Operand value -> comparison operator, when one opcode covers them all.
        self.compare_table: Dict[int, str] = {}
        #: Interpreter fields a comparison read, when it compared no register.
        self.compare_sources: Tuple[Optional[str], Optional[str]] = (None, None)
        #: Handler-local name -> the interpreter field it was read from.
        self.origins: Dict[str, str] = {}

class RegisterHandlerInterpreter:
    """Interprets one handler lambda over the symbolic domain above."""

    def __init__(self, params: Tuple[str, ...], register_key: str,
                 scope_keys: Tuple[str, ...] = (),
                 pc_carrier: Optional[str] = None):
        self.params = params
        self.register_key = register_key
        self.scope_keys = scope_keys
        self.pc_carrier = pc_carrier

    def run(self, handler: ast.Lambda) -> RegisterState:
        state = RegisterState()
        self._effect(handler.body, state)
        return state

    def _effect(self, node: ast.expr, state: RegisterState) -> tuple:
        """Interpret an expression evaluated for effect rather than for value."""
        # `bool(a) & bool(b)` sequences two steps; the operator is irrelevant.
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            self._effect(node.left, state)
            return self._effect(node.right, state)

        if isinstance(node, ast.BoolOp):
            result = (OTHER,)
            for value in node.values:
                result = self._effect(value, state)
            return result

        # `bool(x)` / `list(x)` wrappers exist only to make the conjunction legal.
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ("bool", "list", "tuple", "any", "all")
                and len(node.args) == 1):
            return self._effect(node.args[0], state)

        if isinstance(node, ast.NamedExpr):
            value = self._value(node.value, state)
            if isinstance(node.target, ast.Name):
                state.env[node.target.id] = value
            return value

        # `[None for <target> in [<value>]]` is an assignment in disguise.
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            assigned = self._comprehension_assignment(node, state)
            if assigned:
                return assigned

        # `<effect> if <cond> else None` is a guarded step.
        if isinstance(node, ast.IfExp):
            return self._guarded(node, state)

        if isinstance(node, ast.Call):
            return self._call(node, state, for_effect=True)

        return self._value(node, state)

    def _comprehension_assignment(self, node, state: RegisterState) -> Optional[tuple]:
        """
        Read ``[None for TARGET in [VALUE]]`` as ``TARGET = VALUE``.

        The iterable must be a one-element sequence: that is what makes the
        comprehension run exactly once and leave the binding behind.
        """
        if len(node.generators) != 1:
            return None
        gen = node.generators[0]
        if gen.ifs or gen.is_async:
            return None
        source = gen.iter
        if not (isinstance(source, (ast.List, ast.Tuple)) and len(source.elts) == 1):
            return None

        value = self._value(source.elts[0], state)
        target = gen.target

        if isinstance(target, ast.Name):
            state.env[target.id] = value
            return value

        destination = self._destination(target, state)
        if destination is None:
            return None
        if destination[0] == "pc":
            state.pc_writes.append(value)
        else:
            state.stores.append((destination, value))
        return value

    def _destination(self, target: ast.expr, state: RegisterState) -> Optional[tuple]:
        """Classify what an assignment writes to."""
        if isinstance(target, ast.Subscript):
            base = ast.unparse(target.value)
            index = self._value(target.slice, state)
            if base == self.register_key:
                return (REG, index)
            return (SCOPE, base, index)
        if isinstance(target, ast.Attribute):
            if self.pc_carrier is not None and target.attr == self.pc_carrier:
                return ("pc",)
            return ("attr", target.attr)
        return None

    def _guarded(self, node: ast.IfExp, state: RegisterState) -> tuple:
        """``<step> if <cond> else None`` — a conditional effect, i.e. a branch."""
        test = node.test
        negated = isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not)
        condition = self._value(test.operand if isinstance(test, ast.UnaryOp) and negated
                                else test, state)

        before = len(state.pc_writes)
        taken = state.env.copy()
        self._effect(node.body, state)
        if isinstance(node.orelse, ast.Constant) and node.orelse.value is None:
            pass
        else:
            state.env = taken
            self._effect(node.orelse, state)

        if len(state.pc_writes) > before:
            state.conditional = condition
            state.negated = negated
        return (OTHER,)

    def _value(self, node: Optional[ast.expr], state: RegisterState) -> tuple:
        if node is None:
            return (OTHER,)

        if isinstance(node, ast.NamedExpr):
            value = self._value(node.value, state)
            if isinstance(node.target, ast.Name):
                state.env[node.target.id] = value
                origin = _attribute_name(node.value)
                if origin is not None:
                    state.origins[node.target.id] = origin
            return value

        if isinstance(node, ast.Name):
            if node.id in state.env:
                return state.env[node.id]
            if node.id in self.params:
                return (OPERAND, self.params.index(node.id))
            return (OTHER,)

        if isinstance(node, ast.Constant):
            return (CONSTV, node.value)

        if isinstance(node, ast.Subscript):
            table = self._comparison_table(node, state)
            if table is not None:
                return table
            return self._subscript(node, state)

        if isinstance(node, ast.BinOp):
            symbol = BINARY_SYMBOLS.get(type(node.op).__name__)
            return (BINOP, symbol,
                    self._value(node.left, state), self._value(node.right, state))

        if isinstance(node, ast.UnaryOp):
            symbol = UNARY_SYMBOLS.get(type(node.op).__name__)
            return (UNOP, symbol, self._value(node.operand, state))

        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            symbol = COMPARE_SYMBOLS.get(type(node.ops[0]).__name__)
            return (BINOP, symbol, self._value(node.left, state),
                    self._value(node.comparators[0], state))

        if isinstance(node, ast.BoolOp):
            # `self.decode(x) or self.result` reads the result back off a field;
            # the left operand is what actually names the source.
            values = [self._value(v, state) for v in node.values]
            for value in values:
                if value[0] != OTHER:
                    return value
            return values[0] if values else (OTHER,)

        if isinstance(node, ast.Call):
            return self._call(node, state, for_effect=False)

        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return (SEQV, type(node).__name__.lower(),
                    tuple(self._value(e, state) for e in node.elts))

        if isinstance(node, ast.Dict):
            return (DICTV,)

        if isinstance(node, ast.ListComp):
            # `[decode(r) for r in regs[a:b]]` gathers a register range.
            return self._value(node.generators[0].iter, state) if node.generators \
                else (OTHER,)

        if isinstance(node, ast.Slice):
            return (SLICEV, (self._value(node.lower, state),
                             self._value(node.upper, state),
                             self._value(node.step, state)))

        if isinstance(node, ast.IfExp):
            # A value-position conditional picks between two spellings of the
            # same recovery (``getattr(x, n) if hasattr(x, n) else import(...)``),
            # so either branch describes the instruction.
            body = self._value(node.body, state)
            return body if body[0] != OTHER else self._value(node.orelse, state)

        if isinstance(node, ast.Attribute):
            # Keep the field name: a comparison against interpreter state has no
            # register operand, so this is the only thing that can name it.
            field = _attribute_name(node)
            return (FIELD, field) if field else (OTHER,)

        return (OTHER,)

    def _comparison_table(self, node: ast.Subscript,
                          state: RegisterState) -> Optional[tuple]:
        """
        Recognise ``[a == b, a != b, a < b, ...][sel]`` as one COMPARE opcode.

        A single opcode covers every comparison by indexing a list of them with
        its operand. Read literally that is a subscript, which loses the whole
        comparison family; recovering the list position -> operator mapping is
        what turns the operand into a real ``<`` or ``==``.
        """
        base = node.value
        if not isinstance(base, (ast.List, ast.Tuple)) or len(base.elts) < 2:
            return None

        table: Dict[int, str] = {}
        for position, element in enumerate(base.elts):
            comparison = element
            # `a in b if isinstance(b, Iterable) else None` guards a variant.
            if isinstance(comparison, ast.IfExp):
                comparison = comparison.body
            if not (isinstance(comparison, ast.Compare)
                    and len(comparison.ops) == 1):
                return None
            symbol = COMPARE_SYMBOLS.get(type(comparison.ops[0]).__name__)
            if symbol is None:
                return None
            table[position] = symbol

        if len(set(table.values())) < 2:
            return None

        first = base.elts[0]
        if isinstance(first, ast.IfExp):
            first = first.body
        if not isinstance(first, ast.Compare):
            return None

        selector = self._value(node.slice, state)
        left = self._value(first.left, state)
        right = self._value(first.comparators[0], state)
        state.compare_table = table
        # A comparison of interpreter fields names no register, so record where
        # the values came from; without it the branch reads an undefined slot.
        state.compare_sources = (
            self._origin(first.left, state), self._origin(first.comparators[0], state)
        )
        return (CMPTABLE, selector, left, right)

    def _origin(self, node: ast.expr, state: RegisterState) -> Optional[str]:
        """
        Interpreter field a handler-local value was read from, if any.

        A comparison's operands are usually walrus targets bound earlier in the
        same handler, so the local name is resolved back to the field it read.
        """
        if isinstance(node, ast.Name):
            recorded = state.origins.get(node.id)
            if recorded is not None:
                return recorded
            bound = state.env.get(node.id)
            return _field_of(bound)
        return _attribute_name(node)

    def _subscript(self, node: ast.Subscript, state: RegisterState) -> tuple:
        base = ast.unparse(node.value)
        index = self._value(node.slice, state)
        if base == self.register_key:
            if isinstance(node.slice, ast.Slice):
                return (SEQV, "regrange",
                        (self._value(node.slice.lower, state),
                         self._value(node.slice.upper, state)))
            state.reads.append(index)
            return (REG, index)
        if base in self.scope_keys:
            return (SCOPE, base, index)
        return (SUBV, self._value(node.value, state), index)

    def _call(self, node: ast.Call, state: RegisterState, for_effect: bool) -> tuple:
        func = node.func

        # `gen.throw(Exc(value))` is how a lambda raises: the VM returns.
        if isinstance(func, ast.Attribute) and func.attr == "throw":
            payload: tuple = self._value(node.args[0], state) if node.args else (OTHER,)
            if payload[0] in (CALLV, VMV) and len(payload) > 2:
                inner = payload[2]
                if isinstance(inner, tuple) and inner and isinstance(inner[0], tuple):
                    payload = inner[0]
            state.returns.append(payload)
            return (OTHER,)

        if isinstance(func, ast.Name):
            if func.id == "import_module" or func.id == "__import__":
                return (IMPORTV, self._value(node.args[0], state) if node.args
                        else (OTHER,))
            if func.id == "getattr" and len(node.args) >= 2:
                return (ATTRV, self._value(node.args[0], state),
                        self._value(node.args[1], state))
            if func.id == "hasattr" and len(node.args) >= 2:
                return (ATTRV, self._value(node.args[0], state),
                        self._value(node.args[1], state))
            if func.id in ("slice",):
                return (SLICEV, tuple(
                    self._value(a.value if isinstance(a, ast.Starred) else a, state)
                    for a in node.args))
            if func.id in ("dict",):
                return (DICTV,)
            if func.id in ("list", "tuple", "set"):
                inner = self._value(node.args[0], state) if node.args else (OTHER,)
                return (SEQV, func.id, inner)
            if func.id == "bool" and len(node.args) == 1:
                return self._value(node.args[0], state)

        # A single-argument method on ``self`` is a transparent codec: what it
        # means is decided by what it is handed, not by what it is called.
        if (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                and func.value.id == "self" and len(node.args) == 1):
            inner = self._value(node.args[0], state)
            if inner[0] == OPERAND:
                return (POOL, inner[1])
            return inner

        callee = self._value(func, state)
        args: List[tuple] = []
        for arg in node.args:
            args.append(self._value(arg.value if isinstance(arg, ast.Starred) else arg,
                                    state))
        if callee[0] == OTHER and isinstance(func, ast.Name):
            # A class instantiated from a payload table builds a nested program.
            return (VMV, args[0] if args else (OTHER,))
        return (CALLV, callee, tuple(args))

def _field_of(value: Any) -> Optional[str]:
    """Interpreter field a symbolic value was ultimately read from."""
    if not isinstance(value, tuple) or not value:
        return None
    if value[0] == FIELD and len(value) > 1 and isinstance(value[1], str):
        return value[1]
    for item in value:
        if isinstance(item, tuple):
            found = _field_of(item)
            if found is not None:
                return found
    return None

def _attribute_name(node: ast.AST) -> Optional[str]:
    """``self.field`` -> 'field', so a compared value can be named."""
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "self"):
        return node.attr
    if isinstance(node, ast.Call) and node.args:
        return _attribute_name(node.args[0])
    if isinstance(node, ast.BoolOp) and node.values:
        return _attribute_name(node.values[0])
    return None

def _operand_index(value: Any) -> Optional[int]:
    """Index of the operand a symbolic value is addressed by, if any."""
    if not isinstance(value, tuple) or not value:
        return None
    if value[0] == OPERAND and len(value) > 1:
        return value[1] if isinstance(value[1], int) else None
    if value[0] == POOL and len(value) > 1:
        return value[1] if isinstance(value[1], int) else None
    if value[0] == REG and len(value) > 1:
        return _operand_index(value[1])
    # A scope store is keyed by a decoded operand: ("scope", base, key).
    if value[0] == SCOPE and len(value) > 2:
        return _operand_index(value[2])
    return None

def _mentions(value: Any, kind: str) -> bool:
    if not isinstance(value, tuple) or not value:
        return False
    if value[0] == kind:
        return True
    return any(_mentions(v, kind) for v in value if isinstance(v, tuple))

def _roles(destination: Optional[tuple], value: tuple, arity: int) -> Tuple[str, ...]:
    """
    Name each operand position by the job it does in this handler.

    A store addressed through the *pool* rather than the register file names its
    target, so that operand is a name index and not a register — recording it as
    ``dest`` would emit an anonymous binding.
    """
    roles = ["none"] * arity
    if destination is not None:
        index = _operand_index(destination)
        if index is not None and index < arity:
            roles[index] = "dest" if destination[0] == REG else "name"

    # `regs[a : b + 1]` gathers a run of registers, so the second operand bounds
    # a range rather than naming one source.
    end = _range_end(value)
    if end is not None and end < arity and roles[end] == "none":
        roles[end] = "range_end"

    # An operand fed through a pool decoder indexes the name pool, not the
    # register file; reading it as a register would print the wrong operand.
    for position in _pool_operands(value):
        if position < arity and roles[position] == "none":
            roles[position] = "name"

    for position in range(arity):
        if roles[position] != "none":
            continue
        if _addresses(value, position):
            roles[position] = "src"
    return tuple(roles)

def _pool_operands(value: Any) -> List[int]:
    """Operand positions the handler resolves through a pool decoder."""
    found: List[int] = []
    if not isinstance(value, tuple) or not value:
        return found
    if value[0] == POOL and len(value) > 1 and isinstance(value[1], int):
        found.append(value[1])
    for item in value:
        if isinstance(item, tuple):
            found.extend(_pool_operands(item))
    return found

def _fixed_register(destination: Any) -> Optional[int]:
    """Register index a handler always writes, when it is a literal."""
    if (isinstance(destination, tuple) and len(destination) > 1
            and destination[0] == REG):
        index = destination[1]
        if (isinstance(index, tuple) and len(index) > 1 and index[0] == CONSTV
                and isinstance(index[1], int) and not isinstance(index[1], bool)):
            return index[1]
    return None

def _operand_in(value: Any) -> Optional[int]:
    """First operand mentioned anywhere in a bound expression, e.g. ``b + 1``."""
    direct = _operand_index(value)
    if direct is not None:
        return direct
    if isinstance(value, tuple):
        for item in value:
            found = _operand_in(item)
            if found is not None:
                return found
    return None

def _range_end(value: Any) -> Optional[int]:
    """Operand index bounding a register range, when the handler reads one."""
    if not isinstance(value, tuple) or not value:
        return None
    if value[0] == SEQV and len(value) > 2 and value[1] == "regrange":
        bounds = value[2]
        if isinstance(bounds, tuple) and len(bounds) > 1:
            # `regs[a : b + 1]` — the upper bound names the operand, though it
            # is usually written as an offset from it.
            return _operand_in(bounds[1])
        return _operand_in(bounds)
    for item in value:
        if isinstance(item, tuple):
            found = _range_end(item)
            if found is not None:
                return found
    return None

def _addresses(value: Any, operand: int) -> bool:
    if not isinstance(value, tuple) or not value:
        return False
    if value[0] == OPERAND and value[1] == operand:
        return True
    if value[0] == POOL and value[1] == operand:
        return True
    return any(_addresses(v, operand) for v in value if isinstance(v, tuple))

def classify_register_handler(state: RegisterState, number: int, source: str,
                              arity: int = 2) -> OpcodeSpec:
    """Turn an interpreted register handler into an :class:`OpcodeSpec`."""
    spec = OpcodeSpec(number=number, source=source[:200])

    if state.pc_writes:
        target = state.pc_writes[-1]
        scale, index = _jump_target(target)
        spec.target_scale = scale or 1
        roles = ["none"] * arity
        if index is not None and index < arity:
            roles[index] = "target"
        if state.conditional is not None:
            source_index = _operand_index(state.conditional)
            if source_index is not None and source_index < arity \
                    and roles[source_index] == "none":
                roles[source_index] = "src"
            spec.op = VOp.JUMP_IF_FALSE if state.negated else VOp.JUMP_IF_TRUE
        else:
            spec.op = VOp.JUMP
        spec.operand_roles = tuple(roles)
        spec.operand_role = "target"
        return spec

    if state.returns:
        spec.op = VOp.RETURN
        spec.operand_roles = _roles(None, state.returns[-1], arity)
        return spec

    if not state.stores:
        spec.op = VOp.NOP
        return spec

    destination, value = state.stores[-1]

    # A handler may write interpreter fields rather than the register file —
    # scratch state the program can read back later. It stores, but it has no
    # destination register, so it must not be rendered as an assignment to one.
    if destination[0] == "attr":
        spec.op = VOp.STORE_LOCAL
        spec.operand_roles = _roles(None, value, arity)
        spec.symbol = destination[1] if len(destination) > 1 else None
        return spec

    spec.operand_roles = _roles(destination, value, arity)
    spec.fixed_dest = _fixed_register(destination)

    if destination[0] == SCOPE:
        spec.op = VOp.STORE_GLOBAL
        spec.operand_role = "name"
        return spec

    kind = value[0]

    if kind == VMV:
        spec.op = VOp.MAKE_VM
        spec.operand_role = "name"
        return spec
    if kind == IMPORTV:
        spec.op = VOp.IMPORT
        spec.operand_role = "name"
        return spec
    if kind == SCOPE:
        spec.op = VOp.LOAD_GLOBAL
        spec.operand_role = "name"
        return spec
    if kind == POOL:
        spec.op = VOp.LOAD_CONST
        spec.operand_role = "const"
        return spec
    if kind == CALLV:
        spec.op = VOp.CALL
        return spec
    if kind == SLICEV:
        spec.op = VOp.BUILD_SLICE
        return spec
    if kind == DICTV:
        spec.op = VOp.BUILD_DICT
        return spec
    if kind == SEQV:
        spec.op = VOp.BUILD_LIST
        return spec
    if kind == CMPTABLE:
        spec.op = VOp.COMPARE
        spec.compare_table = dict(state.compare_table)
        spec.compare_sources = state.compare_sources
        # One operand picks which comparison runs; the values compared come from
        # wherever the handler read them, which may be a register or a field.
        roles = list(spec.operand_roles)
        selector = _operand_index(value[1] if len(value) > 1 else None)
        if selector is not None and selector < len(roles):
            roles[selector] = "selector"
        for position, operand in enumerate((value[2] if len(value) > 2 else None,
                                            value[3] if len(value) > 3 else None)):
            index = _operand_index(operand)
            if index is not None and index < len(roles) and roles[index] == "none":
                roles[index] = "dest" if position == 0 else "src"
        spec.operand_roles = tuple(roles)
        spec.operand_role = "selector"
        return spec

    if kind == SUBV:
        # `regs[a][regs[b]]` indexes a value the program computed, whereas
        # `scope[name]` looks a binding up by a decoded name. The base tells
        # them apart: a namespace read is never keyed by a register.
        base = value[1] if len(value) > 1 else (OTHER,)
        key = value[2] if len(value) > 2 else (OTHER,)
        if isinstance(base, tuple) and base and base[0] == REG:
            spec.op = VOp.SUBSCRIPT
            return spec
        if isinstance(key, tuple) and key and key[0] == POOL:
            spec.op = VOp.LOAD_GLOBAL
            spec.operand_role = "name"
            return spec
        spec.op = VOp.SUBSCRIPT
        return spec
    if kind == ATTRV:
        spec.op = VOp.LOAD_ATTR
        spec.operand_role = "name"
        return spec
    if kind == BINOP:
        symbol = value[1]
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
        spec.symbol = value[1]
        return spec
    if kind == REG:
        spec.op = VOp.MOVE
        return spec
    if kind == OPERAND or kind == CONSTV:
        spec.op = VOp.LOAD_IMM
        spec.operand_role = "immediate"
        return spec

    spec.op = VOp.UNKNOWN
    return spec

def _jump_target(value: Any) -> Tuple[Optional[int], Optional[int]]:
    """
    Split a pc write into (scale, operand index).

    Targets are commonly stored as an instruction index and multiplied up to a
    byte offset inside the handler, so the factor is read off that multiply
    rather than assumed to equal the instruction width.
    """
    if not isinstance(value, tuple) or not value:
        return None, None
    if value[0] == SEQV and len(value) > 2:
        parts = value[2]
        if isinstance(parts, tuple) and len(parts) == 1 and isinstance(parts[0], tuple):
            return _jump_target(parts[0])
    if value[0] == BINOP and len(value) > 3 and value[1] == "*":
        left, right = value[2], value[3]
        for a, b in ((left, right), (right, left)):
            if (isinstance(b, tuple) and len(b) > 1 and b[0] == CONSTV
                    and isinstance(b[1], int) and not isinstance(b[1], bool)):
                return b[1], _operand_index(a)
    return None, _operand_index(value)
