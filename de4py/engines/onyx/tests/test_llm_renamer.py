# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import ast
import json
import sys
import os
import threading
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from de4py.engines.onyx.llm_renamer import (
    LLMRenamer,
    _apply_rename,
    _collect_candidates,
    _excluded_names,
    _has_dynamic_names,
    _parse_json_mapping,
    _safe_simplification,
    _validated_mapping,
)


class _FakeClient:
    def __init__(self, responses=None, available=True):
        self.responses = responses
        self.calls = []
        self.available = available

    def chat(self, system, user, temperature=0.0, max_tokens=2048, json_mode=False):
        self.calls.append(user)
        if callable(self.responses):
            return self.responses(user)
        if isinstance(self.responses, list):
            return self.responses.pop(0) if self.responses else None
        return self.responses

    def ensure_model(self):
        return True


def _make_renamer(responses=None, available=True):
    r = LLMRenamer.__new__(LLMRenamer)
    r.ai_config = SimpleNamespace(
        context_window=4096, model="test-model", is_ollama=True
    )
    r.client = _FakeClient(responses, available=available)
    r._cache = {}
    r._cache_lock = threading.Lock()
    return r


def _never_called(*args, **kwargs):
    raise AssertionError("LLM should not have been called")


def test_mapping_rename_applies():
    r = _make_renamer(
        json.dumps({"a1": "decode_b64", "a2": "payload", "a3": "raw", "a4": "text"})
    )
    src = (
        "import base64\n"
        "\n"
        "def a1(a2):\n"
        "    a3 = base64.b64decode(a2)\n"
        "    a4 = a3.decode()\n"
        "    return a4\n"
    )
    out = r.process_file(src)
    assert "def decode_b64(payload):" in out
    assert "raw = base64.b64decode(payload)" in out
    assert "text = raw.decode()" in out
    assert "import base64" in out


def test_rename_only_changes_identifiers():
    src = 'def a1(a2):\n    a3 = "a1 a2 a3 kept verbatim"\n    return a3[a2]\n'
    tree = ast.parse(src)
    mapping = {"a1": "lookup", "a2": "index", "a3": "items"}
    out = _apply_rename(src, tree, mapping)
    assert out == (
        'def lookup(index):\n    items = "a1 a2 a3 kept verbatim"\n    return items[index]\n'
    )
    orig_dump = ast.dump(tree)
    renamed_dump = ast.dump(ast.parse(out))
    for old, new in mapping.items():
        orig_dump = orig_dump.replace("'%s'" % old, "'%s'" % new)
    assert orig_dump == renamed_dump


def test_invalid_json_no_change():
    r = _make_renamer("this is not json at all")
    src = "def a1():\n    return 1\n"
    assert r.process_file(src) == src


def test_mapping_filters_unsafe_names():
    r = _make_renamer(json.dumps({"a1": "print", "a2": "def", "a3": "ghost"}))
    src = "def a1(a2):\n    return a2\n"
    assert r.process_file(src) == src


def test_mapping_rejects_collision_with_existing_name():
    r = _make_renamer(json.dumps({"a1": "count"}))
    src = "def a1(count):\n    return count\n"
    assert r.process_file(src) == src


def test_mapping_rejects_collision_with_other_mangled_name():
    r = _make_renamer(json.dumps({"a1": "b2"}))
    src = "def a1(b2):\n    return b2\n"
    assert r.process_file(src) == src


def test_dynamic_names_skip_llm():
    r = _make_renamer(_never_called)
    src = "def a1(code):\n    return eval(code)\n"
    assert r.process_file(src) == src
    assert r.client.calls == []


def test_imported_and_global_names_excluded():
    r = _make_renamer(json.dumps({"base64": "b64", "GLOBAL_X": "gx"}))
    src = (
        "import base64\n"
        "GLOBAL_X = 1\n"
        "def a1():\n"
        "    global GLOBAL_X\n"
        "    return base64, GLOBAL_X\n"
    )
    out = r.process_file(src)
    assert "import base64" in out
    assert "GLOBAL_X" in out
    assert "def a1():" in out


def test_payloads_stripped_from_prompt():
    r = _make_renamer(json.dumps({"a1": "decode"}))
    payload = "A" * 500
    src = 'def a1():\n    x = "%s"\n    return x\n' % payload
    r.process_file(src)
    assert r.client.calls
    assert payload not in r.client.calls[0]
    assert "<payload_" in r.client.calls[0]


def test_cache_hits_avoid_second_call():
    r = _make_renamer(json.dumps({"a1": "identity", "a2": "value"}))
    src = "def a1(a2):\n    return a2\n"
    out1 = r.process_file(src)
    out2 = r.process_file(src)
    assert out1 == out2
    assert len(r.client.calls) == 1


def test_multiple_functions_parallel_and_ordered():
    r = _make_renamer(json.dumps({"a1": "first", "b2": "second"}))
    src = "def a1():\n    return 1\n\n\ndef b2():\n    return 2\n"
    out = r.process_file(src)
    assert "def first():" in out
    assert "def second():" in out
    assert out.index("def first") < out.index("def second")


