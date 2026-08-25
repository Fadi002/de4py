# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Payload extraction.

Finds the serialized programs a VM is constructed with, decodes them into
``VProgram`` objects, and recursively recovers nested programs (the shape a
``MAKE_VM`` opcode builds a callable out of).

Payloads are read with a whitelist unpickler that resolves *only* primitive
container and scalar types. ``pickle`` normally grants arbitrary code execution on
untrusted input, so ``find_class`` refuses every module/name pair outside that
list rather than blocking a denylist — a REDUCE opcode naming any callable simply
fails to load.
"""

import ast
import io
import pickle
from typing import Any, Dict, List, Optional, Sequence, Tuple

from de4py.engines.onyx.vm.ir import VMModel, VOp, VProgram
from de4py.engines.onyx.vm.lifter import decode

_SAFE_BUILTINS = frozenset({
    "dict", "list", "tuple", "set", "frozenset", "int", "float", "str",
    "bytes", "bool", "complex", "bytearray", "NoneType", "range", "slice",
})

MAX_PAYLOAD_BYTES = 32 * 1024 * 1024


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler that can only rebuild primitive containers and scalars."""

    def find_class(self, module, name):
        if module == "builtins" and name in _SAFE_BUILTINS:
            import builtins
            return getattr(builtins, name)
        raise pickle.UnpicklingError(f"refused type: {module}.{name}")


def safe_loads(data: bytes) -> Any:
    if not isinstance(data, (bytes, bytearray)) or len(data) > MAX_PAYLOAD_BYTES:
        raise ValueError("payload rejected")
    return RestrictedUnpickler(io.BytesIO(data)).load()


def looks_like_payload(value: Any) -> bool:
    return isinstance(value, (bytes, bytearray)) and len(value) > 8 and value[:1] == b"\x80"


def _split_payload(data: Any, model: VMModel) -> Optional[Tuple[List[int], List[Any], List[str]]]:
    """
    Split a payload into (code, consts, names).

    Position is authoritative: the interpreter's ``__init__`` unpacks the payload
    in a fixed order, recovered by discovery into ``model.payload_order``. Type
    sniffing is only a fallback, and cannot be trusted on its own — an empty
    const pool satisfies "every element is a string" vacuously and would steal
    the name pool's slot.
    """
    if not isinstance(data, (tuple, list)) or len(data) < 3:
        return None

    parts = [list(p) if isinstance(p, (list, tuple)) else None for p in data[:3]]
    if all(p is not None for p in parts):
        order = model.payload_order
        slots = {role: parts[i] for i, role in enumerate(order[:3])}
        code = slots.get("bytecode")
        if code is not None and code and all(isinstance(x, int) for x in code):
            return (code,
                    list(slots.get("consts") or []),
                    [str(n) for n in (slots.get("names") or [])])

    code = consts = names = None
    for part in parts:
        if part is None:
            continue
        if code is None and part and all(isinstance(x, int) for x in part):
            code = part
        elif names is None and part and all(isinstance(x, str) for x in part):
            names = part
        elif consts is None:
            consts = part
    if code is None:
        return None
    return code, list(consts or []), [str(n) for n in (names or [])]


def _infer_params(instrs, names: List[str], model: VMModel, arity: Optional[int]) -> List[str]:
    """
    Parameters are the leading entries of the name pool.

    The prologue binds ``names[i] = args[i]`` for each supplied argument, so the
    arity observed at the call site names the parameters. Without a call site,
    fall back to names read before they are ever written.
    """
    if arity is not None:
        return [names[i] if i < len(names) else f"arg{i}" for i in range(arity)]
    written: set = set()
    params: List[str] = []
    for instr in instrs:
        if instr.op in (VOp.STORE_LOCAL, VOp.STORE_GLOBAL):
            if 0 <= instr.arg < len(names):
                written.add(names[instr.arg])
        elif instr.op is VOp.LOAD_LOCAL and 0 <= instr.arg < len(names):
            name = names[instr.arg]
            if name not in written and name not in params:
                params.append(name)
    return params[:4]


