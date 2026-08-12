# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Register code -> readable Python.

A register machine lifts to correct but unreadable code: every operand goes
through a numbered slot, so ``base64.b64decode(payload)`` arrives as four
statements threading ``r25``. This pass rebuilds the expressions.

It works on the emitted AST rather than on strings, and every rewrite is
justified by a property that can be checked:

* **Copy propagation.** ``r25 = expr`` followed by exactly one read of ``r25``
  before it is written again lets ``expr`` move to that use. Restricted to a
  single basic block so no branch can reach the definition another way.
* **Effect ordering.** A definition may only move across statements that cannot
  observe it. Anything that calls, imports, or writes a name the expression
  reads blocks the move, because reordering two side effects changes behaviour.
* **Dead slot removal.** A slot nothing reads after propagation is a temporary
  the rebuild consumed, so removing it is backed by the substitution that
  actually happened rather than by how its name looks.

What cannot be proven is left exactly as it was: an unreadable statement is a
worse outcome than a wrong one only until someone trusts the wrong one.
"""

import ast
from typing import List, Optional, Set, Tuple

#: Rewriting is iterative; each round can expose another foldable temporary.
MAX_ROUNDS = 8

def reconstruct(source: str, slot_prefix: str = "r") -> str:
    """Rebuild expressions in lifted register code, returning valid Python."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    try:
        for _ in range(MAX_ROUNDS):
            before = ast.dump(tree)
            tree = _Rewriter(slot_prefix).visit(tree)
            ast.fix_missing_locations(tree)
            if ast.dump(tree) == before:
                break
        rebuilt = ast.unparse(tree)
    except (RecursionError, ValueError, AttributeError):
        return source

    # A rebuild that does not parse is discarded outright: the register form is
    # ugly but correct, and correctness outranks readability.
    try:
        ast.parse(rebuilt)
    except SyntaxError:
        return source
    return rebuilt

class _Rewriter(ast.NodeTransformer):
    """Applies propagation and slot cleanup to every statement suite."""

    def __init__(self, slot_prefix: str):
        super().__init__()
        self.prefix = slot_prefix

    def _suite(self, node):
        self.generic_visit(node)
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block:
                rebuilt = _collapse_import_slots(block, self.prefix)
                rebuilt = _rename_import_slots(rebuilt, self.prefix)
                rebuilt = _propagate(rebuilt, self.prefix)
                rebuilt = _drop_dead_slots(rebuilt, self.prefix)
                if not rebuilt and not isinstance(node, ast.Module):
                    rebuilt = [ast.Pass()]
                setattr(node, field, rebuilt)
        return node

    def visit_Subscript(self, node: ast.Subscript):
        """``x[slice(a, b, c)]`` is the machine's spelling of ``x[a:b:c]``."""
        self.generic_visit(node)
        index = node.slice
        if (isinstance(index, ast.Call) and isinstance(index.func, ast.Name)
                and index.func.id == "slice" and not index.keywords
                and 1 <= len(index.args) <= 3
                and not any(isinstance(a, ast.Starred) for a in index.args)):
            args = list(index.args)
            if len(args) == 1:
                lower, upper, step = None, args[0], None
            elif len(args) == 2:
                lower, upper, step = args[0], args[1], None
            else:
                lower, upper, step = args[0], args[1], args[2]
            # A None bound is the default, so writing it back would produce
            # `x[None:16:None]` where the sample means `x[:16]`.
            drop = lambda part: None if _is_none(part) else part  # noqa: E731
            node.slice = ast.copy_location(
                ast.Slice(lower=drop(lower), upper=drop(upper), step=drop(step)),
                index)
        return node

    visit_Module = _suite
    visit_FunctionDef = _suite
    visit_AsyncFunctionDef = _suite
    visit_ClassDef = _suite
    visit_If = _suite
    visit_For = _suite
    visit_AsyncFor = _suite
    visit_While = _suite
    visit_With = _suite
    visit_AsyncWith = _suite
    visit_Try = _suite

def _is_none(node: Optional[ast.expr]) -> bool:
    return isinstance(node, ast.Constant) and node.value is None

