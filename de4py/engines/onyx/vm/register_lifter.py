# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Register-machine payload extraction and emission.

A table-dispatch VM carries its program as a flat byte string plus encoded
pools, and each instruction already names its own operands, so lifting does not
need a symbolic stack: ``regs[a] = regs[a] op regs[b]`` is three-address code
already. What it does need is the pools, and those are stored encoded — the
interpreter owns a decoder method for each.

Rather than reimplement those codecs, the decoder *method bodies are
interpreted* with :mod:`de4py.engines.onyx.safe_eval`. The sample's own
arithmetic therefore produces the strings, which means a variant that changes
its constants still decodes, and no sample code is ever executed.

Control flow reuses :mod:`de4py.engines.onyx.vm.lifter`: the CFG, dominator and
structuring passes there are machine-agnostic, so only the per-block rendering
step is specific to registers.
"""

import ast
import builtins
import keyword
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from de4py.engines.onyx.safe_eval import SafeFunctionRunner, safe_eval
from de4py.engines.onyx.vm.ir import Block, OpcodeSpec, VInstr, VMModel, VOp, VProgram

MAX_PROGRAM_INSTRUCTIONS = 200_000
MAX_NESTED_DEPTH = 8

def decode_register_program(code: Sequence[int], model: VMModel) -> List[VInstr]:
    """
    Split a flat instruction stream using the recovered fixed width.

    Offsets are kept in *instruction* units rather than bytes because a jump
    operand indexes instructions; the handler's own scale factor states this and
    is applied when the target is resolved.
    """
    width = max(1, model.instruction_width)
    operands = max(0, width - 1)
    out: List[VInstr] = []
    index = 0
    position = 0
    while position + width <= len(code) and index < MAX_PROGRAM_INSTRUCTIONS:
        opcode = code[position]
        args = tuple(code[position + 1 + i] for i in range(operands))
        spec = model.opcodes.get(opcode) or OpcodeSpec(number=opcode, op=VOp.UNKNOWN)
        out.append(VInstr(offset=index, opcode=opcode, operands=args, spec=spec))
        position += width
        index += 1
    return out

def _resolve_targets(instrs: List[VInstr], model: VMModel) -> None:
    """
    Rewrite jump operands into instruction indices.

    A target is stored scaled by the factor its handler multiplies by, so the
    conversion divides by that factor rather than by the instruction width —
    the two coincide in the samples seen so far, but only one of them is stated
    by the handler.
    """
    for instr in instrs:
        if instr.op not in (VOp.JUMP, VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE):
            continue
        position = instr.spec.role_index("target")
        if position is None or position >= len(instr.operands):
            continue
        scale = max(1, instr.spec.target_scale)
        raw = instr.operands[position]
        resolved = raw // scale if scale > 1 else raw
        operands = list(instr.operands)
        operands[position] = resolved
        instr.operands = tuple(operands)

class DecoderReplay:
    """
    Replays an interpreter's own decoder methods over the bounded evaluator.

    Each method takes an encoded pool and returns a decoded value. Interpreting
    the method body means the recovered strings come from the sample's own
    arithmetic, so nothing about the encoding has to be known in advance.
    """

    def __init__(self, cls: ast.ClassDef, fields: Dict[str, Any]):
        self.cls = cls
        self.fields = dict(fields)
        self.methods = {
            item.name: item for item in cls.body if isinstance(item, ast.FunctionDef)
        }

    def decode_pool(self, method_name: str, payload: Any,
                    extra: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """
        Run one decoder method against a payload and return what it produced.

        Instance fields are rewritten into plain bound names rather than handed
        to the evaluator as an object. The evaluator refuses attribute access on
        arbitrary objects on purpose — that refusal is the sandbox boundary, and
        widening it to read a pool would trade a decoded string for an escape
        route. Nothing is executed: the body is interpreted under the usual
        budget.
        """
        method = self.methods.get(method_name)
        if method is None or len(method.args.args) < 2:
            return None

        fields = dict(self.fields)
        if extra:
            fields.update(extra)

        rewritten, env = _bind_self(method, fields)
        if rewritten is None:
            return None

        # A fresh runner per call: the step budget lives on the runner, so a
        # shared one would let the first pool entry starve every later entry.
        try:
            return SafeFunctionRunner(env).run_function(rewritten, [payload])
        except Exception:
            return None

    def decode_indexed(self, method_name: str, count: int,
                       extra: Optional[Dict[str, Any]] = None) -> List[Any]:
        """
        Decode a pool entry by entry until the decoder stops producing values.

        Pool length is not recorded anywhere in the sample, so the end is found
        by decoding until failure rather than by trusting a declared size.
        """
        out: List[Any] = []
        for index in range(max(0, count)):
            value = self.decode_pool(method_name, index, extra)
            if value is None:
                break
            out.append(_unwrap(value))
        return out

    def decoder_names(self) -> List[str]:
        """Methods shaped like a single-pool decoder."""
        return [name for name, method in self.methods.items()
                if not name.startswith("__") and len(method.args.args) == 2]

def _unwrap(value: Any) -> Any:
    """A decoder that published through one field returns a 1-tuple; unwrap it."""
    if isinstance(value, tuple) and len(value) == 1:
        return value[0]
    return value

class _SelfBinder(ast.NodeTransformer):
    """Replace every ``self.<field>`` read with a uniquely-named bound value."""

    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix
        self.seen: Dict[str, str] = {}

    def visit_Attribute(self, node: ast.Attribute):
        if (isinstance(node.value, ast.Name) and node.value.id == "self"):
            alias = f"{self.prefix}{node.attr}"
            self.seen[node.attr] = alias
            return ast.copy_location(ast.Name(id=alias, ctx=node.ctx), node)
        return self.generic_visit(node)

def _bind_self(method: ast.FunctionDef,
               fields: Dict[str, Any]) -> Tuple[Optional[ast.FunctionDef], Dict[str, Any]]:
    """
    Rewrite a decoder method into a plain single-argument function.

    ``self`` is dropped from the signature and each field read becomes a bound
    name, chosen so it cannot collide with a local the method already uses.
    """
    try:
        clone = ast.parse(ast.unparse(method)).body[0]
    except (SyntaxError, ValueError, RecursionError):
        return None, {}
    if not isinstance(clone, ast.FunctionDef):
        return None, {}

    used = {n.id for n in ast.walk(clone) if isinstance(n, ast.Name)}
    prefix = "self_"
    while any(name.startswith(prefix) for name in used):
        prefix = "_" + prefix

    binder = _SelfBinder(prefix)
    clone = binder.visit(clone)
    clone.args.args = clone.args.args[1:]
    clone.decorator_list = []

    # A decoder commonly publishes its result by writing an instance field
    # rather than returning it. Those writes are now plain local assignments,
    # so the rewritten function is given a return that surfaces them.
    if not any(isinstance(n, ast.Return) and n.value is not None
               for n in ast.walk(clone)):
        written = sorted({
            target.id
            for node in ast.walk(clone) if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name) and target.id.startswith(prefix)
        })
        if written:
            clone.body.append(ast.Return(value=ast.Tuple(
                elts=[ast.Name(id=name, ctx=ast.Load()) for name in written],
                ctx=ast.Load(),
            )))

    ast.fix_missing_locations(clone)

    env = {alias: fields[attr] for attr, alias in binder.seen.items()
           if attr in fields}
    return clone, env

class RegisterPayloadExtractor:
    """
    Builds :class:`VProgram` trees for a table-dispatch interpreter.

    The constructor's own signature says what each payload slot is: the slot
    whose value the dispatch loop indexes is the bytecode, and the remaining
    slots are pools identified by which decoder method accepts them. A slot
    holding a list of same-shaped payloads is the nested-program table.
    """

    def __init__(self, model: VMModel, cls: ast.ClassDef,
                 fields: Dict[str, Any], code_field: Optional[str],
                 nested_field: Optional[str] = None):
        self.model = model
        self.cls = cls
        self.fields = dict(fields)
        self.code_field = code_field
        self.nested_field = nested_field
        self.params = [a.arg for a in _init_args(cls)]

    def build(self, payload: Sequence[Any], name: str,
              depth: int = 0) -> Optional[VProgram]:
        if depth > MAX_NESTED_DEPTH:
            return None

        bound = dict(self.fields)
        for param, value in zip(self.params, payload):
            bound[param] = value

        code = bound.get(self.code_field) if self.code_field else None
        if not isinstance(code, (bytes, bytearray, list, tuple)):
            return None

        instrs = decode_register_program(list(code), self.model)
        if not instrs:
            return None
        _resolve_targets(instrs, self.model)

        replay = DecoderReplay(self.cls, bound)
        consts, names = self._pools(replay, instrs)

        program = VProgram(
            name=_sanitize(name),
            instructions=instrs,
            consts=consts,
            names=names,
        )
        program.nested = self._nested(bound, name, depth)
        return program

    def _pools(self, replay: DecoderReplay,
               instrs: List[VInstr]) -> Tuple[List[Any], List[str]]:
        """
        Decode each pool only as far as the program actually indexes it.

        The highest operand carrying a given role bounds that pool, so nothing
        is decoded speculatively and a decoder that stops producing values ends
        the pool early.
        """
        # LOAD_IMM reaches the constant pool through its source operand, so a
        # bound derived only from `const`-tagged operands stops one entry short
        # and the last constant renders as a placeholder.
        highest = max(
            _max_role_operand(instrs, "name"),
            _max_role_operand(instrs, "const"),
            _max_role_operand(instrs, "immediate"),
            _max_pool_operand(instrs),
        )
        if highest < 0:
            return [], []

        # Each decoder is tried against the same index range; the one whose
        # results are all identifiers-or-strings is the name pool, and any other
        # is the constant pool. Which method serves which is not stated in the
        # sample, so it is decided by what comes back.
        decoded = {name: replay.decode_indexed(name, highest + 1)
                   for name in replay.decoder_names()}
        decoded = {k: v for k, v in decoded.items() if v}

        names: List[str] = []
        consts: List[Any] = []
        for values in decoded.values():
            if all(isinstance(v, str) for v in values):
                if len(values) > len(names):
                    names = [str(v) for v in values]
            elif len(values) > len(consts):
                consts = values
        return consts, names

    def _nested(self, bound: Dict[str, Any], parent: str,
                depth: int) -> List[VProgram]:
        """Recover programs held in the payload slot that lists sub-payloads."""
        if self.nested_field is None:
            return []
        table = bound.get(self.nested_field)
        if not isinstance(table, (list, tuple)):
            return []

        out: List[VProgram] = []
        for index, entry in enumerate(table):
            if not isinstance(entry, (list, tuple)):
                continue
            child = self.build(entry, f"{parent}_fn{index}", depth + 1)
            if child is not None:
                out.append(child)
        return out

def _init_args(cls: ast.ClassDef) -> List[ast.arg]:
    for item in cls.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            return item.args.args[1:]
    return []

def _max_pool_operand(instrs: List[VInstr]) -> int:
    """
    Highest index any pool-reading instruction uses.

    An opcode whose handler resolves an operand through the interpreter's
    decoder indexes a pool even when its role is spelled differently, so the
    bound is taken from the instruction's own semantic class.
    """
    pool_ops = (VOp.LOAD_CONST, VOp.LOAD_IMM, VOp.LOAD_GLOBAL,
                VOp.STORE_GLOBAL, VOp.LOAD_ATTR, VOp.IMPORT, VOp.MAKE_VM)
    highest = -1
    for instr in instrs:
        if instr.op not in pool_ops:
            continue
        for position, role in enumerate(instr.spec.operand_roles):
            if role in ("dest", "target", "range_end"):
                continue
            if position < len(instr.operands):
                value = instr.operands[position]
                if isinstance(value, int) and value > highest:
                    highest = value
    return highest

def _max_role_operand(instrs: List[VInstr], role: str) -> int:
    """
    Largest value any operand carrying ``role`` takes, or -1 if unused.

    Only operands the handler actually assigned that role are counted: reading
    every operand of a matching instruction would let a register number inflate
    a pool bound and index past its end.
    """
    highest = -1
    for instr in instrs:
        position = instr.spec.role_index(role)
        if position is None or position >= len(instr.operands):
            continue
        value = instr.operands[position]
        if isinstance(value, int) and value > highest:
            highest = value
    return highest

def _sanitize(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"vm_{cleaned}"
    return cleaned

class RegisterBlockLifter:
    """Renders one basic block of a register machine as Python statements."""

    def __init__(self, program: VProgram, model: VMModel,
                 nested_names: Optional[Dict[int, str]] = None):
        self.program = program
        self.model = model
        self.nested_names = nested_names or {}

    def run(self, block: Block) -> Tuple[List[str], Optional[str]]:
        lines: List[str] = []
        condition: Optional[str] = None

        for instr in block.instructions:
            rendered, cond = self._instruction(instr)
            lines.extend(rendered)
            if cond is not None:
                condition = cond

        if condition is not None:
            lines, condition = _inline_condition(lines, condition)
        return lines, condition

    def _instruction(self, instr: VInstr) -> Tuple[List[str], Optional[str]]:
        op = instr.op
        dest = self._operand(instr, "dest")
        src = self._operand(instr, "src")

        if op in (VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE):
            test = self._reg(src) if src is not None else "<unknown>"
            return [], test if op is VOp.JUMP_IF_TRUE else f"not {test}"

        if op is VOp.JUMP:
            return [], None

        if op is VOp.RETURN:
            value = self._reg(src) if src is not None else ""
            return [f"return {value}".rstrip()], None

        if dest is None and op not in (VOp.STORE_GLOBAL, VOp.STORE_LOCAL,
                                       VOp.NOP, VOp.MOVE):
            return [f"# opcode {instr.opcode} {op.value} operands={instr.operands}"], None

        target = self._reg(dest) if dest is not None else None

        if op is VOp.BINARY:
            return [f"{target} = {target} {instr.spec.symbol} {self._reg(src)}"], None
        if op is VOp.COMPARE:
            # One opcode can cover every comparison by selecting from a table,
            # so the operator comes from the selector rather than the opcode.
            selector = self._operand(instr, "selector")
            symbol = instr.spec.compare_table.get(
                selector if selector is not None else -1, instr.spec.symbol)
            if symbol is None:
                return [f"# opcode {instr.opcode} compare selector={selector}"], None
            other = src if src is not None else self._operand(instr, "range_end")
            if dest is None:
                return [f"# opcode {instr.opcode} compare {symbol} "
                        f"(operands {instr.operands})"], None
            if other is None:
                # The handler compared interpreter fields rather than registers.
                # Naming them keeps the test readable and, crucially, keeps the
                # destination defined so the branch does not read a stale slot.
                left, right = self._compared_fields(instr)
                return [f"{target} = {left} {symbol} {right}"], None
            return [f"{target} = {target} {symbol} {self._reg(other)}"], None
        if op is VOp.BOOL:
            return [f"{target} = {target} {instr.spec.symbol} {self._reg(src)}"], None
        if op is VOp.UNARY:
            symbol = instr.spec.symbol or ""
            spacer = "" if symbol in ("-", "+", "~") else " "
            return [f"{target} = {symbol}{spacer}{target}"], None
        if op is VOp.MOVE:
            return [f"{target} = {self._reg(src)}"], None
        if op is VOp.LOAD_IMM:
            # The operand is a constant-pool index, not the value itself: the
            # interpreter resolves every register read through its decoder, so
            # emitting the raw number turns `open(f, 'r')` into `open(f, 0)`.
            return [f"{target} = {self._const(instr, 'src')}"], None
        if op is VOp.LOAD_CONST:
            return [f"{target} = {self._const(instr, 'name')}"], None
        if op is VOp.LOAD_GLOBAL:
            # The looked-up key is a pool name in most handlers, but some
            # compute it into a register first; the assigned role says which.
            if instr.spec.role_index("name") is not None:
                return [f"{target} = {self._name(instr, 'name')}"], None
            return [f"{target} = globals()[{self._reg(src)}]"], None
        if op is VOp.STORE_GLOBAL:
            name = self._binding(instr, "name")
            source = self._operand(instr, "src")
            return [f"{name} = {self._reg(source if source is not None else dest)}"], None
        if op is VOp.LOAD_ATTR:
            attr = self._name(instr, "name")
            source = self._reg(src if src is not None else dest)
            return [f"{target} = {source}.{attr}" if _identifier(attr)
                    else f"{target} = getattr({source}, {attr!r})"], None
        if op is VOp.IMPORT:
            # A module path is dotted, which is legal here even though it is not
            # a single identifier.
            module = self._pool_entry(instr, "name")
            if module is None or not _module_path(module):
                return [f"# import <unrecovered> as {target}"], None
            return [f"import {module} as {target}"], None
        if op is VOp.CALL:
            # The callee sits in the destination register and its arguments in
            # the registers after it, up to the range bound.
            end = self._operand(instr, "range_end")
            args = self._range(None if dest is None else dest + 1, end)
            return [f"{target} = {target}({args})"], None
        if op is VOp.BUILD_LIST:
            return [f"{target} = [{self._range(dest, self._operand(instr, 'range_end'))}]"], None
        if op is VOp.BUILD_DICT:
            return [f"{target} = {{}}"], None
        if op is VOp.BUILD_SLICE:
            end = self._operand(instr, "range_end")
            return [f"{target} = slice({self._range(dest, end)})"], None
        if op is VOp.SUBSCRIPT:
            index = src if src is not None else self._operand(instr, "range_end")
            return [f"{target} = {target}[{self._reg(index)}]"], None
        if op is VOp.MAKE_VM:
            name = self.nested_names.get(instr.operands[0] if instr.operands else 0)
            return [f"{target} = {name}" if name
                    else f"{target} = <nested program>"], None
        if op is VOp.STORE_LOCAL:
            field = instr.spec.symbol or "vm_state"
            return [f"{_sanitize(field)} = {self._reg(src)}"], None
        if op is VOp.NOP:
            return [], None

        return [f"# opcode {instr.opcode} {op.value} operands={instr.operands}"], None

    def _operand(self, instr: VInstr, role: str) -> Optional[int]:
        position = instr.spec.role_index(role)
        if position is None or position >= len(instr.operands):
            # A handler may always write the same register instead of one the
            # instruction names.
            if role == "dest":
                return instr.spec.fixed_dest
            return None
        return instr.operands[position]

    def _reg(self, index: Optional[int]) -> str:
        return "<unknown>" if index is None else f"r{index}"

    def _range(self, start: Optional[int], stop: Optional[int]) -> str:
        """Registers ``start`` through ``stop`` inclusive, as an argument list."""
        if start is None or stop is None or stop < start:
            return ""
        span = stop - start + 1
        if span > 24:
            return f"*regs[{start}:{stop + 1}]"
        return ", ".join(f"r{i}" for i in range(start, stop + 1))

    def _const(self, instr: VInstr, role: str) -> str:
        index = self._pool_index(instr, role)
        consts = self.program.consts
        if index is not None and 0 <= index < len(consts):
            return repr(consts[index])
        return f"const_{index if index is not None else 'unknown'}"

    def _name(self, instr: VInstr, role: str) -> str:
        """
        Pool entry an operand names, or a placeholder that is still valid Python.

        A missing entry must never render as ``None``: emitting ``None = x``
        turns a partial recovery into a file that will not parse, and an
        unparsable lift is discarded wholesale by the pipeline.
        """
        index = self._pool_index(instr, role)
        names = self.program.names
        if index is not None and 0 <= index < len(names):
            candidate = str(names[index])
            return candidate if _identifier(candidate) else f"name_{index}"
        return f"name_{index if index is not None else 'unknown'}"

    def _compared_fields(self, instr: VInstr) -> Tuple[str, str]:
        """
        Names of the interpreter fields a register-free comparison read.

        Both sides must be renderable as identifiers: a placeholder containing
        punctuation would make the emitted module unparsable, and the pipeline
        discards an unparsable lift wholesale.
        """
        left, right = instr.spec.compare_sources
        return (_sanitize(left) if left else "vm_state_left",
                _sanitize(right) if right else "vm_state_right")

    def _pool_entry(self, instr: VInstr, role: str) -> Optional[str]:
        """Raw name-pool entry, unfiltered — for contexts that accept dotted paths."""
        index = self._pool_index(instr, role)
        names = self.program.names
        if index is not None and 0 <= index < len(names):
            return str(names[index])
        return None

    def _binding(self, instr: VInstr, role: str) -> str:
        """A pool name in assignment position, guaranteed to be assignable."""
        name = self._name(instr, role)
        return name if _identifier(name) else f"name_{self._pool_index(instr, role)}"

    def _pool_index(self, instr: VInstr, role: str) -> Optional[int]:
        """
        Operand indexing a pool, strictly as the handler assigned it.

        Guessing a position when the role is absent produces a confident-looking
        wrong name, which is worse than an honest placeholder.
        """
        return self._operand(instr, role)

def _inline_condition(lines: List[str], condition: str) -> Tuple[List[str], str]:
    """
    Fold the test register's definition into the branch condition.

    A branch tests a register the preceding compare wrote. Leaving that
    definition as its own statement produces ``while r4:`` and, because the loop
    body rewrites the register, no later pass can recover the real test — the
    condition has to be inlined while the definition is still adjacent.
    """
    negated = condition.startswith("not ")
    slot = condition[4:] if negated else condition
    if not _looks_like_slot(slot):
        return lines, condition

    for position in range(len(lines) - 1, -1, -1):
        head, sep, value = lines[position].partition(" = ")
        if not sep or head.strip() != slot:
            continue
        # Only a self-contained expression may move; anything referring to the
        # slot again would change meaning once the definition is removed.
        if slot in value.split():
            return lines, condition
        remaining = lines[:position] + lines[position + 1:]
        rebuilt = f"not ({value})" if negated else value
        return remaining, rebuilt
    return lines, condition

def _looks_like_slot(text: str) -> bool:
    return (text.startswith("r") and len(text) > 1 and text[1:].isdigit())

def _module_path(text: str) -> bool:
    """``Crypto.Cipher`` — a dotted path of identifiers."""
    return bool(text) and all(_identifier(part) for part in text.split("."))

def _identifier(text: str) -> bool:
    """
    Usable as an assignment target.

    A pool entry may decode to a reserved word — ``None`` is a real recovered
    name here — and emitting ``None = x`` makes the whole lift unparsable, so
    keywords are rendered as placeholders instead.
    """
    return bool(text) and text.isidentifier() and not keyword.iskeyword(text)

def _collect_role_names(instrs: List[VInstr], names: List[str], op: VOp) -> Set[str]:
    """Name-pool entries a program's own instructions reach through the ``name`` role."""
    out: Set[str] = set()
    for instr in instrs:
        if instr.op is not op:
            continue
        position = instr.spec.role_index("name")
        if position is None or position >= len(instr.operands):
            continue
        index = instr.operands[position]
        if 0 <= index < len(names):
            out.add(names[index])
    return out

