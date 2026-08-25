# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import contextlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from de4py.main import build_arg_parser, run_tui_if_requested


def test_tui_flag_parses():
    args = build_arg_parser().parse_args(["--tui"])
    assert args.tui is True
    assert args.cli is False


def test_cli_flag_still_parses_as_deprecated_alias():
    args = build_arg_parser().parse_args(["--cli"])
    assert args.cli is True


def test_cli_flag_hidden_from_help():
    help_text = build_arg_parser().format_help()
    assert "--tui" in help_text
    assert "--cli" not in help_text


def test_neither_flag_does_not_start_tui(monkeypatch):
    import de4py.tui.cli as cli_module
    monkeypatch.setattr(cli_module, "start", lambda: (_ for _ in ()).throw(AssertionError("should not start")))

    args = build_arg_parser().parse_args([])
    assert run_tui_if_requested(args) is False


def test_tui_flag_calls_cli_start(monkeypatch):
    import de4py.tui.cli as cli_module
    import de4py.utils.sentry as sentry_module

    monkeypatch.setattr(sentry_module, "transaction", lambda *a, **k: contextlib.nullcontext())
    called = {"started": False}
    monkeypatch.setattr(cli_module, "start", lambda: called.__setitem__("started", True))

    args = build_arg_parser().parse_args(["--tui"])
    assert run_tui_if_requested(args) is True
    assert called["started"] is True


def test_deprecated_cli_flag_still_calls_cli_start_with_warning(monkeypatch, capsys):
    import de4py.tui.cli as cli_module
    import de4py.utils.sentry as sentry_module

    monkeypatch.setattr(sentry_module, "transaction", lambda *a, **k: contextlib.nullcontext())
    called = {"started": False}
    monkeypatch.setattr(cli_module, "start", lambda: called.__setitem__("started", True))

    args = build_arg_parser().parse_args(["--cli"])
    assert run_tui_if_requested(args) is True
    assert called["started"] is True
    assert "deprecated" in capsys.readouterr().err.lower()
