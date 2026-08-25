# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import marshal
import subprocess as _subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from de4py.engines.legacy._pyarmor_static import MarshalReader, RawCode
from de4py.engines.legacy.detector import obfuscators
from de4py.engines.legacy import pyarmor as pyarmor_module
from de4py.engines.legacy.pyarmor import resolve_mode, STATIC_MODE, HOOKING_MODE


def test_marshal_reader_round_trip_real_code_object():
    src = "def f(x):\n    y = x + 1\n    return [i for i in range(y)]\n"
    code = compile(src, "<test>", "exec")
    data = marshal.dumps(code)

    reader = MarshalReader(data, sys.version_info[:2])
    root = reader.read()

    assert isinstance(root, RawCode)
    assert root.name.decode() == "<module>"

    nested_names = {rc.name.decode() for rc in reader.all_codes if isinstance(rc.name, bytes)}
    assert "f" in nested_names


def test_pyarmor_regex_matches_marker_call():
    name, regex, _ = next(o for o in obfuscators if o[0] == "PyArmor")
    assert regex.search("some prefix __pyarmor__(__name__, __file__, b'...')")


def test_pyarmor_checked_before_devtool():
    names = [name for name, _, _ in obfuscators]
    assert names.index("PyArmor") < names.index("devtool")


def test_resolve_mode_defaults_to_static_without_a_chooser():
    assert resolve_mode(None) == STATIC_MODE


def test_resolve_mode_hooking_when_chosen():
    assert resolve_mode(lambda: "hooking") == HOOKING_MODE


def test_resolve_mode_anything_else_falls_back_to_static():
    assert resolve_mode(lambda: "nonsense") == STATIC_MODE


def test_pyarmor_never_reaches_hooking_worker_without_a_chooser(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(pyarmor_module.subprocess, "run", fake_run)
    dummy = tmp_path / "sample.py"
    dummy.write_text("__pyarmor__(...)")

    pyarmor_module.pyarmor(str(dummy), confirm_dynamic=None)

    assert len(calls) == 1
    assert "_pyarmor_static.py" in calls[0][1]
    assert not any("_pyarmor_hooking.py" in c[1] for c in calls)


def test_successful_report_gets_the_de4py_signature(tmp_path, monkeypatch):
    output_holder = {}

    def fake_run(cmd, **kwargs):
        output_path = cmd[cmd.index("-o") + 1]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("=== blob[0]  name='<module>' ===\n")
        output_holder["path"] = output_path
        return _subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(pyarmor_module.subprocess, "run", fake_run)
    dummy = tmp_path / "sample.py"
    dummy.write_text("__pyarmor__(...)")

    result = pyarmor_module.pyarmor(str(dummy), confirm_dynamic=None)

    assert result.startswith("# Cleaned with de4py | https://github.com/Fadi002/de4py\n")
    assert "=== blob[0]" in result


def test_hooking_mode_declines_cleanly_on_non_windows(monkeypatch):
    monkeypatch.setattr(pyarmor_module, "IS_WINDOWS", False)
    result = pyarmor_module.pyarmor("does-not-matter.py", confirm_dynamic=lambda: "hooking")
    assert "Windows-only" in result
