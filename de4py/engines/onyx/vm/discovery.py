# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
VM discovery.

Locates an interpreter in a module and recovers, from its dispatch loop alone:
the program counter, the stack and its push/pop aliases, the const/name/bytecode
pools, the local and global scope dicts, the operand registers, and the
instruction width. Everything downstream is derived from these bindings, so a
sample that renames every identifier still lifts.
"""

import ast
from typing import List, Optional, Tuple

from de4py.engines.onyx.vm.ir import OpcodeSpec, VMModel, VOp
from de4py.engines.onyx.vm.semantics import HandlerInterpreter, VMNames, classify

#: A dispatcher needs enough arms to be a real opcode table rather than a
#: two-way branch that happens to switch on an integer.
MIN_DISPATCH_ARMS = 6


def _int_cases(match_node: ast.Match) -> List[int]:
    out = []
    for case in match_node.cases:
        pattern = case.pattern
        if (isinstance(pattern, ast.MatchValue)
                and isinstance(pattern.value, ast.Constant)
                and isinstance(pattern.value.value, int)):
            out.append(pattern.value.value)
    return out


def find_dispatch_loop(node: ast.AST) -> Optional[Tuple[ast.While, ast.Match]]:
    """Return the (loop, match) pair that forms an opcode dispatcher."""
    best = None
    best_arms = 0
    for outer in ast.walk(node):
        if not isinstance(outer, ast.While):
            continue
        for inner in ast.walk(outer):
            if not isinstance(inner, ast.Match):
                continue
            arms = len(_int_cases(inner))
            if arms >= MIN_DISPATCH_ARMS and arms > best_arms:
                best, best_arms = (outer, inner), arms
    return best


def _is_empty_list(node) -> bool:
    return isinstance(node, ast.List) and not node.elts


def recover_names(call_method: ast.FunctionDef, loop: ast.While,
                  match_node: ast.Match, class_name: str) -> VMNames:
    """Bind interpreter roles by reading the prologue and the fetch expressions."""
    names = VMNames()
    names.vm_class = class_name

    # `self.bytecode, self.consts, self.names = pickle.loads(...)` lives in
    # __init__, but the loop refers to them as attributes; capture the attribute
    # names that index with the operand or bound the loop.
    for stmt in ast.walk(call_method):
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        target, value = stmt.targets[0], stmt.value
        if not isinstance(target, ast.Name):
            continue
        if _is_empty_list(value):
            names.stack = target.id
        elif isinstance(value, ast.Attribute):
            base = value.value
            if isinstance(base, ast.Name) and base.id == names.stack:
                if value.attr == "pop":
                    names.pop = target.id
                elif value.attr == "append":
                    names.push = target.id
        elif isinstance(value, ast.Call):
            fname = value.func.id if isinstance(value.func, ast.Name) else None
            if fname == "vars":
                # `vlocals = vars(__builtins__)` — a scope dict
                if names.locals is None:
                    names.locals = target.id

    # Module-level `vglobals = vars(__builtins__)` sits outside __call__.
    module = _enclosing_module(call_method)
    if module is not None:
        for stmt in module.body:
            if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                    and isinstance(stmt.targets[0], ast.Name)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id == "vars"):
                names.globals = stmt.targets[0].id

    # The loop test `while cx < len(self.bytecode)` names the pc and the code pool.
    test = loop.test
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name):
        names.pc = test.left.id
        for comparator in test.comparators:
            for sub in ast.walk(comparator):
                if isinstance(sub, ast.Attribute):
                    names.bytecode = sub.attr

    # `opc = self.bytecode[cx]` / `opa = self.bytecode[cx + 1]` name the registers
    # and, by their index offsets, give the instruction width.
    offsets = []
    for stmt in loop.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Subscript)):
            continue
        pool = stmt.value.value
        pool_name = pool.attr if isinstance(pool, ast.Attribute) else (
            pool.id if isinstance(pool, ast.Name) else None)
        if names.bytecode and pool_name != names.bytecode:
            continue
        offset = _index_offset(stmt.value.slice, names.pc)
        if offset is None:
            continue
        offsets.append((offset, stmt.targets[0].id))

    offsets.sort()
    if offsets:
        names.opcode_var = offsets[0][1]
        names.operand_vars = [ident for _, ident in offsets[1:]]

    # The const/name pools are whatever the handlers subscript with the operand.
    for case in match_node.cases:
        for sub in ast.walk(case):
            if not isinstance(sub, ast.Subscript):
                continue
            base = sub.value
            if not isinstance(base, ast.Attribute):
                continue
            index = sub.slice
            if isinstance(index, ast.Name) and index.id in names.operand_vars:
                lowered = base.attr.lower()
                if "const" in lowered and names.consts is None:
                    names.consts = base.attr
                elif "name" in lowered and names.names is None:
                    names.names = base.attr

    if names.consts is None:
        names.consts = "consts"
    if names.names is None:
        names.names = "names"
    return names


def _index_offset(slice_node, pc_name: Optional[str]) -> Optional[int]:
    """`cx` -> 0, `cx + 1` -> 1."""
    if isinstance(slice_node, ast.Name):
        return 0 if (pc_name is None or slice_node.id == pc_name) else None
    if (isinstance(slice_node, ast.BinOp) and isinstance(slice_node.op, ast.Add)
            and isinstance(slice_node.left, ast.Name)
            and isinstance(slice_node.right, ast.Constant)
            and isinstance(slice_node.right.value, int)):
        if pc_name is None or slice_node.left.id == pc_name:
            return slice_node.right.value
    return None


def _enclosing_module(node) -> Optional[ast.Module]:
    return getattr(node, "_onyx_module", None)


def _payload_order(cls: ast.ClassDef, names: VMNames) -> Tuple[str, ...]:
    """
    Recover the payload's field order from the constructor's tuple unpack.

    ``self.bytecode, self.consts, self.names = pickle.loads(data)`` states the
    order explicitly, so reading it beats guessing from element types.
    """
    role_of = {}
    if names.bytecode:
        role_of[names.bytecode] = "bytecode"
    if names.consts:
        role_of[names.consts] = "consts"
    if names.names:
        role_of[names.names] = "names"

    for item in cls.body:
        if not isinstance(item, ast.FunctionDef) or item.name != "__init__":
            continue
        for stmt in ast.walk(item):
            if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                continue
            target = stmt.targets[0]
            if not isinstance(target, (ast.Tuple, ast.List)) or len(target.elts) < 3:
                continue
            order = []
            for element in target.elts:
                attr = element.attr if isinstance(element, ast.Attribute) else None
                if attr is None:
                    order = []
                    break
                lowered = attr.lower()
                if attr in role_of:
                    order.append(role_of[attr])
                elif "byte" in lowered or "code" in lowered:
                    order.append("bytecode")
                elif "const" in lowered:
                    order.append("consts")
                elif "name" in lowered:
                    order.append("names")
                else:
                    order.append(attr)
            if len(order) >= 3 and len(set(order)) == len(order):
                return tuple(order)
    return ("bytecode", "consts", "names")


def _instruction_width(loop: ast.While, pc_name: Optional[str], operands: int) -> int:
    """`cx += 2` at the tail of the loop gives the real width."""
    for stmt in loop.body:
        if (isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name)
                and stmt.target.id == pc_name
                and isinstance(stmt.op, ast.Add)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, int)):
            return stmt.value.value
    return operands + 1


class VMDiscovery:
    """Finds interpreters in a module and recovers a model for each."""

    def discover(self, tree: ast.Module) -> List[VMModel]:
        models = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            model = self._from_class(node, tree)
            if model is not None:
                models.append(model)
        return models

    def _from_class(self, cls: ast.ClassDef, module: ast.Module) -> Optional[VMModel]:
        call_method = None
        for item in cls.body:
            if isinstance(item, ast.FunctionDef) and item.name in ("__call__", "run",
                                                                   "execute", "start"):
                call_method = item
                break
        if call_method is None:
            for item in cls.body:
                if isinstance(item, ast.FunctionDef) and find_dispatch_loop(item):
                    call_method = item
                    break
        if call_method is None:
            return None

        found = find_dispatch_loop(call_method)
        if found is None:
            return None
        loop, match_node = found

        setattr(call_method, "_onyx_module", module)
        names = recover_names(call_method, loop, match_node, cls.name)

        model = VMModel(class_name=cls.name, dispatch_kind="match")
        model.payload_order = _payload_order(cls, names)
        model.operand_count = max(1, len(names.operand_vars))
        model.instruction_width = _instruction_width(loop, names.pc, model.operand_count)

        interpreter = HandlerInterpreter(names)
        for case in match_node.cases:
            pattern = case.pattern
            if not (isinstance(pattern, ast.MatchValue)
                    and isinstance(pattern.value, ast.Constant)
                    and isinstance(pattern.value.value, int)):
                continue
            number = pattern.value.value
            state = interpreter.run(case.body)
            source = "; ".join(ast.unparse(s) for s in case.body)[:200]
            model.opcodes[number] = classify(state, number, source)

        if not model.opcodes:
            return None

        model.notes.append(
            f"width={model.instruction_width} operands={model.operand_count} "
            f"coverage={model.coverage():.0%}"
        )
        return model