def _collapse_import_slots(stmts: List[ast.stmt], prefix: str) -> List[ast.stmt]:
    """
    Rewrite ``import m as r25`` + ``name = r25`` into a direct import.

    The machine has no notion of an import target, so it lands the module in a
    slot and copies it out. Recognising that pair restores the ordinary form,
    and the ``.attr`` variant becomes a from-import naming the same binding.
    """
    result: List[ast.stmt] = []
    index = 0
    while index < len(stmts):
        stmt = stmts[index]
        nxt = stmts[index + 1] if index + 1 < len(stmts) else None
        slot = _import_slot(stmt, prefix)

        if slot is not None and isinstance(nxt, ast.Assign) \
                and len(nxt.targets) == 1 and isinstance(nxt.targets[0], ast.Name):
            module = stmt.names[0].name          # type: ignore[union-attr]
            bound = nxt.targets[0].id
            value = nxt.value

            # `pkg = r25` — the slot is the module itself.
            if isinstance(value, ast.Name) and value.id == slot:
                result.append(ast.copy_location(
                    ast.Import(names=[ast.alias(name=module, asname=bound)]), stmt))
                index += 2
                continue

            # `AES = r25.AES` — a member of the module.
            if (isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
                    and value.value.id == slot):
                asname = None if value.attr == bound else bound
                result.append(ast.copy_location(
                    ast.ImportFrom(
                        module=module,
                        names=[ast.alias(name=value.attr, asname=asname)],
                        level=0,
                    ), stmt))
                index += 2
                continue

        result.append(stmt)
        index += 1
    return result

def _import_slot(stmt: ast.stmt, prefix: str) -> Optional[str]:
    """Slot name an ``import m as <slot>`` statement binds."""
    if not isinstance(stmt, ast.Import) or len(stmt.names) != 1:
        return None
    asname = stmt.names[0].asname
    if asname is None or not _is_slot(asname, prefix):
        return None
    return asname

def _rename_import_slots(stmts: List[ast.stmt], prefix: str) -> List[ast.stmt]:
    """
    Fold ``from m import Y as <slot>`` + ``Y = <slot>`` into one import.

    The first rewrite pass turns the machine's two-step import into a from-import
    that still lands in a slot; this collapses the leftover copy so the binding
    reads the way the original source would have written it.
    """
    result: List[ast.stmt] = []
    index = 0
    while index < len(stmts):
        stmt = stmts[index]
        nxt = stmts[index + 1] if index + 1 < len(stmts) else None

        if (isinstance(stmt, ast.ImportFrom) and len(stmt.names) == 1
                and stmt.names[0].asname is not None
                and _is_slot(stmt.names[0].asname, prefix)
                and isinstance(nxt, ast.Assign) and len(nxt.targets) == 1
                and isinstance(nxt.targets[0], ast.Name)
                and isinstance(nxt.value, ast.Name)
                and nxt.value.id == stmt.names[0].asname):
            bound = nxt.targets[0].id
            member = stmt.names[0].name
            result.append(ast.copy_location(
                ast.ImportFrom(
                    module=stmt.module,
                    names=[ast.alias(name=member,
                                     asname=None if member == bound else bound)],
                    level=stmt.level,
                ), stmt))
            index += 2
            continue

        # `import m as m` is how a direct import round-trips; drop the alias.
        if (isinstance(stmt, ast.Import) and len(stmt.names) == 1
                and stmt.names[0].asname == stmt.names[0].name):
            result.append(ast.copy_location(
                ast.Import(names=[ast.alias(name=stmt.names[0].name, asname=None)]),
                stmt))
            index += 1
            continue

        result.append(stmt)
        index += 1
    return result

def _propagate(stmts: List[ast.stmt], prefix: str) -> List[ast.stmt]:
    """Fold each single-use slot definition into the statement that reads it."""
    result = list(stmts)
    index = 0
    while index < len(result):
        stmt = result[index]
        slot = _slot_defined_by(stmt, prefix)
        if slot is None or not isinstance(stmt, ast.Assign):
            index += 1
            continue

        value = stmt.value
        target = _single_use_after(result, index, slot)
        if target is None:
            index += 1
            continue

        use_index, = target
        if not _movable(result, index, use_index, value, slot):
            index += 1
            continue

        substituted = _Substituter(slot, value).visit(result[use_index])
        ast.fix_missing_locations(substituted)
        result[use_index] = substituted
        del result[index]
    return result