def _compare_field_names(instrs: List[VInstr]) -> Set[str]:
    """
    Field names a COMPARE renders when the handler compared no register.

    Mirrors the condition in :meth:`RegisterBlockLifter._instruction`'s COMPARE
    branch: a destination but no second operand means the handler compared an
    interpreter field, and ``_compared_fields`` names it directly rather than
    through the name pool — so it needs the same free-variable treatment as a
    ``LOAD_GLOBAL`` read, or it renders as a reference nothing ever defines.
    """
    out: Set[str] = set()
    for instr in instrs:
        if instr.op is not VOp.COMPARE:
            continue

        def role(name: str) -> Optional[int]:
            position = instr.spec.role_index(name)
            if position is None or position >= len(instr.operands):
                return None
            return instr.operands[position]

        dest = role("dest")
        if dest is None:
            dest = instr.spec.fixed_dest
        if dest is None:
            continue
        other = role("src")
        if other is None:
            other = role("range_end")
        if other is not None:
            continue

        left, right = instr.spec.compare_sources
        out.add(_sanitize(left) if left else "vm_state_left")
        out.add(_sanitize(right) if right else "vm_state_right")
    return out

def _store_local_names(instrs: List[VInstr]) -> Set[str]:
    """
    Names a STORE_LOCAL writes.

    Unlike STORE_GLOBAL, the target is not a name-pool index but a fixed
    symbol baked into the opcode's own spec (see ``RegisterBlockLifter``'s
    STORE_LOCAL case) — the same opcode number carries the same symbol in
    every program built from this VM class, which is exactly what marks it as
    VM-wide bookkeeping state rather than a per-function local.
    """
    out: Set[str] = set()
    for instr in instrs:
        if instr.op is VOp.STORE_LOCAL:
            out.add(_sanitize(instr.spec.symbol or "vm_state"))
    return out

