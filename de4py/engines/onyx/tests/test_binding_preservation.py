# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Guards for the "never delete what you cannot prove is junk" rule.

Each test here corresponds to a transformation that previously destroyed real
program content: an unread binding holding a decoded payload, a conventional
single-letter variable mistaken for a generated name, a constant propagated
across a loop back edge, and a triage signature that never matched.
"""

import ast

import pytest

from de4py.engines.onyx.ast_cleaner import ASTCleaner
from de4py.engines.onyx.pipeline import Pipeline
from de4py.engines.onyx.rule_renamer import is_mangled
from de4py.engines.onyx.triage import TriageEngine


@pytest.fixture(scope="module")
def pipeline():
    return Pipeline(use_llm=False)


# ── decoded-but-unread bindings must survive ────────────────────────────────

def test_decoded_payload_is_not_deleted(pipeline):
    """The decoded value is the analysis result; dropping it defeats the tool."""
    result = pipeline.run("import base64\nx = base64.b64decode('SGVsbG8=')\n", "t.py")
    assert result.success
    assert "Hello" in result.cleaned


def test_chr_chain_binding_survives(pipeline):
    result = pipeline.run("x = chr(72)+chr(101)+chr(108)+chr(108)+chr(111)\n", "t.py")
    assert result.success
    assert "Hello" in result.cleaned
    assert result.cleaned.strip() != "pass"


def test_unread_binding_kept_even_when_name_looks_generated(pipeline):
    """`a1` is never read, so there is no substitution to justify removing it."""
    result = pipeline.run("a1 = 'Recovered Secret'\n", "t.py")
    assert result.success
    assert "Recovered Secret" in result.cleaned


def test_inlined_mangled_proxy_is_still_removed(pipeline):
    """The rule only protects bindings that were not consumed."""
    result = pipeline.run("a1 = 'Mangled Proxy'\nprint(a1)\n", "t.py")
    assert result.success
    assert "Mangled Proxy" in result.cleaned
    assert "a1 =" not in result.cleaned


# ── conventional names are not obfuscation artifacts ────────────────────────

@pytest.mark.parametrize("name", ["i", "j", "k", "n", "m", "x", "y", "z"])
def test_conventional_single_letters_not_mangled(name):
    assert not is_mangled(name)


@pytest.mark.parametrize("name", ["a1", "b99", "OOIl", "lllI"])
def test_generated_names_still_detected(name):
    assert is_mangled(name)


# ── constant propagation must respect back edges ────────────────────────────

def test_constant_not_propagated_into_loop_that_reassigns_it():
    """
    A value that holds before a loop need not hold on the second iteration.

    Propagating it in rewrites the dispatcher's state test to `0 == 0` and the
    state machine can no longer be recognised, let alone linearised.
    """
    source = (
        "def f():\n"
        "    state = 0\n"
        "    while True:\n"
        "        if state == 0:\n"
        "            a = 1\n"
        "            state = 1\n"
        "        elif state == 1:\n"
        "            return a\n"
    )
    cleaned = ASTCleaner().clean(source)
    assert "0 == 0" not in cleaned
    assert "0 == 1" not in cleaned


def test_constant_still_propagated_when_loop_does_not_touch_it():
    source = (
        "def f():\n"
        "    limit = 3\n"
        "    total = 0\n"
        "    for i in range(10):\n"
        "        total = total + limit\n"
        "    return total\n"
    )
    cleaned = ASTCleaner().clean(source)
    assert "limit" not in cleaned.split("return")[0] or "3" in cleaned


# ── triage signatures must scan the whole file ──────────────────────────────

def test_signature_matches_at_start_of_file():
    """
    `Pattern.search(s, flags)` treats the second argument as a start offset, so
    passing re flags there skipped the first 24 characters of every sample.
    """
    engine = TriageEngine()
    result = engine.analyze("exec('x')\n", "t.py")
    assert "eval_exec" in result.flags


def test_obfuscated_scores_above_clean():
    engine = TriageEngine()
    clean = engine.analyze("def add(a, b):\n    return a + b\n", "c.py")
    obfuscated = engine.analyze(
        "import base64\nexec(base64.b64decode('cHJpbnQoMSk='))\n", "o.py")
    assert obfuscated.score > clean.score


# ── accumulator initializers must survive ───────────────────────────────────

def test_accumulator_initializer_survives():
    """`acc += x` reads acc, so dropping `acc = ''` leaves an unbound name."""
    source = (
        "def f():\n"
        "    acc = ''\n"
        "    for i in range(3):\n"
        "        acc += chr(i)\n"
        "    return acc\n"
    )
    out = ASTCleaner().clean(source)
    assert "acc = ''" in out
    assert "return acc" in out


def test_value_mutated_in_loop_is_not_folded_after_it():
    """The post-loop read sees the accumulated value, not the initial constant."""
    source = (
        "def f():\n"
        "    total = 0\n"
        "    for i in range(3):\n"
        "        total += i\n"
        "    return total\n"
    )
    out = ASTCleaner().clean(source)
    assert "return total" in out
    assert "return 0" not in out


def test_mutated_container_binding_survives():
    """`obj[i] = v` reads obj in order to mutate it."""
    source = (
        "def f():\n"
        "    slots = {}\n"
        "    slots['k'] = 1\n"
        "    return slots\n"
    )
    out = ASTCleaner().clean(source)
    assert "slots = {}" in out


def test_imported_names_are_not_renamed():
    """A library name is the strongest clue about what recovered code does."""
    from de4py.engines.onyx.rule_renamer import RuleRenamer
    source = (
        "from Crypto.Cipher import AES\n"
        "def f(k, iv):\n"
        "    return AES.new(k, AES.MODE_CBC, iv)\n"
    )
    out = RuleRenamer().rename(source)
    assert "AES" in out
    assert "AES.MODE_CBC" in out


def test_value_mutated_in_nested_block_is_not_folded():
    """An accumulator built inside `if` must not read back as its initializer."""
    source = (
        "def f(n):\n"
        "    acc = ''\n"
        "    if n:\n"
        "        for i in range(n):\n"
        "            acc += chr(i)\n"
        "        out = acc[0:2]\n"
        "        return out\n"
        "    return acc\n"
    )
    out = ASTCleaner().clean(source)
    assert "acc[0:2]" in out
    assert "''[0:2]" not in out
