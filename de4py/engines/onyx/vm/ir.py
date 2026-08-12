# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
VM-agnostic intermediate representation.

A lifted virtual instruction is described by *what it does to VM state*, not by
which opcode number carried it, so the same IR serves a stack machine whose
dispatcher is a ``match`` statement and a register machine whose dispatcher is a
tuple of lambdas. Concrete opcode numbers stay in the per-sample opcode table.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class VOp(Enum):
    """Semantic classes a virtual instruction can belong to."""

    LOAD_CONST = "load_const"
    LOAD_LOCAL = "load_local"
    LOAD_GLOBAL = "load_global"
    STORE_LOCAL = "store_local"
    STORE_GLOBAL = "store_global"
    BINARY = "binary"
    UNARY = "unary"
    COMPARE = "compare"
    BOOL = "bool"
    CALL = "call"
    RETURN = "return"
    JUMP = "jump"
    JUMP_IF_FALSE = "jump_if_false"
    JUMP_IF_TRUE = "jump_if_true"
    IMPORT = "import"
    MAKE_VM = "make_vm"
    LOAD_ATTR = "load_attr"
    BUILD_TUPLE = "build_tuple"
    BUILD_LIST = "build_list"
    BUILD_SLICE = "build_slice"
    SUBSCRIPT = "subscript"
    POP = "pop"
    NOP = "nop"
    #: Register machines address operands directly instead of through a stack.
    MOVE = "move"
    LOAD_IMM = "load_imm"
    BUILD_DICT = "build_dict"
    UNKNOWN = "unknown"


#: Operators recovered from handler bodies, keyed by the AST operator class name.
BINARY_SYMBOLS = {
    "Add": "+", "Sub": "-", "Mult": "*", "Div": "/", "FloorDiv": "//",
    "Mod": "%", "Pow": "**", "LShift": "<<", "RShift": ">>", "BitOr": "|",
    "BitXor": "^", "BitAnd": "&", "MatMult": "@",
}

UNARY_SYMBOLS = {"USub": "-", "UAdd": "+", "Not": "not ", "Invert": "~"}

COMPARE_SYMBOLS = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=", "Gt": ">", "GtE": ">=",
    "Is": "is", "IsNot": "is not", "In": "in", "NotIn": "not in",
}


@dataclass
class OpcodeSpec:
    """
    What one opcode number means, recovered from its handler body.

    ``operand_role`` records how the instruction's operand argument is used, which
    is what lets the lifter turn a raw number into a name, a constant index, a
    jump target or an argument count without guessing.
    """

    number: int
    op: VOp = VOp.UNKNOWN
    symbol: Optional[str] = None
    operand_role: str = "none"          # const | name | target | count | selector | none
    compare_table: Dict[int, str] = field(default_factory=dict)
    source: str = ""
    #: Register machines name their operands by role rather than by position:
    #: which operand selects the destination, and which the second source.
    operand_roles: Tuple[str, ...] = ()
    #: Jump targets are often stored scaled (an instruction index rather than a
    #: byte offset); the factor is recovered from the handler, never assumed.
    target_scale: int = 1
    #: Register a handler writes at a fixed index rather than one named by an
    #: operand, e.g. an accumulator the instruction always lands in.
    fixed_dest: Optional[int] = None
    #: Interpreter fields a comparison read when it compared no register, so the
    #: emitted test names real state instead of an undefined slot.
    compare_sources: Tuple[Optional[str], Optional[str]] = (None, None)

    @property
    def is_terminator(self) -> bool:
        return self.op in (VOp.RETURN, VOp.JUMP, VOp.JUMP_IF_FALSE, VOp.JUMP_IF_TRUE)

    def role_index(self, role: str) -> Optional[int]:
        """Position of the operand carrying ``role``, if the handler named one."""
        for index, found in enumerate(self.operand_roles):
            if found == role:
                return index
        return None


@dataclass
class VMModel:
    """The recovered shape of one VM implementation."""

    class_name: str = ""
    opcodes: Dict[int, OpcodeSpec] = field(default_factory=dict)
    instruction_width: int = 2
    operand_count: int = 1
    pc_start: int = 0
    dispatch_kind: str = "match"          # match | table
    payload_order: Tuple[str, ...] = ("bytecode", "consts", "names")
    handler_rotation: int = 0
    #: "stack" machines push and pop; "register" machines address a register file
    #: directly, so a lifted instruction is already three-address code.
    machine: str = "stack"
    #: Number of registers, when the interpreter allocates a fixed file.
    register_count: int = 0
    notes: List[str] = field(default_factory=list)

    def by_op(self, op: VOp) -> List[int]:
        return [n for n, spec in self.opcodes.items() if spec.op is op]

    def first(self, op: VOp) -> Optional[int]:
        found = self.by_op(op)
        return found[0] if found else None

    def coverage(self) -> float:
        if not self.opcodes:
            return 0.0
        known = sum(1 for s in self.opcodes.values() if s.op is not VOp.UNKNOWN)
        return known / len(self.opcodes)


@dataclass
class VInstr:
    """One decoded virtual instruction."""

    offset: int
    opcode: int
    operands: Tuple[int, ...]
    spec: OpcodeSpec

    @property
    def arg(self) -> int:
        return self.operands[0] if self.operands else 0

    @property
    def op(self) -> VOp:
        return self.spec.op


@dataclass
class VProgram:
    """A decoded bytecode body plus the pools it indexes into."""

    name: str
    instructions: List[VInstr]
    consts: List[Any]
    names: List[str]
    params: List[str] = field(default_factory=list)
    nested: List["VProgram"] = field(default_factory=list)

    def offsets(self) -> Dict[int, int]:
        return {instr.offset: i for i, instr in enumerate(self.instructions)}


@dataclass
class Block:
    """A basic block: straight-line instructions with a single entry point."""

    start: int
    instructions: List[VInstr] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    #: Filled by the lifter — rendered source lines for this block.
    lines: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    kind: str = "linear"                  # linear | branch | loop_head | exit

    @property
    def end(self) -> int:
        return self.instructions[-1].offset if self.instructions else self.start