def _walk_register(program: VProgram):
    yield program
    for nested in program.nested:
        yield from _walk_register(nested)

def _tree_global_names(root: VProgram) -> Tuple[List[str], Dict[int, Set[str]]]:
    """
    Every sibling program in a register-VM tree is a method of the same
    interpreter instance and reaches the same register file through
    ``STORE_GLOBAL``/``LOAD_GLOBAL`` — a name one function only reads may be one
    a sibling function writes, so the free-variable analysis has to see the
    whole tree at once rather than one function's own instructions.

    Returns the names read somewhere but never written anywhere in the tree —
    true free variables, since the recovered payload never assigns them and
    they likely come from ``__init__`` or from a call site outside the
    recovered VM — plus each program's own write-set, keyed by ``id(program)``,
    for that function's ``global`` declaration.
    """
    all_written: Set[str] = set()
    all_read: Set[str] = set()
    writes_by_id: Dict[int, Set[str]] = {}
    for program in _walk_register(root):
        written = _collect_role_names(program.instructions, program.names, VOp.STORE_GLOBAL)
        written |= _store_local_names(program.instructions)
        read = _collect_role_names(program.instructions, program.names, VOp.LOAD_GLOBAL)
        read |= _compare_field_names(program.instructions)
        writes_by_id[id(program)] = written
        all_written |= written
        all_read |= read
    free_names = sorted(
        name for name in (all_read - all_written) if _needs_placeholder(name)
    )
    return free_names, writes_by_id

