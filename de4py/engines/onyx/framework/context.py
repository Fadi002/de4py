# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
from collections import Counter
from dataclasses import dataclass, field

from de4py.engines.onyx.framework.events import Event

SAFETY_CLASSES = ("safe", "probably_safe", "speculative")
_MODE_ALLOWED = {
    "safe": frozenset({"safe"}),
    "normal": frozenset({"safe", "probably_safe"}),
    "aggressive": frozenset(SAFETY_CLASSES),
}


@dataclass
class PassConfig:
    enabled: bool = False
    mode: str = "normal"
    max_iterations: int = 12
    max_ast_nodes: int = 500_000
    max_rules_source: int = 120_000
    explain: bool = False
    stats: bool = False
    debug: bool = False

    def __post_init__(self):
        if self.mode not in _MODE_ALLOWED:
            raise ValueError(f"unknown mode: {self.mode}")

    def allows(self, safety: str) -> bool:
        return safety in _MODE_ALLOWED[self.mode]

    @classmethod
    def from_options(cls, options) -> "PassConfig":
        options = dict(options or {})
        options.setdefault("enabled", bool(options))
        int_fields = {"max_iterations", "max_ast_nodes"}
        for name in int_fields & options.keys():
            options[name] = int(options[name])
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in options.items() if k in known})


@dataclass
class PassContext:
    source: str
    tree: ast.Module
    config: PassConfig
    events: list = field(default_factory=list)
    stats: Counter = field(default_factory=Counter)
    artifacts: dict = field(default_factory=dict)

    def log(self, category: str, detail: str, rule: str = "",
            confidence: float = 1.0):
        self.events.append(Event(category, detail, rule, confidence))

    def count(self, stat: str, amount: int = 1):
        self.stats[stat] += amount
