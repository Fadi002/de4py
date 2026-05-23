# de4py - Onyx Engine
# IR Optimization Passes

from ..ir.graph import CFG
from ..ir.instructions import Assign, BinaryOp, UnaryOp, Branch, Jump
from ..ir.values import Constant, Variable

class OptimizerPass:
    def run(self, cfg: CFG) -> bool:
        """Returns True if any changes were made."""
        pass

class ConstantFolder(OptimizerPass):
    def run(self, cfg: CFG) -> bool:
        changed = False
        for block in cfg.blocks.values():
            for i, instr in enumerate(block.instructions):
                if isinstance(instr, BinaryOp):
                    if isinstance(instr.left, Constant) and isinstance(instr.right, Constant):
                        try:
                            # Evaluate simple arithmetic
                            val = eval(f"{repr(instr.left.value)} {instr.op} {repr(instr.right.value)}")
                            block.instructions[i] = Assign(instr.target, Constant(val))
                            changed = True
                        except Exception:
                            pass
        return changed

class DeadBlockElimination(OptimizerPass):
    def run(self, cfg: CFG) -> bool:
        reachable = {cfg.entry_block_id}
        stack = [cfg.entry_block_id]

        while stack:
            bid = stack.pop()
            for succ in cfg.blocks[bid].successors:
                if succ not in reachable:
                    reachable.add(succ)
                    stack.append(succ)

        to_remove = [bid for bid in cfg.blocks if bid not in reachable]
        for bid in to_remove:
            del cfg.blocks[bid]
            # Clean up predecessor sets
            for b in cfg.blocks.values():
                b.predecessors.discard(bid)

        return len(to_remove) > 0