def _needs_placeholder(name: str) -> bool:
    """
    False for a name Python already provides without help.

    A builtin (``len``, ``print``) resolves through ordinary scoping once it is
    no longer shadowed by a bogus module-level assignment, and a dunder
    (``__file__``, ``__name__``) is set automatically when the module runs —
    declaring either as a free variable would silently override the real
    value instead of recovering a missing one.
    """
    if name.startswith("__") and name.endswith("__"):
        return False
    return not hasattr(builtins, name)

def lift_register_program(program: VProgram, model: VMModel,
                          nested_names: Optional[Dict[int, str]] = None) -> str:
    """
    Render a whole register-VM tree, nested programs first.

    Sibling programs share one register file (see :func:`_tree_global_names`),
    so they are rendered as ordinary functions sharing real Python globals
    rather than as independently-scoped functions that would silently lose a
    value one sibling sets for another to read.
    """
    from de4py.engines.onyx.vm.reconstruct import reconstruct

    free_names, writes_by_id = _tree_global_names(program)
    parts: List[str] = []
    if free_names:
        parts.append("# free variables: read but never assigned anywhere in the recovered VM")
        parts.append("# (likely set by __init__ or by code outside the recovered payload)")
        parts.extend(f"{name} = None" for name in free_names)
        parts.append("")

    parts.append(_render_register_tree(program, model, nested_names or {}, writes_by_id))
    return reconstruct("\n".join(parts))