def _slot_defined_by(stmt: ast.stmt, prefix: str) -> Optional[str]:
    """Name of the machine slot a statement defines, if it defines exactly one."""
    if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
        return None
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return None
    if not _is_slot(target.id, prefix):
        return None
    return target.id

def _is_slot(name: str, prefix: str) -> bool:
    """``r25`` — a generated machine slot rather than a recovered name."""
    return (name.startswith(prefix) and len(name) > len(prefix)
            and name[len(prefix):].isdigit())

def _single_use_after(stmts: List[ast.stmt], start: int,
                      slot: str) -> Optional[Tuple[int]]:
    """
    Index of the one statement that reads ``slot`` before it is rewritten.

    More than one read means folding would duplicate the expression, which
    duplicates its side effects; none means the definition is dead and a later
    pass removes it.
    """
    found: Optional[int] = None
    for index in range(start + 1, len(stmts)):
        stmt = stmts[index]
        reads = _read_count(stmt, slot)
        if reads > 1:
            return None
        if reads == 1:
            if found is not None:
                return None
            found = index
        if _rebinds(stmt, slot):
            break
    return (found,) if found is not None else None

def _read_count(node: ast.AST, name: str) -> int:
    return sum(1 for child in ast.walk(node)
               if isinstance(child, ast.Name) and child.id == name
               and isinstance(child.ctx, ast.Load))

def _rebinds(stmt: ast.stmt, name: str) -> bool:
    for child in ast.walk(stmt):
        if isinstance(child, ast.Name) and child.id == name \
                and isinstance(child.ctx, (ast.Store, ast.Del)):
            return True
        if isinstance(child, ast.alias) and (child.asname or child.name) == name:
            return True
    return False

def _movable(stmts: List[ast.stmt], start: int, end: int,
             value: ast.expr, slot: str) -> bool:
    """
    True when the definition can move down to its use without changing meaning.

    Two hazards matter: a statement in between may write something the
    expression reads, and moving one side effect past another reorders them.
    """
    reads = _names_read(value)
    effectful = _has_effect(value)

    for index in range(start + 1, end):
        between = stmts[index]
        if effectful and _has_effect(between):
            return False
        for name in reads:
            if _rebinds(between, name):
                return False
        if _rebinds(between, slot):
            return False
    return True

def _names_read(node: ast.AST) -> Set[str]:
    return {child.id for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}

def _has_effect(node: ast.AST) -> bool:
    """Conservatively true when evaluating the node could be observed."""
    for child in ast.walk(node):
        if isinstance(child, (ast.Call, ast.Await, ast.Yield, ast.YieldFrom,
                              ast.Import, ast.ImportFrom, ast.Raise,
                              ast.Delete, ast.NamedExpr)):
            return True
        if isinstance(child, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            return True
    return False

class _Substituter(ast.NodeTransformer):
    """Replaces reads of one slot with the expression that defined it."""

    def __init__(self, slot: str, value: ast.expr):
        super().__init__()
        self.slot = slot
        self.value = value

    def visit_Name(self, node: ast.Name):
        if node.id == self.slot and isinstance(node.ctx, ast.Load):
            # ast.unparse re-derives precedence parentheses, so the definition
            # node can be spliced in directly.
            return ast.copy_location(self.value, node)
        return node

def _drop_dead_slots(stmts: List[ast.stmt], prefix: str) -> List[ast.stmt]:
    """
    Remove slot assignments nothing reads.

    Only generated slots qualify, and only when the discarded value cannot have
    a side effect — a call whose result is unused still had to run.
    """
    live: Set[str] = set()
    for stmt in stmts:
        live |= _names_read(stmt)

    kept: List[ast.stmt] = []
    for stmt in stmts:
        slot = _slot_defined_by(stmt, prefix)
        if (slot is not None and slot not in live
                and isinstance(stmt, ast.Assign)
                and not _has_effect(stmt.value)):
            continue
        kept.append(stmt)
    return kept
