# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Utilities for detecting meaningful source changes without formatting noise."""

import ast
from typing import Optional


def _ast_signature_from_source(source: str) -> Optional[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    except Exception:
        return None
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def ast_signature(tree: ast.AST) -> str:
    """Return a stable AST signature without location noise."""
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def ast_changed(before_tree: ast.AST, after_tree: ast.AST) -> bool:
    """Return True only when the AST structure changed meaningfully."""
    try:
        return ast_signature(before_tree) != ast_signature(after_tree)
    except Exception:
        try:
            return ast.unparse(before_tree) != ast.unparse(after_tree)
        except Exception:
            return True


def source_changed(before: str, after: str) -> bool:
    """
    Return True only when the source changed meaningfully.

    Preferred path compares AST structure so whitespace / trailing-newline /
    unparsing-only differences do not count as a real transform.
    Falls back to normalized text when parsing is unavailable.
    """
    if before == after:
        return False

    before_sig = _ast_signature_from_source(before)
    after_sig = _ast_signature_from_source(after)
    if before_sig is not None and after_sig is not None:
        return before_sig != after_sig

    return before.rstrip() != after.rstrip()
