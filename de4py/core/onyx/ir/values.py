# de4py - Onyx Engine
# IR Values Definition

from abc import ABC
from typing import Any, Optional

class Value(ABC):
    """Abstract base class for all IR values."""
    pass

class Constant(Value):
    """Represents a literal constant value."""
    def __init__(self, value: Any):
        self.value = value

    def __repr__(self):
        return f"Const({repr(self.value)})"

class Variable(Value):
    """Represents a named variable or register."""
    def __init__(self, name: str, version: Optional[int] = None):
        self.name = name
        self.version = version  # For SSA

    def __repr__(self):
        if self.version is not None:
            return f"{self.name}_{self.version}"
        return self.name

class Temporary(Variable):
    """Internal IR temporary variable."""
    def __init__(self, id: int, version: Optional[int] = None):
        super().__init__(f"t{id}", version)

class PhiValue(Value):
    """SSA Phi function representation."""
    def __init__(self, options: dict[int, Variable]):
        # map: block_id -> variable
        self.options = options

    def __repr__(self):
        opts = ", ".join(f"B{bid}: {var}" for bid, var in self.options.items())
        return f"phi({opts})"
