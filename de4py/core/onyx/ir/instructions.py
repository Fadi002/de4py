# de4py - Onyx Engine
# IR Instructions Definition

from abc import ABC, abstractmethod
from typing import List, Optional, Any
from .values import Variable

class Instruction(ABC):
    """Abstract base class for all IR instructions."""
    def __init__(self):
        self.metadata = {}

    @abstractmethod
    def __repr__(self):
        pass

class Assign(Instruction):
    """target = value"""
    def __init__(self, target: Variable, value: Any):
        super().__init__()
        self.target = target
        self.value = value

    def __repr__(self):
        return f"{self.target} = {self.value}"

class BinaryOp(Instruction):
    """target = left op right"""
    def __init__(self, target: Variable, left: Any, op: str, right: Any):
        super().__init__()
        self.target = target
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"{self.target} = {self.left} {self.op} {self.right}"

class UnaryOp(Instruction):
    """target = op operand"""
    def __init__(self, target: Variable, op: str, operand: Any):
        super().__init__()
        self.target = target
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"{self.target} = {self.op}{self.operand}"

class Call(Instruction):
    """target = func(*args)"""
    def __init__(self, target: Optional[Variable], func: Any, args: List[Any]):
        super().__init__()
        self.target = target
        self.func = func
        self.args = args

    def __repr__(self):
        res = f"{self.target} = " if self.target else ""
        return f"{res}{self.func}({', '.join(map(str, self.args))})"

class Jump(Instruction):
    """Unconditional jump to a block"""
    def __init__(self, target_block_id: int):
        super().__init__()
        self.target_block_id = target_block_id

    def __repr__(self):
        return f"jump B{self.target_block_id}"

class Branch(Instruction):
    """Conditional jump"""
    def __init__(self, condition: Any, true_block_id: int, false_block_id: int):
        super().__init__()
        self.condition = condition
        self.true_block_id = true_block_id
        self.false_block_id = false_block_id

    def __repr__(self):
        return f"if {self.condition} jump B{self.true_block_id} else B{self.false_block_id}"

class Return(Instruction):
    """Return value"""
    def __init__(self, value: Optional[Any]):
        super().__init__()
        self.value = value

    def __repr__(self):
        return f"return {self.value}"

class LoadAttr(Instruction):
    """target = obj.attr"""
    def __init__(self, target: Variable, obj: Any, attr: str):
        super().__init__()
        self.target = target
        self.obj = obj
        self.attr = attr

    def __repr__(self):
        return f"{self.target} = {self.obj}.{self.attr}"

class StoreAttr(Instruction):
    """obj.attr = value"""
    def __init__(self, obj: Any, attr: str, value: Any):
        super().__init__()
        self.obj = obj
        self.attr = attr
        self.value = value

    def __repr__(self):
        return f"{self.obj}.{self.attr} = {self.value}"