class PayloadExtractor:
    """Pulls VM payloads out of a module and turns them into ``VProgram`` trees."""

    def __init__(self, model: VMModel):
        self.model = model

    def find_payloads(self, tree: ast.Module) -> List[Tuple[bytes, str, Optional[int]]]:
        """Return (payload, suggested_name, arity) for each VM construction."""
        found: List[Tuple[bytes, str, Optional[int]]] = []
        arities = self._call_arities(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name)
                    and node.func.id == self.model.class_name):
                continue
            if not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, bytes)):
                continue
            name = self._binding_name(tree, node) or "vm_main"
            found.append((arg.value, name, arities.get(name)))
        return found

    def _binding_name(self, tree: ast.Module, call: ast.Call) -> Optional[str]:
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and node.value is call
                    and node.targets and isinstance(node.targets[0], ast.Name)):
                return node.targets[0].id
        return None

    def _call_arities(self, tree: ast.Module) -> Dict[str, int]:
        arities: Dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                arities.setdefault(node.func.id, len(node.args))
        return arities

    def build(self, payload: bytes, name: str, arity: Optional[int] = None,
              depth: int = 0) -> Optional[VProgram]:
        if depth > 6:
            return None
        try:
            data = safe_loads(payload)
        except Exception:
            return None
        parts = _split_payload(data, self.model)
        if parts is None:
            return None
        code, consts, names = parts
        instrs = decode(code, self.model)
        program = VProgram(
            name=_sanitize(name),
            instructions=instrs,
            consts=consts,
            names=names,
            params=_infer_params(instrs, names, self.model, arity),
        )
        program.nested = self._nested(program, depth)
        if depth == 0:
            # Arity can only be resolved once the whole tree exists: a helper is
            # usually called by a sibling, not by the program that defines it.
            _resolve_params(program)
        return program

    def _nested(self, program: VProgram, depth: int) -> List[VProgram]:
        """
        Recover functions built by MAKE_VM.

        The pattern is ``LOAD_CONST <payload>; MAKE_VM <name>``: the const holds a
        pickled program and the operand names the global it is bound to, so the
        pair gives both the body and the function name.
        """
        out: List[VProgram] = []
        instrs = program.instructions
        make_vm_ops = set(self.model.by_op(VOp.MAKE_VM))
        if not make_vm_ops:
            return out
        for index, instr in enumerate(instrs):
            if instr.opcode not in make_vm_ops:
                continue
            const_index = None
            for back in range(index - 1, max(-1, index - 4), -1):
                if instrs[back].op is VOp.LOAD_CONST:
                    const_index = instrs[back].arg
                    break
            if const_index is None or not (0 <= const_index < len(program.consts)):
                continue
            blob = program.consts[const_index]
            if not looks_like_payload(blob):
                continue
            fn_name = (program.names[instr.arg]
                       if 0 <= instr.arg < len(program.names) else f"vm_fn_{index}")
            arity = self._nested_arity(program, fn_name)
            child = self.build(bytes(blob), fn_name, arity, depth + 1)
            if child is not None:
                out.append(child)
        return out

    def _nested_arity(self, program: VProgram, fn_name: str) -> Optional[int]:
        """
        Arity of a nested function, read off the call sites that invoke it.

        Scanning backwards by instruction count mis-counts as soon as an argument
        is itself an expression, so replay the block over a symbolic stack: at a
        CALL with operand k the callee sits exactly k slots below the top, which
        identifies it exactly regardless of how the arguments were computed.
        """
        for callee, argc in collect_call_sites(program):
            if callee == fn_name:
                return argc
        for nested in program.nested:
            found = self._nested_arity(nested, fn_name)
            if found is not None:
                return found
        return None


def _walk(program: VProgram):
    yield program
    for nested in program.nested:
        yield from _walk(nested)


def _resolve_params(root: VProgram) -> None:
    """
    Fix every program's parameter list using call sites from the whole tree.

    The interpreter prologue binds ``names[i] = args[i]``, so an observed arity of
    k means the first k entries of the name pool are the parameters — in pool
    order, which is what makes the recovered signature match the original.
    """
    arities: Dict[str, int] = {}
    for program in _walk(root):
        for callee, argc in collect_call_sites(program):
            arities.setdefault(callee, argc)

    for program in _walk(root):
        if program is root:
            continue
        argc = arities.get(program.name)
        if argc is None:
            continue
        program.params = [
            program.names[i] if i < len(program.names) else f"arg{i}"
            for i in range(argc)
        ]


def collect_call_sites(program: VProgram) -> List[Tuple[str, int]]:
    """Replay the instruction stream symbolically and report (callee, argcount)."""
    stack: List[Optional[str]] = []
    out: List[Tuple[str, int]] = []

    def name_of(index: int) -> Optional[str]:
        names = program.names
        return names[index] if 0 <= index < len(names) else None

    for instr in program.instructions:
        op = instr.op
        if op in (VOp.LOAD_LOCAL, VOp.LOAD_GLOBAL):
            stack.append(name_of(instr.arg))
        elif op is VOp.LOAD_CONST:
            stack.append(None)
        elif op is VOp.CALL:
            count = instr.arg if instr.spec.operand_role == "count" else 0
            for _ in range(count):
                if stack:
                    stack.pop()
            callee = stack.pop() if stack else None
            if callee:
                out.append((callee, count))
            stack.append(None)
        elif op in (VOp.BINARY, VOp.COMPARE, VOp.BOOL, VOp.SUBSCRIPT, VOp.LOAD_ATTR):
            for _ in range(2):
                if stack:
                    stack.pop()
            stack.append(None)
        elif op is VOp.UNARY:
            if stack:
                stack.pop()
            stack.append(None)
        elif op in (VOp.BUILD_TUPLE, VOp.BUILD_LIST):
            for _ in range(instr.arg):
                if stack:
                    stack.pop()
            stack.append(None)
        elif op is VOp.BUILD_SLICE:
            for _ in range(3):
                if stack:
                    stack.pop()
            stack.append(None)
        elif op in (VOp.STORE_LOCAL, VOp.STORE_GLOBAL, VOp.MAKE_VM, VOp.RETURN,
                    VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE, VOp.POP):
            if stack:
                stack.pop()
    return out


def _sanitize(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"vm_{cleaned}"
    return cleaned
