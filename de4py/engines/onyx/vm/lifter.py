# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Bytecode -> IR -> structured Python.

Three stages:

1. **Decode.** Split the flat instruction stream using the width recovered by
   discovery, resolving each operand through the role its handler assigned it.
2. **CFG.** Cut basic blocks at jump targets and after branches, then compute
   dominators and post-dominators. Loops come from back edges (a branch whose
   target dominates it); an ``if``'s join point is the branch's immediate
   post-dominator.
3. **Emit.** Execute each block over a symbolic stack, threading the entry stack
   between blocks as a dataflow fact, and render structured Python.

The symbolic stack is what recovers statements a naive lifter loses: a call whose
result is pushed and never consumed is a discarded-result expression statement,
so it is flushed rather than dropped.
"""

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from de4py.engines.onyx.vm.ir import Block, VInstr, VMModel, VOp, VProgram

MAX_BLOCKS = 4000
MAX_EMIT_DEPTH = 60

def decode(code: Sequence[int], model: VMModel) -> List[VInstr]:
    width = max(1, model.instruction_width)
    operands = max(0, min(model.operand_count, width - 1))
    out: List[VInstr] = []
    offset = 0
    while offset + width <= len(code):
        opcode = code[offset]
        args = tuple(code[offset + 1 + i] for i in range(operands))
        spec = model.opcodes.get(opcode)
        if spec is None:
            from de4py.engines.onyx.vm.ir import OpcodeSpec
            spec = OpcodeSpec(number=opcode, op=VOp.UNKNOWN)
        out.append(VInstr(offset=offset, opcode=opcode, operands=args, spec=spec))
        offset += width
    return out

def build_cfg(instrs: List[VInstr], width: int) -> Dict[int, Block]:
    if not instrs:
        return {}
    by_offset = {i.offset: i for i in instrs}
    valid = set(by_offset)

    leaders: Set[int] = {instrs[0].offset}
    for index, instr in enumerate(instrs):
        nxt = instrs[index + 1].offset if index + 1 < len(instrs) else None
        if instr.op in (VOp.JUMP, VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE):
            target = instr.arg
            if target in valid:
                leaders.add(target)
            if instr.op is not VOp.JUMP and nxt is not None:
                leaders.add(nxt)
        elif instr.op is VOp.RETURN and nxt is not None:
            leaders.add(nxt)

    ordered = sorted(leaders)
    blocks: Dict[int, Block] = {}
    for position, start in enumerate(ordered):
        end = ordered[position + 1] if position + 1 < len(ordered) else None
        body = [i for i in instrs
                if i.offset >= start and (end is None or i.offset < end)]
        if not body:
            continue
        block = Block(start=start, instructions=body)
        last = body[-1]
        fallthrough = end
        if last.op is VOp.JUMP:
            if last.arg in valid:
                block.successors = [last.arg]
            block.kind = "linear"
        elif last.op in (VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE):
            block.kind = "branch"
            succ = []
            if fallthrough is not None:
                succ.append(fallthrough)
            if last.arg in valid:
                succ.append(last.arg)
            block.successors = succ
        elif last.op is VOp.RETURN:
            block.kind = "exit"
        elif fallthrough is not None:
            block.successors = [fallthrough]
        blocks[start] = block
    return blocks

def _dominators(blocks: Dict[int, Block], entry: int) -> Dict[int, Set[int]]:
    nodes = set(blocks)
    dom = {n: set(nodes) for n in nodes}
    dom[entry] = {entry}
    preds: Dict[int, List[int]] = {n: [] for n in nodes}
    for n, block in blocks.items():
        for s in block.successors:
            if s in preds:
                preds[s].append(n)
    changed = True
    guard = 0
    while changed and guard < 200:
        guard += 1
        changed = False
        for n in sorted(nodes):
            if n == entry:
                continue
            incoming = [dom[p] for p in preds[n] if p in dom]
            new = set(nodes) if not incoming else set.intersection(*incoming)
            new = new | {n}
            if new != dom[n]:
                dom[n] = new
                changed = True
    return dom

def _postdominators(blocks: Dict[int, Block]) -> Dict[int, Set[int]]:
    nodes = set(blocks)
    exits = [n for n, b in blocks.items() if not b.successors or b.kind == "exit"]
    pdom = {n: set(nodes) for n in nodes}
    for e in exits:
        pdom[e] = {e}
    changed = True
    guard = 0
    while changed and guard < 200:
        guard += 1
        changed = False
        for n in sorted(nodes, reverse=True):
            if n in exits:
                continue
            succs = [pdom[s] for s in blocks[n].successors if s in pdom]
            new = set(nodes) if not succs else set.intersection(*succs)
            new = new | {n}
            if new != pdom[n]:
                pdom[n] = new
                changed = True
    return pdom

def _immediate_postdominator(node: int, pdom: Dict[int, Set[int]]) -> Optional[int]:
    candidates = pdom.get(node, set()) - {node}
    if not candidates:
        return None
    # The immediate post-dominator is the candidate post-dominated by all others.
    for c in sorted(candidates):
        if all(c in pdom.get(other, set()) or c == other for other in candidates):
            return c
    return min(candidates)

class _Value:
    """A symbolic stack entry: rendered text plus whether it has side effects."""

    __slots__ = ("text", "effectful")

    def __init__(self, text: str, effectful: bool = False):
        self.text = text
        self.effectful = effectful

    def __repr__(self):
        return f"<{self.text}>"

def _fmt_const(value: Any) -> str:
    if isinstance(value, bytes) and len(value) > 40:
        return f"<nested vm: {len(value)} bytes>"
    try:
        return repr(value)
    except Exception:
        return "<const>"

class BlockLifter:
    """Executes one block over the symbolic stack and renders its statements."""

    def __init__(self, program: VProgram, model: VMModel, nested_names: Dict[int, str]):
        self.program = program
        self.model = model
        self.nested_names = nested_names

    def run(self, block: Block, entry_stack: List[_Value]) -> Tuple[List[str], List[_Value], Optional[str]]:
        stack: List[_Value] = list(entry_stack)
        lines: List[str] = []
        condition: Optional[str] = None

        def push(value: _Value):
            stack.append(value)

        def pop() -> _Value:
            return stack.pop() if stack else _Value("<underflow>")

        def flush_effects():
            """
            Emit calls whose results nobody consumed.

            Only valid at a statement boundary: once this instruction has taken
            its own operands off the stack, anything still holding a side effect
            was produced by an earlier statement and is therefore a
            discarded-result expression. Flushing on every load instead would
            wrongly emit values that the *next* instruction still needs.
            """
            if not any(v.effectful for v in stack):
                return
            for value in stack:
                if value.effectful:
                    lines.append(value.text)
            stack[:] = [v for v in stack if not v.effectful]

        for instr in block.instructions:
            op = instr.op
            role = instr.spec.operand_role

            if op is VOp.LOAD_CONST:
                push(_Value(_fmt_const(self._const(instr.arg))))
            elif op in (VOp.LOAD_LOCAL, VOp.LOAD_GLOBAL):
                push(_Value(self._name(instr.arg)))
            elif op in (VOp.STORE_LOCAL, VOp.STORE_GLOBAL):
                value = pop()
                flush_effects()
                lines.append(f"{self._name(instr.arg)} = {value.text}")
            elif op is VOp.BINARY:
                right, left = pop(), pop()
                push(_Value(f"({left.text} {instr.spec.symbol} {right.text})"))
            elif op is VOp.BOOL:
                right, left = pop(), pop()
                push(_Value(f"({left.text} {instr.spec.symbol} {right.text})"))
            elif op is VOp.UNARY:
                value = pop()
                push(_Value(f"({instr.spec.symbol}{value.text})"))
            elif op is VOp.COMPARE:
                right, left = pop(), pop()
                symbol = instr.spec.compare_table.get(instr.arg, instr.spec.symbol or "==")
                push(_Value(f"({left.text} {symbol} {right.text})"))
            elif op is VOp.CALL:
                count = instr.arg if role == "count" else 0
                args = [pop().text for _ in range(count)][::-1]
                func = pop()
                push(_Value(f"{func.text}({', '.join(args)})", effectful=True))
            elif op is VOp.LOAD_ATTR:
                attr, obj = pop(), pop()
                literal = attr.text.strip("'\"")
                if literal.isidentifier():
                    push(_Value(f"{obj.text}.{literal}"))
                else:
                    push(_Value(f"getattr({obj.text}, {attr.text})"))
            elif op is VOp.SUBSCRIPT:
                index, obj = pop(), pop()
                push(_Value(f"{obj.text}[{index.text}]"))
            elif op is VOp.BUILD_SLICE:
                step, stop, start = pop(), pop(), pop()
                text = f"{'' if start.text == 'None' else start.text}:" \
                       f"{'' if stop.text == 'None' else stop.text}"
                if step.text != "None":
                    text += f":{step.text}"
                push(_Value(text))
            elif op is VOp.BUILD_TUPLE:
                items = [pop().text for _ in range(instr.arg)][::-1]
                push(_Value(f"({', '.join(items)}{',' if len(items) == 1 else ''})"))
            elif op is VOp.BUILD_LIST:
                items = [pop().text for _ in range(instr.arg)][::-1]
                push(_Value(f"[{', '.join(items)}]"))
            elif op is VOp.IMPORT:
                flush_effects()
                name = self._name(instr.arg)
                lines.append(f"import {name}")
            elif op is VOp.MAKE_VM:
                pop()
                flush_effects()
                name = self._name(instr.arg)
                lines.append(f"# {name}() is defined above (lifted from a nested VM)")
            elif op is VOp.RETURN:
                value = pop()
                flush_effects()
                lines.append(f"return {value.text}")
            elif op in (VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE):
                condition = pop().text
                if op is VOp.JUMP_IF_FALSE:
                    condition = f"not {condition}"
            elif op is VOp.JUMP:
                pass
            elif op is VOp.POP:
                flush_effects()
                if stack:
                    stack.pop()
            elif op is VOp.NOP:
                pass
            else:
                lines.append(f"# unrecognised opcode {instr.opcode} operand={instr.arg}")

        if block.kind != "branch":
            flush_effects()
        return lines, stack, condition

    def _const(self, index: int) -> Any:
        consts = self.program.consts
        return consts[index] if 0 <= index < len(consts) else f"<const {index}>"

    def _name(self, index: int) -> str:
        names = self.program.names
        return names[index] if 0 <= index < len(names) else f"name_{index}"

class Structurer:
    """Turns the CFG back into nested Python using dominance information."""

    def __init__(self, program: VProgram, model: VMModel, blocks: Dict[int, Block],
                 nested_names: Dict[int, str]):
        self.program = program
        self.model = model
        self.blocks = blocks
        self.lifter = BlockLifter(program, model, nested_names)
        self.entry = min(blocks) if blocks else 0
        self.dom = _dominators(blocks, self.entry) if blocks else {}
        self.pdom = _postdominators(blocks) if blocks else {}
        self.loop_heads = self._find_loops()
        self.emitted: Set[int] = set()

    def _find_loops(self) -> Dict[int, Set[int]]:
        """A back edge n -> h where h dominates n marks h as a loop header."""
        loops: Dict[int, Set[int]] = {}
        for n, block in self.blocks.items():
            for s in block.successors:
                if s in self.dom.get(n, set()) and s <= n:
                    loops.setdefault(s, set()).add(n)
        return loops

    def emit(self) -> List[str]:
        if not self.blocks:
            return []
        return self._emit_from(self.entry, stop=None, stack=[], depth=0)

    def _emit_from(self, start: Optional[int], stop: Optional[int],
                   stack: List[_Value], depth: int) -> List[str]:
        out: List[str] = []
        current = start
        guard = 0
        while current is not None and current != stop:
            guard += 1
            if guard > MAX_BLOCKS or depth > MAX_EMIT_DEPTH:
                out.append("# structuring budget exhausted")
                break
            block = self.blocks.get(current)
            if block is None:
                break
            if current in self.emitted:
                out.append(f"# jump back to block {current}")
                break
            self.emitted.add(current)

            is_loop = current in self.loop_heads
            lines, stack, condition = self.lifter.run(block, stack)

            if is_loop and block.kind == "branch":
                # `while <cond>:` — body is the fallthrough, exit is the target.
                body_start = block.successors[0] if block.successors else None
                exit_start = block.successors[1] if len(block.successors) > 1 else None
                out.extend(lines)
                out.append(f"while {self._invert(condition)}:")
                body = self._emit_from(body_start, stop=current, stack=list(stack),
                                       depth=depth + 1)
                out.extend(_body(body))
                current = exit_start
                continue

            if block.kind == "branch" and condition is not None:
                join = _immediate_postdominator(current, self.pdom)
                succ = block.successors
                then_start = succ[0] if succ else None
                else_start = succ[1] if len(succ) > 1 else None
                out.extend(lines)
                out.append(f"if {self._invert(condition)}:")
                then_body = self._emit_from(then_start, stop=join, stack=list(stack),
                                            depth=depth + 1)
                out.extend(_body(then_body))
                if else_start is not None and else_start != join:
                    else_body = self._emit_from(else_start, stop=join,
                                                stack=list(stack), depth=depth + 1)
                    if else_body and not all(
                        line.lstrip().startswith("#") for line in else_body
                    ):
                        out.append("else:")
                        out.extend(_body(else_body))
                current = join
                continue

            out.extend(lines)
            if block.kind == "exit" or not block.successors:
                break
            current = block.successors[0]
        return out

    @staticmethod
    def _invert(condition: Optional[str]) -> str:
        if condition is None:
            return "True"
        # `jump-if-false target` means "continue when the condition holds".
        if condition.startswith("not "):
            return condition[4:]
        return f"not ({condition})"

def _indent(lines: List[str]) -> List[str]:
    return [f"    {line}" for line in lines]

def _body(lines: List[str]) -> List[str]:
    """Indent a suite, keeping it syntactically valid when it is comments only."""
    if not lines or all(line.lstrip().startswith("#") for line in lines):
        return _indent(list(lines) + ["pass"])
    return _indent(lines)

def lift_program(program: VProgram, model: VMModel,
                 nested_names: Optional[Dict[int, str]] = None) -> str:
    """Render one decoded program as a Python function."""
    blocks = build_cfg(program.instructions, model.instruction_width)
    structurer = Structurer(program, model, blocks, nested_names or {})
    body = structurer.emit()

    parts: List[str] = []
    for nested in program.nested:
        parts.append(lift_program(nested, model))
        parts.append("")

    signature = f"def {program.name}({', '.join(program.params)}):"
    parts.append(signature)
    parts.extend(_body(body))
    return "\n".join(parts)
