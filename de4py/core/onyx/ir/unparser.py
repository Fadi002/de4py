# de4py - Onyx Engine
# IR to Python Source Unparser

from ..ir.graph import CFG
from ..ir.instructions import (
    Jump, Branch
)

class IR_Unparser:
    def unparse(self, cfg: CFG, debug: bool = False) -> str:
        # Very basic linearized unparsing for Milestone 1.
        # This will be replaced by a proper structured flow reconstructor later.
        lines = []
        for bid in sorted(cfg.blocks.keys()):
            block = cfg.blocks[bid]
            if debug:
                lines.append(f"# Block B{bid}")
            for instr in block.instructions:
                if isinstance(instr, (Jump, Branch)):
                    if debug:
                        lines.append(f"# {instr}")
                else:
                    lines.append(str(instr))
        return "\n".join(lines)
