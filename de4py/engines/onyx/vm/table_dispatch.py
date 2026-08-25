# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Table-dispatch VM discovery.

Some interpreters do not branch on the opcode at all: they index a tuple of
handler lambdas with it, so there is no ``match`` and no ``if`` chain for
:mod:`de4py.engines.onyx.vm.discovery` to find. The opcode's meaning is its
*position* in that table.

Two properties make such a VM harder than a switch dispatcher, and both are
recovered here rather than assumed:

* **The table is rotated before use.** A sample may evaluate
  ``table = table[-(-1 % n):] + table[:-(-1 % n)]`` where ``n`` is an instance
  field, which shifts every opcode number. The rotation expression is
  interpreted with the bounded evaluator over the fields the constructor binds,
  so the shift comes from the sample's own arithmetic.
* **Registers, not a stack.** Handlers read and write ``regs[a]`` / ``regs[b]``
  directly, so operands carry roles (destination, source) instead of positions.

Nothing here executes sample code: the table is located by parsing, and every
number is produced by :mod:`de4py.engines.onyx.safe_eval`.
"""

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from de4py.engines.onyx.safe_eval import safe_eval
from de4py.engines.onyx.vm.ir import VMModel
from de4py.engines.onyx.vm.register_semantics import (
    RegisterHandlerInterpreter,
    classify_register_handler,
)

#: A handler table smaller than this is more likely a tuple of callbacks than an
#: opcode table.
MIN_TABLE_HANDLERS = 6

#: Guards against pathological rotation expressions.
MAX_TABLE_HANDLERS = 4096


@dataclass
class HandlerTable:
    """A dispatcher built from an indexable sequence of handler lambdas."""

    attr: str
    handlers: List[ast.Lambda]
    rotation: int = 0
    #: Parameter names shared by every handler, in order.
    params: Tuple[str, ...] = ()

    def rotated(self) -> List[Tuple[int, ast.Lambda]]:
        """Opcode number -> handler, with the sample's own rotation applied."""
        size = len(self.handlers)
        if size == 0:
            return []
        shift = self.rotation % size
        order = self.handlers[shift:] + self.handlers[:shift]
        return list(enumerate(order))


@dataclass
class DispatchSite:
    """Where the interpreter loop indexes the handler table."""

    loop: ast.While
    table_attr: str
    code_attr: Optional[str]
    pc_attr: Optional[str]
    operand_offsets: Tuple[int, ...] = ()
    #: `pc + 3` in the next-pc computation gives the instruction width.
    width: int = 0
    registers_attr: Optional[str] = None
    register_count: int = 0
    #: Some interpreters never assign the pc: they push the fall-through address
    #: into a queue and unpack the next pc from it, so a handler jumps by
    #: replacing that queue. This names it, when the loop uses one.
    pc_carrier: Optional[str] = None
    fields: Dict[str, Any] = field(default_factory=dict)


def _attr_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _self_attr(node: ast.AST) -> Optional[str]:
    """``self.x`` -> 'x'; anything else -> None."""
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "self"):
        return node.attr
    return None


class _SelfToName(ast.NodeTransformer):
    """Rewrite ``self.field`` to a bare name so the evaluator can bind it."""

    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix
        self.renamed: Dict[str, str] = {}

    def visit_Attribute(self, node: ast.Attribute):
        attr = _self_attr(node)
        if attr is not None:
            alias = f"{self.prefix}{attr}"
            self.renamed[attr] = alias
            return ast.copy_location(ast.Name(id=alias, ctx=node.ctx), node)
        return self.generic_visit(node)


