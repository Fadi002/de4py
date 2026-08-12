# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Tests for the Cyron-style match/case state machine deobfuscator.

The ground-truth cases matter most: build-logs/control-flow-flattening ships an
original and its flattened form by the same author, so recovery can be checked
against truth instead of against a heuristic score.
"""

import ast
import pathlib

import pytest

from de4py.engines.onyx.match_case_deobfuscator import MatchCaseDeobfuscator

CFF = (
    pathlib.Path(__file__).resolve().parents[4]
    / "build-logs"
    / "control-flow-flattening"
)


@pytest.fixture(scope="module")
def deobfuscator():
    return MatchCaseDeobfuscator()


def _normalize(source: str) -> str:
    return ast.dump(ast.parse(source))


# ── ground truth ────────────────────────────────────────────────────────────

@pytest.mark.skipif(not CFF.exists(), reason="corpus not present")
def test_flattened_sample_recovers_to_original(deobfuscator):
    """out.py is input.py run through the author's flattener; recover it exactly."""
    flattened = (CFF / "out.py").read_text(encoding="utf-8")
    original = (CFF / "input.py").read_text(encoding="utf-8")

    recovered = deobfuscator.deobfuscate(flattened)

    assert _normalize(recovered) == _normalize(original)


# ── dead dispatcher state is removable, live state is not ───────────────────

SM = """\
state = 0
table = {0: 1}
delta = 0
step = 0
while state != 9:
    match state:
        case 0:
            print('first')
            state = 1
        case 1:
            print('second')
            state = 9
        case _:
            table[str(state)] = state + delta
            state -= step
"""


def test_dispatcher_state_is_removed_when_dead(deobfuscator):
    out = deobfuscator.deobfuscate(SM)
    assert "print('first')" in out
    assert "print('second')" in out
    for name in ("state", "table", "delta", "step"):
        assert name not in out


def test_dispatcher_state_survives_when_still_read(deobfuscator):
    """A later read is proof the binding is live; it must not be removed."""
    out = deobfuscator.deobfuscate(SM + "print(delta)\n")
    assert "delta = 0" in out
    assert "print(delta)" in out


def test_non_control_binding_is_never_removed(deobfuscator):
    """`secret` is unread, but nothing proves it is dispatcher state."""
    out = deobfuscator.deobfuscate("secret = 'payload'\n" + SM)
    assert "secret = 'payload'" in out


def test_dynamic_scope_access_disables_removal(deobfuscator):
    """globals() can read any binding, so no name is provably dead."""
    out = deobfuscator.deobfuscate(SM + "print(globals())\n")
    assert "state = 0" in out


def test_impure_value_is_never_dropped(deobfuscator):
    """Discarding a call would discard its side effect."""
    source = SM.replace("delta = 0", "delta = int(input())")
    out = deobfuscator.deobfuscate(source)
    assert "input()" in out


# ── the transform must never produce invalid Python ─────────────────────────

def test_output_always_parses(deobfuscator):
    for source in (SM, SM + "print(delta)\n", "x = 1\n"):
        ast.parse(deobfuscator.deobfuscate(source))


def test_function_body_never_left_empty(deobfuscator):
    source = "def f():\n" + "".join("    " + line for line in SM.splitlines(True))
    out = deobfuscator.deobfuscate(source)
    ast.parse(out)
    assert "def f():" in out


def test_unrelated_source_is_untouched(deobfuscator):
    source = "def f(a, b):\n    return a + b\n"
    assert _normalize(deobfuscator.deobfuscate(source)) == _normalize(source)
