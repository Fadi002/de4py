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
from typing import Tuple


@dataclass
class ValidationResult:
    valid: bool
    syntax_ok: bool
    structure_ok: bool
    error: str = ""
    warnings: list = field(default_factory=list)


class Validator:

    def validate(self, original: str, cleaned: str) -> ValidationResult:
        """Full validation: syntax + structural equivalence"""

        syntax_ok, syntax_error = self._check_syntax(cleaned)
        if not syntax_ok:
            return ValidationResult(
                valid=False,
                syntax_ok=False,
                structure_ok=False,
                error=f"Syntax error in cleaned output: {syntax_error}",
            )

        structure_ok, structure_warnings = self._check_structure(original, cleaned)

        return ValidationResult(
            valid=syntax_ok and structure_ok,
            syntax_ok=syntax_ok,
            structure_ok=structure_ok,
            warnings=structure_warnings,
        )

    def check_syntax_only(self, source: str) -> Tuple[bool, str]:
        """Quick syntax check - used mid-pipeline"""
        return self._check_syntax(source)

    def _check_syntax(self, source: str) -> Tuple[bool, str]:
        try:
            ast.parse(source)
            return True, ""
        except SyntaxError as e:
            return False, f"line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)

    def _check_structure(
        self, original: str, cleaned: str
    ) -> Tuple[bool, list]:
        """
        Compare high-level structure metrics between original and cleaned.
        Differences generate warnings but only large discrepancies fail validation.
        """
        warnings = []

        try:
            orig_tree  = ast.parse(original)
            clean_tree = ast.parse(cleaned)
        except SyntaxError:
            return True, []

        orig_stats  = self._tree_stats(orig_tree)
        clean_stats = self._tree_stats(clean_tree)

        for key in orig_stats:
            orig_val  = orig_stats[key]
            clean_val = clean_stats.get(key, 0)

            if orig_val == 0:
                continue

            ratio = clean_val / orig_val
            if ratio < 0.5:
                warnings.append(
                    f"Significant reduction in {key}: {orig_val} -> {clean_val} "
                    f"({ratio:.0%})"
                )

        orig_fns  = orig_stats.get("functions", 0)
        clean_fns = clean_stats.get("functions", 0)
        if orig_fns > 0 and clean_fns < orig_fns * 0.4:
            return False, warnings + [
                f"Too many functions lost: {orig_fns} -> {clean_fns}"
            ]

        return True, warnings

    def _tree_stats(self, tree: ast.Module) -> dict:
        """Count structural elements in an AST"""
        stats = {
            "functions": 0,
            "classes":   0,
            "loops":     0,
            "branches":  0,
            "imports":   0,
            "returns":   0,
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stats["functions"] += 1
            elif isinstance(node, ast.ClassDef):
                stats["classes"] += 1
            elif isinstance(node, (ast.For, ast.While)):
                stats["loops"] += 1
            elif isinstance(node, ast.If):
                stats["branches"] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                stats["imports"] += 1
            elif isinstance(node, ast.Return):
                stats["returns"] += 1
        return stats
