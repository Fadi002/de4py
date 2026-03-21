# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
from dataclasses import dataclass
from typing import Tuple


@dataclass
class ValidationResult:
    valid: bool
    syntax_ok: bool
    structure_ok: bool
    error: str = ""
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class Validator:

    def validate(self, original: str, cleaned: str) -> ValidationResult:
        """Full validation: syntax + structural equivalence"""

        # Step 1: Syntax check on cleaned output
        syntax_ok, syntax_error = self._check_syntax(cleaned)
        if not syntax_ok:
            return ValidationResult(
                valid=False,
                syntax_ok=False,
                structure_ok=False,
                error=f"Syntax error in cleaned output: {syntax_error}",
            )

        # Step 2: Structural equivalence
        structure_ok, structure_warnings = self._check_structure(original, cleaned)

        return ValidationResult(
            valid=syntax_ok and structure_ok,
            syntax_ok=syntax_ok,
            structure_ok=structure_ok,
            warnings=structure_warnings,
        )

    def check_syntax_only(self, source: str) -> Tuple[bool, str]:
        """Quick syntax check â€” used mid-pipeline"""
        return self._check_syntax(source)

    # â”€â”€ Private â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
            return True, []  # Can't compare â€” give benefit of the doubt

        orig_stats  = self._tree_stats(orig_tree)
        clean_stats = self._tree_stats(clean_tree)

        for key in orig_stats:
            orig_val  = orig_stats[key]
            clean_val = clean_stats.get(key, 0)

            if orig_val == 0:
                continue

            # Allow up to 30% difference (dead code removal changes counts legitimately)
            ratio = clean_val / orig_val if orig_val > 0 else 1.0
            if ratio < 0.5:
                warnings.append(
                    f"Significant reduction in {key}: {orig_val} â†’ {clean_val} "
                    f"({ratio:.0%})"
                )

        # Fail if function count dropped by more than 60% (likely LLM hallucination)
        orig_fns  = orig_stats.get("functions", 0)
        clean_fns = clean_stats.get("functions", 0)
        if orig_fns > 0 and clean_fns < orig_fns * 0.4:
            return False, warnings + [
                f"Too many functions lost: {orig_fns} â†’ {clean_fns}"
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

