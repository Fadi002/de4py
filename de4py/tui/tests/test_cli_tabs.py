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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import de4py.tui.cli as cli_module


def test_deobfuscator_set_file_with_explicit_path_skips_picker(monkeypatch):
    called = {"picker": False}

    def fake_picker():
        called["picker"] = True
        return "should-not-be-used.py"

    monkeypatch.setattr(cli_module, "file_explorer", fake_picker)
    state = {"file_path": None}
    registry = cli_module._build_deobfuscator_registry(state)

    registry.dispatch("set_file /path/to/file.txt")

    assert state["file_path"] == "/path/to/file.txt"
    assert called["picker"] is False


def test_deobfuscator_set_file_without_path_opens_picker(monkeypatch):
    monkeypatch.setattr(cli_module, "file_explorer", lambda: "/picked/path.py")
    state = {"file_path": None}
    registry = cli_module._build_deobfuscator_registry(state)

    registry.dispatch("set_file")

    assert state["file_path"] == "/picked/path.py"


def test_deobfuscator_start_with_no_file_selected_prints_warning(capsys):
    state = {"file_path": None}
    registry = cli_module._build_deobfuscator_registry(state)

    registry.dispatch("start")

    assert "No file selected" in capsys.readouterr().out


def test_analyzer_set_file_with_explicit_path_skips_picker(monkeypatch):
    called = {"picker": False}

    def fake_picker():
        called["picker"] = True
        return "nope.py"

    monkeypatch.setattr(cli_module, "file_explorer", fake_picker)
    state = {"file_path": None}
    registry = cli_module._build_analyzer_registry(state)

    registry.dispatch("set_file /path/to/sample.exe")

    assert state["file_path"] == "/path/to/sample.exe"
    assert called["picker"] is False


def test_analyzer_get_file_hashs_with_no_file_selected_prints_warning(capsys):
    state = {"file_path": None}
    registry = cli_module._build_analyzer_registry(state)

    registry.dispatch("get_file_hashs")

    assert "No file selected" in capsys.readouterr().out


def test_analyzer_registry_help_lines_include_back_and_help():
    state = {"file_path": None}
    registry = cli_module._build_analyzer_registry(state)
    names = [name for name, _ in registry.help_lines()]
    assert "back" in names
    assert "help" in names


def test_pyshell_exec_file_with_explicit_path_skips_picker(monkeypatch):
    called = {"picker": False}

    def fake_picker():
        called["picker"] = True
        return "nope.py"

    monkeypatch.setattr(cli_module, "file_explorer", fake_picker)

    class FakeShell:
        def __init__(self):
            self.received = None

        def execute_python_file(self, path):
            self.received = path
            return True

    shell = FakeShell()
    registry = cli_module._build_pyshell_registry(shell, 1234)

    registry.dispatch("exec_file /path/to/script.py")

    assert shell.received == "/path/to/script.py"
    assert called["picker"] is False


def test_pyshell_exec_file_without_path_opens_picker(monkeypatch):
    monkeypatch.setattr(cli_module, "file_explorer", lambda: "/picked/script.py")

    class FakeShell:
        def __init__(self):
            self.received = None

        def execute_python_file(self, path):
            self.received = path
            return True

    shell = FakeShell()
    registry = cli_module._build_pyshell_registry(shell, 1234)

    registry.dispatch("exec_file")

    assert shell.received == "/picked/script.py"


def test_pyshell_registry_has_no_clear_or_exit_command():
    registry = cli_module._build_pyshell_registry(object(), 1234)
    names = [name for name, _ in registry.help_lines()]
    assert "clear" not in names
    assert "exit" not in names