def test_module_level_rename():
    r = _make_renamer(json.dumps({"a1": "base", "b2": "total"}))
    src = "a1 = 5\nb2 = a1 + 1\n"
    out = r.process_file(src)
    assert out == "base = 5\ntotal = base + 1\n"


def test_available_false_returns_source():
    r = _make_renamer(_never_called, available=False)
    src = "def a1():\n    return 1\n"
    assert r.process_file(src) == src
    assert r.client.calls == []


def test_non_mangled_names_not_renamed():
    r = _make_renamer(_never_called)
    src = "def helper(value):\n    return value\n"
    assert r.process_file(src) == src
    assert r.client.calls == []


def test_nested_function_closure_consistent():
    r = _make_renamer(json.dumps({"a1": "outer", "a2": "captured", "b3": "inner"}))
    src = "def a1(a2):\n    def b3():\n        return a2\n    return b3\n"
    out = r.process_file(src)
    assert "def outer(captured):" in out
    assert "def inner():" in out
    assert "return captured" in out
    assert "return inner" in out


def test_annotate_path():
    r = _make_renamer(
        lambda prompt: (
            json.dumps({"a1": "identity", "a2": "value"})
            if "produce a mapping for identifiers" in prompt
            else 'def identity(value):\n    """Return the value."""\n    return value\n'
        )
    )
    src = "def a1(a2):\n    return a2\n"
    out = r.process_file(src, annotate=True)
    assert '"""Return the value."""' in out


def test_explain_returns_report():
    r = _make_renamer("# Purpose\nThis decodes base64 payloads.\n")
    out = r.explain("def a1():\n    return 1\n")
    assert "Purpose" in out


def test_explain_unavailable_returns_empty():
    r = _make_renamer(_never_called, available=False)
    assert r.explain("x = 1\n") == ""


def test_simplify_applies_when_safe():
    r = _make_renamer("def a1():\n    return 1\n")
    src = "def a1():\n    x = 1\n    return x + 0\n"
    out = r.simplify(src)
    assert "x + 0" not in out


def test_simplify_rejects_renaming_and_growth():
    r = _make_renamer("def renamed():\n    return 1\n")
    src = "def a1():\n    return 1\n"
    assert r.simplify(src) == src


def test_safe_simplification():
    good = "def a1():\n    return 1\n"
    assert _safe_simplification(good, "def a1():\n    return 1\n") is True
    assert _safe_simplification(good, "def b2():\n    return 1\n") is False
    assert _safe_simplification(good, "def a1():\n    return 1\n" * 5) is False
    assert _safe_simplification("def a1(:\n", "def a1():\n    pass\n") is False


def test_safe_simplification_preserves_constants():
    orig = 'def a1():\n    return "secret-key"\n'
    changed = 'def a1():\n    return "other-key"\n'
    assert _safe_simplification(orig, changed) is False
    numeric = "def a1():\n    return 1234\n"
    assert _safe_simplification(numeric, "def a1():\n    return 9999\n") is False


def test_fix_syntax_fast_path():
    r = _make_renamer(_never_called)
    assert r.fix_syntax("x = 1\n", "unused") == "x = 1\n"


def test_fix_syntax_unavailable_returns_code():
    r = _make_renamer(_never_called, available=False)
    assert r.fix_syntax("broken code (", "unused") == "broken code ("


def test_parse_json_mapping_variants():
    assert _parse_json_mapping(None) == {}
    assert _parse_json_mapping("junk") == {}
    fenced = '```json\n{"a1": "x"}\n```'
    assert _parse_json_mapping(fenced) == {"a1": "x"}
    with_prose = 'Here you go:\n{"a1": "x", "b2": "y"}\nHope that helps'
    assert _parse_json_mapping(with_prose) == {"a1": "x", "b2": "y"}
    salvaged = '{"a1": "x" trailing garbage'
    assert _parse_json_mapping(salvaged) == {"a1": "x"}


def test_candidates_and_exclusions():
    src = (
        "import os\n"
        "def a1(b2):\n"
        "    global c3\n"
        "    try:\n"
        "        pass\n"
        "    except Exception as e4:\n"
        "        pass\n"
        "    return os, c3\n"
    )
    tree = ast.parse(src)
    candidates = _collect_candidates(tree)
    assert "a1" in candidates and "b2" in candidates
    excluded = _excluded_names(tree)
    assert "os" in excluded and "c3" in excluded and "e4" in excluded
    assert _has_dynamic_names(ast.parse("def f():\n    exec('x')\n")) is True
    assert _has_dynamic_names(ast.parse("def f():\n    return 1\n")) is False


def test_validated_mapping_filters():
    src = "def a1(a2):\n    return a2\n"
    tree = ast.parse(src)
    mapping = {
        "a1": "good_name",
        "a2": "print",
        "ghost": "nope",
        "a1_dup": "good_name",
    }
    result = _validated_mapping(mapping, {"a1", "a2"}, tree)
    assert result == {"a1": "good_name"}
