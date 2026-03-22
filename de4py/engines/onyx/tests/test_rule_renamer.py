# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import pytest
import sys
import os

# Add the parent directory to sys.path so we can import engines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from de4py.engines.onyx.rule_renamer import RuleRenamer, is_mangled


@pytest.fixture
def renamer():
    return RuleRenamer()


def test_is_mangled_single_letter():
    assert is_mangled("a") == True
    assert is_mangled("z") == True


def test_is_mangled_short_numeric():
    assert is_mangled("a1") == True
    assert is_mangled("b99") == True


def test_is_mangled_ooi_style():
    assert is_mangled("OOIl") == True
    assert is_mangled("lllI") == True


def test_is_not_mangled_normal_name():
    assert is_mangled("total_count") == False
    assert is_mangled("calculate") == False
    assert is_mangled("main") == False


def test_is_not_mangled_dunder():
    assert is_mangled("__init__") == False
    assert is_mangled("__name__") == False


def test_rename_simple_assignment(renamer):
    source = "import json\na1 = json.loads(data)\n"
    result = renamer.rename(source)
    assert "a1" not in result or "parsed_data" in result


def test_rename_list_constructor(renamer):
    source = "a1 = list(items)\n"
    result = renamer.rename(source)
    assert "a1" not in result


def test_rename_function_def(renamer):
    source = "def a1(b2):\n    return b2 * 2\n"
    result = renamer.rename(source)
    # Function should be renamed
    assert "a1" not in result or "func" in result


def test_clean_code_unchanged(renamer):
    source = "def calculate(total, count):\n    return total / count\n"
    result = renamer.rename(source)
    # Clean code should not be changed
    assert "calculate" in result
    assert "total" in result
    assert "count" in result


def test_builtin_names_not_renamed(renamer):
    source = "x = len(items)\nprint(x)\n"
    result = renamer.rename(source)
    assert "len" in result
    assert "print" in result