def _eval_field_expr(node: ast.expr, env: Dict[str, Any]) -> Tuple[bool, Any]:
    """
    Evaluate an expression written in terms of ``self.<field>`` bindings.

    The alias prefix must not collide with any name already in the expression:
    a sample may reuse a field's name for a lambda parameter, and a bare rewrite
    would then let the parameter shadow the field and silently change meaning.
    """
    try:
        tree = ast.parse(ast.unparse(node), mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return False, None

    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    prefix = "self_"
    while any(name.startswith(prefix) for name in used):
        prefix = "_" + prefix

    transformer = _SelfToName(prefix)
    rewritten = transformer.visit(tree).body
    scope = {transformer.renamed[k]: v for k, v in env.items()
             if k in transformer.renamed}
    return safe_eval(rewritten, scope)


def constructor_fields(cls: ast.ClassDef) -> Dict[str, Any]:
    """
    Fold every ``self.<field> = <literal expression>`` the constructor performs.

    Only values the bounded evaluator can prove are kept, so a field whose value
    depends on runtime input simply stays unknown rather than being guessed.
    """
    values: Dict[str, Any] = {}
    init = _method(cls, "__init__")
    if init is None:
        return values

    for stmt in ast.walk(init):
        if isinstance(stmt, ast.Assign):
            targets = stmt.targets
            value_node = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets = [stmt.target]
            value_node = stmt.value
        else:
            continue

        for target in targets:
            attr = _self_attr(target)
            if attr is not None:
                ok, value = _eval_field_expr(value_node, values)
                if ok:
                    values[attr] = value
                continue
            # `self.a, *self.b = (39,)` states a scalar field positionally.
            if isinstance(target, (ast.Tuple, ast.List)):
                ok, value = _eval_field_expr(value_node, values)
                if not ok or not isinstance(value, (tuple, list)):
                    continue
                for index, element in enumerate(target.elts):
                    if isinstance(element, ast.Starred):
                        break
                    name = _self_attr(element)
                    if name is not None and index < len(value):
                        values[name] = value[index]
    return values


def _method(cls: ast.ClassDef, name: str) -> Optional[ast.FunctionDef]:
    for item in cls.body:
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
    return None


def find_handler_table(cls: ast.ClassDef) -> Optional[HandlerTable]:
    """
    Locate ``self.<attr> = (lambda ..., lambda ..., ...)`` in the constructor.

    Every element must be a lambda taking the same parameters: a mixed tuple is
    a data structure that happens to contain a callback, not an opcode table.
    """
    init = _method(cls, "__init__")
    if init is None:
        return None

    best: Optional[HandlerTable] = None
    for stmt in ast.walk(init):
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        attr = _self_attr(stmt.targets[0])
        if attr is None or not isinstance(stmt.value, (ast.Tuple, ast.List)):
            continue
        elts = stmt.value.elts
        if not (MIN_TABLE_HANDLERS <= len(elts) <= MAX_TABLE_HANDLERS):
            continue
        if not all(isinstance(e, ast.Lambda) for e in elts):
            continue

        handlers: List[ast.Lambda] = list(elts)  # type: ignore[arg-type]
        signatures = {tuple(a.arg for a in h.args.args) for h in handlers}
        if len(signatures) != 1:
            continue
        params = signatures.pop()
        table = HandlerTable(attr=attr, handlers=handlers, params=params)
        if best is None or len(table.handlers) > len(best.handlers):
            best = table
    return best


def recover_rotation(cls: ast.ClassDef, table: HandlerTable,
                     fields: Dict[str, Any]) -> int:
    """
    Recover how far the table is rotated before dispatch.

    The sample rotates with a slice pair, ``t[k:] + t[:k]``, where ``k`` is an
    expression over constructor fields. Interpreting ``k`` with the bounded
    evaluator yields the real shift; a negative ``k`` is a Python slice from the
    end, which is a left rotation by ``len(t) + k``.
    """
    size = len(table.handlers)
    if size == 0:
        return 0

    env = dict(fields)
    for node in ast.walk(cls):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
            continue
        left, right = node.left, node.right
        if not (isinstance(left, ast.Subscript) and isinstance(right, ast.Subscript)):
            continue
        if not (isinstance(left.slice, ast.Slice) and isinstance(right.slice, ast.Slice)):
            continue
        if _table_attr_of(left) != table.attr or _table_attr_of(right) != table.attr:
            continue
        # t[k:] + t[:k] — both halves must name the same cut point.
        cut = left.slice.lower
        if cut is None or left.slice.upper is not None or right.slice.lower is not None:
            continue
        ok, value = _eval_field_expr(cut, env)
        if not ok or not isinstance(value, int) or isinstance(value, bool):
            continue
        return value % size if value >= 0 else (size + value) % size
    return 0


def _table_attr_of(node: ast.Subscript) -> Optional[str]:
    return _self_attr(node.value) or _attr_name(node.value)


def find_dispatch_site(cls: ast.ClassDef, table: HandlerTable,
                       fields: Dict[str, Any]) -> Optional[DispatchSite]:
    """
    Find the loop that calls ``table[code[pc]](code[pc + 1], code[pc + 2])``.

    The call shape states the whole instruction format: the subscript on the
    table names the code pool and the program counter, and the argument offsets
    give the operand count and therefore the instruction width.
    """
    for method in cls.body:
        if not isinstance(method, ast.FunctionDef):
            continue
        for loop in [n for n in ast.walk(method) if isinstance(n, ast.While)]:
            site = _site_from_loop(loop, table, fields)
            if site is not None:
                return site
    return None


def _site_from_loop(loop: ast.While, table: HandlerTable,
                    fields: Dict[str, Any]) -> Optional[DispatchSite]:
    for call in [n for n in ast.walk(loop) if isinstance(n, ast.Call)]:
        func = call.func
        if not isinstance(func, ast.Subscript):
            continue
        if _table_attr_of(func) != table.attr:
            continue

        code_attr, pc_attr, base_offset = _fetch_parts(func.slice)
        if code_attr is None:
            continue

        offsets: List[int] = []
        for arg in call.args:
            pool, name, offset = _fetch_parts(arg)
            if pool == code_attr and offset is not None:
                offsets.append(offset)
        if not offsets:
            continue

        width = _instruction_width(loop, pc_attr, base_offset or 0, offsets)
        site = DispatchSite(
            loop=loop,
            table_attr=table.attr,
            code_attr=code_attr,
            pc_attr=pc_attr,
            operand_offsets=tuple(offsets),
            width=width,
            pc_carrier=_find_pc_carrier(loop, pc_attr),
            fields=dict(fields),
        )
        _bind_registers(site, table, fields)
        return site
    return None


def _fetch_parts(node: ast.AST) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Split ``code[pc + k]`` into (code, pc, k)."""
    if not isinstance(node, ast.Subscript):
        return None, None, None
    pool = _self_attr(node.value) or _attr_name(node.value)
    index = node.slice
    if isinstance(index, ast.BinOp) and isinstance(index.op, ast.Add):
        if isinstance(index.right, ast.Constant) and isinstance(index.right.value, int):
            return pool, _self_attr(index.left) or _attr_name(index.left), index.right.value
        if isinstance(index.left, ast.Constant) and isinstance(index.left.value, int):
            return pool, _self_attr(index.right) or _attr_name(index.right), index.left.value
        return pool, None, None
    name = _self_attr(index) or _attr_name(index)
    if name is None:
        return pool, None, None
    return pool, name, 0


def _find_pc_carrier(loop: ast.While, pc_attr: Optional[str]) -> Optional[str]:
    """
    Name the sequence the next pc is unpacked from, when there is one.

    ``pc, *rest = queue`` states it directly: whatever sits on the right of an
    unpack whose first target is the program counter is the carrier, so a
    handler that rebinds that sequence is performing a jump.
    """
    if pc_attr is None:
        return None
    for node in ast.walk(loop):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, (ast.Tuple, ast.List)) or not target.elts:
            continue
        first = target.elts[0]
        if (_self_attr(first) or _attr_name(first)) != pc_attr:
            continue
        carrier = _self_attr(node.value) or _attr_name(node.value)
        if carrier is not None:
            return carrier
    return None


def _instruction_width(loop: ast.While, pc_attr: Optional[str],
                       base: int, offsets: List[int]) -> int:
    """
    Instruction width, from the loop's own next-pc computation.

    ``self.pending.append(pc + 3)`` states the stride directly; when no such
    expression exists the widest operand offset still bounds it from below.
    """
    for node in ast.walk(loop):
        target = None
        value = None
        if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
            target = _self_attr(node.target) or _attr_name(node.target)
            value = node.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "append" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
                left = _self_attr(arg.left) or _attr_name(arg.left)
                if left == pc_attr:
                    target, value = pc_attr, arg.right
        if target != pc_attr or value is None:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, int):
            if value.value > 0:
                return value.value
    return max(offsets, default=base) + 1


def register_expr(handlers: List[ast.Lambda], params: Tuple[str, ...]) -> Optional[ast.expr]:
    """
    The register file is whatever the handlers index with their own parameters.

    Frequency decides it: an operand-indexed subscript appearing across many
    handlers is the register file, whereas a table a single handler happens to
    read is not. This is evidence from the dispatcher itself rather than a guess
    from field sizes, which would pick the handler tuple.
    """
    counts: Dict[str, int] = {}
    nodes: Dict[str, ast.expr] = {}
    for handler in handlers:
        seen = set()
        for node in ast.walk(handler.body):
            if not isinstance(node, ast.Subscript):
                continue
            index = node.slice
            if isinstance(index, ast.Slice):
                index = index.lower
            if not (isinstance(index, ast.Name) and index.id in params):
                continue
            key = ast.unparse(node.value)
            seen.add(key)
            nodes.setdefault(key, node.value)
        for key in seen:
            counts[key] = counts.get(key, 0) + 1

    if not counts:
        return None
    best = max(counts, key=lambda k: counts[k])
    return nodes[best]


def _bind_registers(site: DispatchSite, table: HandlerTable,
                    fields: Dict[str, Any]) -> None:
    """Bind the register file to the sequence the handlers actually index."""
    expr = register_expr(table.handlers, table.params)
    if expr is None:
        return
    site.registers_attr = ast.unparse(expr)
    ok, value = _eval_field_expr(expr, fields)
    if ok and isinstance(value, (list, tuple)):
        site.register_count = len(value)


def build_table_model(cls: ast.ClassDef) -> Optional[Tuple[VMModel, HandlerTable, DispatchSite]]:
    """Recover a :class:`VMModel` for a table-dispatch interpreter, if this is one."""
    table = find_handler_table(cls)
    if table is None:
        return None

    fields = constructor_fields(cls)
    site = find_dispatch_site(cls, table, fields)
    if site is None:
        return None

    table.rotation = recover_rotation(cls, table, fields)

    model = VMModel(class_name=cls.name, dispatch_kind="table", machine="register")
    model.handler_rotation = table.rotation
    model.operand_count = len(site.operand_offsets)
    model.instruction_width = max(site.width, model.operand_count + 1)
    model.register_count = site.register_count

    if site.registers_attr:
        interpreter = RegisterHandlerInterpreter(
            params=table.params,
            register_key=site.registers_attr,
            scope_keys=_scope_keys(table, site),
            pc_carrier=site.pc_carrier,
        )
        for number, handler in table.rotated():
            state = interpreter.run(handler)
            model.opcodes[number] = classify_register_handler(
                state, number, ast.unparse(handler), model.operand_count
            )

    if not model.opcodes:
        return None

    model.notes.append(
        f"table dispatch: {len(table.handlers)} handlers, rotation "
        f"{table.rotation}, width {model.instruction_width}, "
        f"{model.register_count} registers, coverage {model.coverage():.0%}"
    )
    return model, table, site


def _scope_keys(table: HandlerTable, site: DispatchSite) -> Tuple[str, ...]:
    """
    Namespace dicts the handlers write through.

    A subscript target that is not the register file and is indexed by a decoded
    operand is a name-keyed scope, which is what distinguishes a global store
    from a register move.
    """
    found: Dict[str, int] = {}
    for handler in table.handlers:
        # Names the handler binds itself are values it computed, not namespaces;
        # counting them turns `regs[a][regs[b]]` into a bogus scope lookup.
        local = {
            n.target.id for n in ast.walk(handler)
            if isinstance(n, ast.NamedExpr) and isinstance(n.target, ast.Name)
        }
        local.update(a.arg for a in handler.args.args)

        for node in ast.walk(handler.body):
            if not isinstance(node, ast.Subscript):
                continue
            base = node.value
            key = ast.unparse(base)
            if key == site.registers_attr or key in local:
                continue
            # A namespace is reached through the interpreter itself or through
            # a module-level binding, never through a computed expression.
            if not (isinstance(base, ast.Name) or _self_attr(base) is not None
                    or (isinstance(base, ast.Subscript)
                        and _self_attr(base.value) is not None)):
                continue
            index = node.slice
            if isinstance(index, (ast.Name, ast.Call, ast.BoolOp)):
                found[key] = found.get(key, 0) + 1
    return tuple(sorted(found, key=lambda k: -found[k]))
