# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class _FakeResult:
    success = True
    cleaned = "x = 1\n"
    log = []
    triage = None
    ai_summary = ""


def _write_sample():
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
    f.write("x = 1\n")
    f.close()
    return f.name


def test_onyxalpha_passes_ai_overrides(monkeypatch):
    from de4py.engines.onyx import engine as engine_module

    captured = {}

    class _FakePipeline:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, source, filename="file.py"):
            return _FakeResult()

    monkeypatch.setattr(engine_module, "Pipeline", _FakePipeline)

    from de4py.engines.onyx.engine import OnyxAlpha

    path = _write_sample()
    try:
        OnyxAlpha().deobfuscate(path, ai_overrides={
            "use_llm": True, "annotate": True,
            "ai_explain": True, "ai_simplify": False,
        })
    finally:
        os.unlink(path)

    assert captured["use_llm"] is True
    assert captured["annotate"] is True
    assert captured["ai_explain"] is True
    assert captured["ai_simplify"] is False


def test_onyxalpha_no_overrides_passes_nothing(monkeypatch):
    from de4py.engines.onyx import engine as engine_module

    captured = {}

    class _FakePipeline:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self, source, filename="file.py"):
            return _FakeResult()

    monkeypatch.setattr(engine_module, "Pipeline", _FakePipeline)

    from de4py.engines.onyx.engine import OnyxAlpha

    path = _write_sample()
    try:
        OnyxAlpha().deobfuscate(path)
    finally:
        os.unlink(path)

    assert captured == {}


def test_detect_obfuscator_passes_ai_overrides(tmp_path, monkeypatch):
    from de4py.engines.onyx import engine as engine_module

    captured = {}

    class _FakeAlpha:
        def deobfuscate(self, file_path, ai_overrides=None):
            captured["path"] = file_path
            captured["overrides"] = ai_overrides
            return "cleaned"

    monkeypatch.setattr(engine_module, "OnyxAlpha", _FakeAlpha)

    from de4py.engines.legacy.detector import detect_obfuscator

    path = tmp_path / "sample.py"
    path.write_text("x = 1\n", encoding="utf-8")

    out = detect_obfuscator(str(path), {"use_llm": True, "ai_explain": True})
    assert out == "cleaned"
    assert captured["overrides"] == {"use_llm": True, "ai_explain": True}


def test_detect_obfuscator_default_overrides_none(tmp_path, monkeypatch):
    from de4py.engines.onyx import engine as engine_module

    captured = {}

    class _FakeAlpha:
        def deobfuscate(self, file_path, ai_overrides=None):
            captured["overrides"] = ai_overrides
            return "cleaned"

    monkeypatch.setattr(engine_module, "OnyxAlpha", _FakeAlpha)

    from de4py.engines.legacy.detector import detect_obfuscator

    path = tmp_path / "sample.py"
    path.write_text("x = 1\n", encoding="utf-8")

    detect_obfuscator(str(path))
    assert captured["overrides"] is None