def _render_register_tree(program: VProgram, model: VMModel,
                          nested_names: Dict[int, str],
                          writes_by_id: Dict[int, Set[str]]) -> str:
    """One program's ``def``, nested programs rendered first, no reconstruct pass."""
    from de4py.engines.onyx.vm.lifter import _body, build_cfg

    blocks = build_cfg(program.instructions, 1)
    lifter = RegisterBlockLifter(program, model, nested_names)

    parts: List[str] = []
    for nested in program.nested:
        parts.append(_render_register_tree(nested, model, nested_names, writes_by_id))
        parts.append("")

    body = _structure(blocks, lifter)
    own_writes = sorted(writes_by_id.get(id(program), ()))
    parts.append(f"def {program.name}():")
    if own_writes:
        parts.extend(_body([f"global {', '.join(own_writes)}"]))
    parts.extend(_body(body))
    return "\n".join(parts)

def _structure(blocks: Dict[int, Block], lifter: RegisterBlockLifter) -> List[str]:
    """
    Rebuild nested Python from the CFG, using dominance to find loops.

    Emitting blocks in offset order is wrong for anything with a back edge: a
    loop body then reads whatever its registers held on the first iteration, so
    a per-character encryption loop prints as a handful of constant-folded
    statements. Dominance identifies the header, which turns the same blocks
    back into a ``while``.
    """
    from de4py.engines.onyx.vm.lifter import (
        _body,
        _dominators,
        _immediate_postdominator,
        _postdominators,
    )

    if not blocks:
        return []

    entry = min(blocks)
    dom = _dominators(blocks, entry)
    pdom = _postdominators(blocks)

    # A back edge n -> h whose target dominates it marks h as a loop header.
    loop_heads = {
        successor
        for start, block in blocks.items()
        for successor in block.successors
        if successor in dom.get(start, set()) and successor <= start
    }

    emitted: Set[int] = set()

    def emit(start: Optional[int], stop: Optional[int], depth: int) -> List[str]:
        out: List[str] = []
        current = start
        guard = 0
        while current is not None and current != stop:
            guard += 1
            if guard > 4000 or depth > 40:
                out.append("# structuring budget exhausted")
                break
            block = blocks.get(current)
            if block is None:
                break
            if current in emitted:
                out.append(f"# jump back to block {current}")
                break
            emitted.add(current)

            lines, condition = lifter.run(block)

            if current in loop_heads and block.kind == "branch" and condition:
                body_start = block.successors[0] if block.successors else None
                exit_start = (block.successors[1]
                              if len(block.successors) > 1 else None)
                out.extend(lines)
                out.append(f"while {_negate(condition)}:")
                out.extend(_body(emit(body_start, current, depth + 1)))
                current = exit_start
                continue

            if block.kind == "branch" and condition:
                join = _immediate_postdominator(current, pdom)
                then_start = block.successors[0] if block.successors else None
                else_start = (block.successors[1]
                              if len(block.successors) > 1 else None)
                out.extend(lines)
                out.append(f"if {_negate(condition)}:")
                out.extend(_body(emit(then_start, join, depth + 1)))
                if else_start is not None and else_start != join:
                    alt = emit(else_start, join, depth + 1)
                    if alt and not all(l.lstrip().startswith("#") for l in alt):
                        out.append("else:")
                        out.extend(_body(alt))
                current = join
                continue

            out.extend(lines)
            if block.kind == "exit" or not block.successors:
                break
            current = block.successors[0]
        return out

    rendered = emit(entry, None, 0)

    # Any block dominance never reached still holds recovered code; appending it
    # keeps the lift complete rather than silently dropping instructions.
    for start in sorted(blocks):
        if start in emitted:
            continue
        lines, condition = lifter.run(blocks[start])
        if lines:
            rendered.append(f"# block {start} (unreached by structuring)")
            rendered.extend(lines)
    return rendered

def _negate(condition: str) -> str:
    """`jump-if-false target` continues while the condition holds."""
    if condition.startswith("not "):
        return condition[4:]
    return f"not ({condition})"

def _structure_linear(blocks: Dict[int, Block],
                      lifter: RegisterBlockLifter) -> List[str]:
    """Offset-ordered fallback, kept for diagnosing a structuring failure."""
    out: List[str] = []
    for start in sorted(blocks):
        block = blocks[start]
        lines, condition = lifter.run(block)
        out.extend(lines)
        if condition is not None:
            targets = block.successors
            out.append(f"# branch: if {condition} -> {targets}")
        elif block.kind == "linear" and block.successors \
                and block.successors != [start + len(block.instructions)]:
            out.append(f"# jump -> {block.successors}")
    return out
