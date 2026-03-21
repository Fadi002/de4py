# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import pytest
import sys
import os

# Add the parent directory to sys.path so we can import engines
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from de4py.engines.onyx.ast_cleaner import ASTCleaner


@pytest.fixture
def cleaner():
    return ASTCleaner()


def test_dead_if_false_removed(cleaner):
    source = "if False:\n    x = 1\ny = 2\n"
    result = cleaner.clean(source)
    assert "if False" not in result
    assert "y = 2" in result


def test_dead_if_true_flattened(cleaner):
    source = "if True:\n    x = 1\n"
    result = cleaner.clean(source)
    assert "if True" not in result
    assert "x = 1" in result


def test_constant_folding(cleaner):
    source = "x = 7 * 6\n"
    result = cleaner.clean(source)
    assert "42" in result
    assert "7 * 6" not in result


def test_self_assign_removed(cleaner):
    source = "x = 1\nx = x\ny = 2\n"
    result = cleaner.clean(source)
    assert result.count("x = x") == 0


def test_state_machine_linearized(cleaner):
    source = """
def f():
    __state = 0
    while True:
        if __state == 0:
            a = 1
            __state = 1
        elif __state == 1:
            b = 2
            __state = 2
        elif __state == 2:
            return a + b
"""
    result = cleaner.clean(source)
    assert "while True" not in result
    assert "a = 1" in result
    assert "b = 2" in result


def test_invalid_source_returned_unchanged(cleaner):
    source = "def foo(:\n    pass\n"  # syntax error
    result = cleaner.clean(source)
    assert result == source


def test_while_false_removed(cleaner):
    source = "while False:\n    x = 1\ny = 2\n"
    result = cleaner.clean(source)
    assert "while False" not in result
    assert "y = 2" in result

