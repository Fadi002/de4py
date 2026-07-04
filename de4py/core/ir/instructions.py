# de4py - Onyx Engine
# IR Instructions Definition

from abc import ABC, abstractmethod
from typing import List, Optional, Any
from .values import Value, Variable


class Instruction(ABC):
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
    def __init__(self, target, left, op: str, right):
        super().__init__()
        self.target = target
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"{self.target} = {self.left} {self.op} {self.right}"


class UnaryOp(Instruction):
    """target = op operand"""
    def __init__(self, target, op: str, operand):
        super().__init__()
        self.target = target
        self.op = op
        self.operand = operand

    def __repr__(self):
        return f"{self.target} = {self.op} {self.operand}"


class Compare(Instruction):
    """target = left op right (comparison)"""
    def __init__(self, target, left, op: str, right):
        super().__init__()
        self.target = target
        self.left = left
        self.op = op
        self.right = right

    def __repr__(self):
        return f"{self.target} = {self.left} {self.op} {self.right}"


class BoolOp(Instruction):
    """target = v1 op v2 op ... (and/or)"""
    def __init__(self, target, op: str, values: list):
        super().__init__()
        self.target = target
        self.op = op
        self.values = values

    def __repr__(self):
        joined = f" {self.op} ".join(str(v) for v in self.values)
        return f"{self.target} = {joined}"


class Call(Instruction):
    """target = func(*args, **kwargs)"""
    def __init__(self, target: Optional[Variable], func: Any, args: List[Any],
                 kwargs: Optional[dict] = None):
        super().__init__()
        self.target = target
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}

    def __repr__(self):
        parts = [str(a) for a in self.args]
        parts += [f"{k}={v}" for k, v in self.kwargs.items()]
        call = f"{self.func}({', '.join(parts)})"
        return f"{self.target} = {call}" if self.target else call


class GetItem(Instruction):
    """target = obj[key]"""
    def __init__(self, target, obj, key):
        super().__init__()
        self.target = target
        self.obj = obj
        self.key = key

    def __repr__(self):
        return f"{self.target} = {self.obj}[{self.key}]"


class SetItem(Instruction):
    """obj[key] = value"""
    def __init__(self, obj, key, value):
        super().__init__()
        self.obj = obj
        self.key = key
        self.value = value

    def __repr__(self):
        return f"{self.obj}[{self.key}] = {self.value}"


class BuildSlice(Instruction):
    """target = slice(lower, upper, step)"""
    def __init__(self, target, lower, upper, step):
        super().__init__()
        self.target = target
        self.lower = lower
        self.upper = upper
        self.step = step

    def __repr__(self):
        lo = "" if str(self.lower) == "None" else str(self.lower)
        hi = "" if str(self.upper) == "None" else str(self.upper)
        st = "" if str(self.step) == "None" else f":{self.step}"
        return f"{self.target} = [{lo}:{hi}{st}]"


class BuildTuple(Instruction):
    """target = (elts...)"""
    def __init__(self, target, elts: list):
        super().__init__()
        self.target = target
        self.elts = elts

    def __repr__(self):
        inner = ", ".join(str(e) for e in self.elts)
        if len(self.elts) == 1:
            inner += ","
        return f"{self.target} = ({inner})"


class BuildList(Instruction):
    """target = [elts...]"""
    def __init__(self, target, elts: list):
        super().__init__()
        self.target = target
        self.elts = elts

    def __repr__(self):
        return f"{self.target} = [{', '.join(str(e) for e in self.elts)}]"


class OpaqueExpr(Instruction):
    """Opaque expression stored as raw AST source (for complex exprs like listcomps)."""
    def __init__(self, target, src: str):
        super().__init__()
        self.target = target
        self.src = src

    def __repr__(self):
        return f"{self.target} = {self.src}" if self.target else self.src


class Jump(Instruction):
    def __init__(self, target_block_id: int):
        super().__init__()
        self.target_block_id = target_block_id

    def __repr__(self):
        return f"jump B{self.target_block_id}"


class Branch(Instruction):
    def __init__(self, condition, true_block_id: int, false_block_id: int):
        super().__init__()
        self.condition = condition
        self.true_block_id = true_block_id
        self.false_block_id = false_block_id

    def __repr__(self):
        return f"if {self.condition} jump B{self.true_block_id} else B{self.false_block_id}"


class ForIter(Instruction):
    """Marks start of a for-loop iteration over an iterable."""
    def __init__(self, target, iterable, body_block_id: int, exit_block_id: int):
        super().__init__()
        self.target = target      # loop variable value (each element)
        self.iterable = iterable
        self.body_block_id = body_block_id
        self.exit_block_id = exit_block_id

    def __repr__(self):
        return f"for {self.target} in {self.iterable} → B{self.body_block_id} else B{self.exit_block_id}"


class Return(Instruction):
    def __init__(self, value=None):
        super().__init__()
        self.value = value

    def __repr__(self):
        return f"return {self.value}" if self.value is not None else "return"


class Raise(Instruction):
    def __init__(self, exc=None):
        super().__init__()
        self.exc = exc

    def __repr__(self):
        return f"raise {self.exc}" if self.exc else "raise"


class Assert(Instruction):
    def __init__(self, test, msg=None):
        super().__init__()
        self.test = test
        self.msg = msg

    def __repr__(self):
        return f"assert {self.test}" + (f", {self.msg}" if self.msg else "")


class Import(Instruction):
    def __init__(self, module: str, alias: Optional[str] = None):
        super().__init__()
        self.module = module
        self.alias = alias

    def __repr__(self):
        return f"import {self.module}" + (f" as {self.alias}" if self.alias else "")


class ImportFrom(Instruction):
    def __init__(self, module: str, name: str, alias: Optional[str] = None):
        super().__init__()
        self.module = module
        self.name = name
        self.alias = alias

    def __repr__(self):
        a = f" as {self.alias}" if self.alias else ""
        return f"from {self.module} import {self.name}{a}"


class LoadAttr(Instruction):
    """target = obj.attr"""
    def __init__(self, target, obj, attr: str):
        super().__init__()
        self.target = target
        self.obj = obj
        self.attr = attr

    def __repr__(self):
        return f"{self.target} = {self.obj}.{self.attr}"


class StoreAttr(Instruction):
    """obj.attr = value"""
    def __init__(self, obj, attr: str, value):
        super().__init__()
        self.obj = obj
        self.attr = attr
        self.value = value

    def __repr__(self):
        return f"{self.obj}.{self.attr} = {self.value}"


class FuncDef(Instruction):
    """Function definition (nested CFG)."""
    def __init__(self, name: str, args: list, cfg):
        super().__init__()
        self.name = name
        self.args = args
        self.cfg = cfg  # sub-CFG

    def __repr__(self):
        return f"def {self.name}({', '.join(self.args)}): ..."
