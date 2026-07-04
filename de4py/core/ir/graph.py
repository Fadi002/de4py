# de4py - Onyx Engine
# IR CFG Graph Definition

from typing import List, Dict, Set, Optional
from .instructions import Instruction

class BasicBlock:
    """A sequence of instructions with one entry and one exit point."""
    def __init__(self, id: int):
        self.id = id
        self.instructions: List[Instruction] = []
        self.predecessors: Set[int] = set()
        self.successors: Set[int] = set()

    def add_instruction(self, instr: Instruction):
        self.instructions.append(instr)

    def __repr__(self):
        instrs = "\n    ".join(map(str, self.instructions))
        return f"Block B{self.id}:\n    {instrs}"

class CFG:
    """Control Flow Graph representing a function or code block."""
    def __init__(self, name: str = "root"):
        self.name = name
        self.blocks: Dict[int, BasicBlock] = {}
        self.entry_block_id: int = 0
        self.exit_block_id: Optional[int] = None
        self._next_block_id = 0

    def create_block(self) -> BasicBlock:
        block = BasicBlock(self._next_block_id)
        self.blocks[block.id] = block
        self._next_block_id += 1
        return block

    def add_edge(self, from_id: int, to_id: int):
        if from_id in self.blocks and to_id in self.blocks:
            self.blocks[from_id].successors.add(to_id)
            self.blocks[to_id].predecessors.add(from_id)

    def __repr__(self):
        res = [f"CFG: {self.name}"]
        for bid in sorted(self.blocks.keys()):
            res.append(str(self.blocks[bid]))
        return "\n".join(res)
