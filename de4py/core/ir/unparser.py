# de4py - Onyx Engine
# IR to Python Source Unparser (structured CFG reconstruction)

from ..ir.graph import CFG, BasicBlock
from ..ir.instructions import (
    Assign, BinaryOp, UnaryOp, Compare, BoolOp, Call,
    GetItem, SetItem, BuildSlice, BuildTuple, BuildList, OpaqueExpr,
    Jump, Branch, ForIter, Return, Raise, Assert,
    Import, ImportFrom, LoadAttr, StoreAttr, FuncDef, Instruction
)


class IR_Unparser:
    def unparse(self, cfg: CFG, debug: bool = False) -> str:
        lines: list[str] = []
        self._cfg = cfg
        self._debug = debug
        self._emit_block(cfg.entry_block_id, set(), lines, 0, stop=-1, loop_exit=-1)
        return "\n".join(lines)

    def _pfx(self, n): return "    " * n

    def _reachable(self, start: int) -> set[int]:
        seen, stack = set(), [start]
        while stack:
            b = stack.pop()
            if b in seen or b not in self._cfg.blocks: continue
            seen.add(b)
            stack.extend(self._cfg.blocks[b].successors)
        return seen

    def _loops_back_to(self, start: int, target: int) -> bool:
        seen, stack = set(), [start]
        while stack:
            b = stack.pop()
            if b == target: return True
            if b in seen or b not in self._cfg.blocks: continue
            seen.add(b)
            stack.extend(self._cfg.blocks[b].successors)
        return False

    def _terminates(self, bid: int, seen: frozenset = frozenset()) -> bool:
        if bid in seen or bid not in self._cfg.blocks: return True
        seen = seen | {bid}
        last = self._cfg.blocks[bid].instructions
        if not last: return False
        last = last[-1]
        if isinstance(last, (Return, Raise)): return True
        if isinstance(last, Jump): return self._terminates(last.target_block_id, seen)
        if isinstance(last, Branch):
            return (self._terminates(last.true_block_id, seen) and
                    self._terminates(last.false_block_id, seen))
        return False

    def _join_of(self, a: int, b: int) -> int:
        ra, rb = self._reachable(a), self._reachable(b)
        common = ra & rb
        return min(common) if common else -1

    def _emit_block(self, bid: int, visited: set, lines: list,
                    indent: int, stop: int, loop_exit: int):
        if bid in visited or bid == stop or bid not in self._cfg.blocks:
            return
        visited.add(bid)
        block = self._cfg.blocks[bid]
        pfx = self._pfx(indent)

        if self._debug:
            lines.append(f"{pfx}# Block B{bid}")

        instrs = block.instructions
        if not instrs:
            for s in sorted(block.successors):
                self._emit_block(s, visited, lines, indent, stop, loop_exit)
            return

        last = instrs[-1]

        if isinstance(last, Branch):
            for instr in instrs[:-1]:
                self._emit_instr(instr, lines, pfx, indent, loop_exit)
            self._emit_branch(last, bid, visited, lines, indent, stop, loop_exit)

        elif isinstance(last, ForIter):
            for instr in instrs[:-1]:
                self._emit_instr(instr, lines, pfx, indent, loop_exit)
            self._emit_for(last, visited, lines, indent, stop, loop_exit)

        elif isinstance(last, Jump):
            for instr in instrs[:-1]:
                self._emit_instr(instr, lines, pfx, indent, loop_exit)
            t = last.target_block_id
            if t == loop_exit:
                lines.append(f"{pfx}break")
            elif t in visited:
                if self._debug: lines.append(f"{pfx}# back-edge B{t}")
                # Implicit continue (loop back) — no emit needed
            else:
                self._emit_block(t, visited, lines, indent, stop, loop_exit)

        else:
            for instr in instrs:
                self._emit_instr(instr, lines, pfx, indent, loop_exit)
            for s in sorted(block.successors):
                self._emit_block(s, visited, lines, indent, stop, loop_exit)

    def _is_while(self, header_id: int, true_id: int) -> bool:
        """True iff the true branch contains a block that directly Jump()s back to header_id."""
        for bid in self._reachable(true_id):
            blk = self._cfg.blocks.get(bid)
            if not blk or not blk.instructions: continue
            last = blk.instructions[-1]
            if isinstance(last, Jump) and last.target_block_id == header_id:
                return True
        return False

    def _emit_branch(self, br: Branch, header_id: int,
                     visited: set, lines: list, indent: int, stop: int, loop_exit: int):
        pfx = self._pfx(indent)
        t, f = br.true_block_id, br.false_block_id

        # While pattern: some block reachable from true body directly Jump()s back to header.
        # (If inside a loop satisfies _loops_back_to but NOT _is_while since the
        #  path goes through a ForIter, not a direct Jump.)
        if self._is_while(header_id, t):
            lines.append(f"{pfx}while {br.condition}:")
            inner = set(visited)
            self._emit_block(t, inner, lines, indent + 1, stop=f, loop_exit=f)
            visited.update(inner)
            self._emit_block(f, visited, lines, indent, stop, loop_exit)
            return

        # If-only: true branch is a simple terminator (return/raise/break).
        # Use len(reachable) <= 2 heuristic: t + at most one exit block.
        if self._terminates(t) and len(self._reachable(t)) <= 2:
            lines.append(f"{pfx}if {br.condition}:")
            inner = set(visited)
            self._emit_block(t, inner, lines, indent + 1, stop, loop_exit)
            visited.update(inner)
            self._emit_block(f, visited, lines, indent, stop, loop_exit)
            return

        # Standard if(-else) with join
        join = self._join_of(t, f)
        lines.append(f"{pfx}if {br.condition}:")
        inner_t = set(visited)
        self._emit_block(t, inner_t, lines, indent + 1,
                         stop=join if join >= 0 else stop, loop_exit=loop_exit)

        f_block = self._cfg.blocks.get(f)
        f_has_content = (f_block and f not in visited and f != join and
                         any(not isinstance(i, Jump) for i in f_block.instructions))
        if f_has_content:
            lines.append(f"{pfx}else:")
            inner_f = set(visited) | inner_t
            self._emit_block(f, inner_f, lines, indent + 1,
                             stop=join if join >= 0 else stop, loop_exit=loop_exit)
            visited.update(inner_f)

        visited.update(inner_t)
        if join >= 0 and join != stop:
            self._emit_block(join, visited, lines, indent, stop, loop_exit)

    def _emit_for(self, fi: ForIter, visited: set, lines: list, indent: int, stop: int, outer_loop_exit: int = -1):
        pfx = self._pfx(indent)
        lines.append(f"{pfx}for {fi.target} in {fi.iterable}:")
        inner = set(visited)
        self._emit_block(fi.body_block_id, inner, lines, indent + 1,
                         stop=fi.exit_block_id, loop_exit=fi.exit_block_id)
        visited.update(inner)
        if fi.exit_block_id >= 0 and fi.exit_block_id != stop:
            self._emit_block(fi.exit_block_id, visited, lines, indent, stop, loop_exit=outer_loop_exit)

    def _fmt_value(self, v) -> str:
        return str(v)

    def _emit_instr(self, instr: Instruction, lines: list, pfx: str,
                    indent: int, loop_exit: int):
        if isinstance(instr, FuncDef):
            args = ", ".join(instr.args)
            lines.append(f"{pfx}def {instr.name}({args}):")
            sub = IR_Unparser()
            sub._cfg = instr.cfg
            sub._debug = self._debug
            body: list[str] = []
            sub._emit_block(instr.cfg.entry_block_id, set(), body, indent + 1,
                            stop=-1, loop_exit=-1)
            lines.extend(body) if body else lines.append(f"{pfx}    pass")
        elif isinstance(instr, (Jump, Branch, ForIter)):
            if self._debug: lines.append(f"{pfx}# {instr}")
        elif isinstance(instr, BuildSlice):
            # Don't emit BuildSlice standalone — it's used inline in GetItem
            pass
        else:
            lines.append(f"{pfx}{instr}")
