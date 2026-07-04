# de4py - Onyx Engine
# IR Optimization Passes

from ..ir.graph import CFG
from ..ir.instructions import (
    Assign, BinaryOp, UnaryOp, Compare, BoolOp, Call,
    Branch, Jump, GetItem, SetItem, OpaqueExpr
)
from ..ir.values import Constant, Variable


class OptimizerPass:
    def run(self, cfg: CFG) -> bool:
        """Returns True if any changes were made."""
        return False


class ConstantFolder(OptimizerPass):
    """Folds BinaryOp/UnaryOp/Compare with all-constant operands."""

    def run(self, cfg: CFG) -> bool:
        changed = False
        for block in cfg.blocks.values():
            for i, instr in enumerate(block.instructions):
                result = None
                if isinstance(instr, BinaryOp):
                    if isinstance(instr.left, Constant) and isinstance(instr.right, Constant):
                        try:
                            val = eval(f"{repr(instr.left.value)} {instr.op} {repr(instr.right.value)}")
                            result = Assign(instr.target, Constant(val))
                        except Exception:
                            pass
                elif isinstance(instr, UnaryOp):
                    if isinstance(instr.operand, Constant):
                        try:
                            val = eval(f"{instr.op} {repr(instr.operand.value)}")
                            result = Assign(instr.target, Constant(val))
                        except Exception:
                            pass
                elif isinstance(instr, Compare):
                    if isinstance(instr.left, Constant) and isinstance(instr.right, Constant):
                        try:
                            val = eval(f"{repr(instr.left.value)} {instr.op} {repr(instr.right.value)}")
                            result = Assign(instr.target, Constant(val))
                        except Exception:
                            pass
                if result:
                    block.instructions[i] = result
                    changed = True
        return changed


class ConstantPropagation(OptimizerPass):
    """
    Propagates constant-assigned variables forward within each block.
    Replaces Variable refs with Constant when the variable has a known value.
    """

    def run(self, cfg: CFG) -> bool:
        changed = False
        for block in cfg.blocks.values():
            const_map: dict[str, Constant] = {}
            for instr in block.instructions:
                # Propagate into instruction operands
                changed |= self._subst(instr, const_map)
                # Record new constant assignments
                if isinstance(instr, Assign) and isinstance(instr.value, Constant):
                    const_map[str(instr.target)] = instr.value
                # Any other assignment to this var invalidates it
                elif isinstance(instr, Assign):
                    const_map.pop(str(instr.target), None)
        return changed

    def _subst(self, instr, cm: dict) -> bool:
        changed = False
        for attr in ('left', 'right', 'value', 'operand', 'condition',
                     'func', 'obj', 'key', 'iterable', 'exc', 'test'):
            v = getattr(instr, attr, None)
            if isinstance(v, Variable) and str(v) in cm:
                setattr(instr, attr, cm[str(v)])
                changed = True
        if isinstance(instr, Call) and instr.args:
            for j, a in enumerate(instr.args):
                if isinstance(a, Variable) and str(a) in cm:
                    instr.args[j] = cm[str(a)]
                    changed = True
        if hasattr(instr, 'values') and instr.values:
            for j, v in enumerate(instr.values):
                if isinstance(v, Variable) and str(v) in cm:
                    instr.values[j] = cm[str(v)]
                    changed = True
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
            for b in cfg.blocks.values():
                b.predecessors.discard(bid)
        return len(to_remove) > 0
