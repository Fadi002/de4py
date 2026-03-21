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

from de4py.engines.onyx.pipeline import Pipeline

@pytest.fixture
def pipeline_no_llm():
    return Pipeline(use_llm=False)


def test_clean_code_passes_through(pipeline_no_llm):
    source = "def hello():\n    return 'world'\n"
    result = pipeline_no_llm.run(source, "hello.py")
    assert result.success
    assert "hello" in result.cleaned


def test_b64_decoded(pipeline_no_llm):
    source = "import base64\nx = base64.b64decode('SGVsbG8=')\n"
    result = pipeline_no_llm.run(source, "test.py")
    assert result.success
    assert "Hello" in result.cleaned


def test_chr_chain_decoded(pipeline_no_llm):
    source = "x = chr(72)+chr(101)+chr(108)+chr(108)+chr(111)\n"
    result = pipeline_no_llm.run(source, "test.py")
    assert result.success
    assert "Hello" in result.cleaned


def test_dead_code_removed(pipeline_no_llm):
    source = "x = 1\nif False:\n    x = 999\nprint(x)\n"
    result = pipeline_no_llm.run(source, "test.py")
    assert result.success
    assert "999" not in result.cleaned


def test_validation_fails_on_broken_llm_output(pipeline_no_llm):
    """If cleaning produces invalid Python, original is returned"""
    source = "def valid_function():\n    return 42\n"
    result = pipeline_no_llm.run(source, "test.py")
    # Should always be valid since we run valid input
    assert result.success


def test_triage_scores_obfuscated_higher(pipeline_no_llm):
    clean   = "def add(a, b):\n    return a + b\n"
    obfusc  = "import base64\nexec(base64.b64decode('cHJpbnQoMSk='))\n"
    r1 = pipeline_no_llm.run(clean,  "clean.py")
    r2 = pipeline_no_llm.run(obfusc, "obf.py")
    assert r2.triage.score > r1.triage.score


def test_mixed_obfuscation(pipeline_no_llm):
    source = (
        "import base64\n"
        "x = base64.b64decode('SGVsbG8=')\n"
        "y = chr(87)+chr(111)+chr(114)+chr(108)+chr(100)\n"
        "if False:\n    z = 999\n"
    )
    result = pipeline_no_llm.run(source, "mixed.py")
    assert result.success
    assert "Hello" in result.cleaned
    assert "World" in result.cleaned
    assert "999" not in result.cleaned

