# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Match:
    node: ast.AST
    confidence: float = 1.0
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Patch:
    target: ast.AST
    replacement: "ast.AST | list[ast.stmt] | None"
    detail: str = ""


class Rule:

    name: str = ""
    safety: str = "safe"
    event_category: str = "TRANSFORM"

    def applies(self, ctx) -> list:
        return []

    def transform(self, ctx, match):
        return None


class RuleRegistry:
    def __init__(self):
        self._rules: list = []

    def register(self, *rules):
        for rule in rules:
            if any(r.name == rule.name for r in self._rules):
                raise ValueError(f"duplicate rule name: {rule.name}")
            self._rules.append(rule)

    @property
    def rules(self) -> tuple:
        return tuple(self._rules)
