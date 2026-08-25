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

from de4py.tui.commands import Command, CommandRegistry, CommandError, _ReplArgumentParser


def _add_path_arg(parser):
    parser.add_argument("path", nargs="?", default=None)


def test_parser_raises_command_error_not_system_exit():
    parser = _ReplArgumentParser(prog="test", add_help=False)
    _add_path_arg(parser)
    try:
        parser.parse_args(["--unknown-flag"])
        assert False, "expected CommandError"
    except CommandError:
        pass


def test_dispatch_routes_to_handler_with_explicit_argument():
    seen = {}

    def handler(args):
        seen["path"] = args.path

    registry = CommandRegistry()
    registry.register(Command("set_file", "help text", handler, _add_path_arg))

    registry.dispatch("set_file /tmp/sample.py")

    assert seen["path"] == "/tmp/sample.py"


def test_dispatch_with_no_argument_passes_none():
    seen = {}

    def handler(args):
        seen["path"] = args.path

    registry = CommandRegistry()
    registry.register(Command("set_file", "help text", handler, _add_path_arg))

    registry.dispatch("set_file")

    assert seen["path"] is None


def test_dispatch_unknown_command_prints_message(capsys):
    registry = CommandRegistry()
    registry.dispatch("nonexistent")
    assert "Unknown command" in capsys.readouterr().out


def test_dispatch_empty_line_is_a_noop():
    registry = CommandRegistry()
    assert registry.dispatch("   ") is True


def test_dispatch_quoted_path_with_spaces():
    seen = {}

    def handler(args):
        seen["path"] = args.path

    registry = CommandRegistry()
    registry.register(Command("set_file", "help text", handler, _add_path_arg))

    registry.dispatch('set_file "C:\\my files\\a.py"')

    assert seen["path"] == "C:\\my files\\a.py"


def test_dispatch_unquoted_windows_path_preserves_backslashes():
    seen = {}

    def handler(args):
        seen["path"] = args.path

    registry = CommandRegistry()
    registry.register(Command("set_file", "help text", handler, _add_path_arg))

    registry.dispatch("set_file C:\\Users\\me\\a.py")

    assert seen["path"] == "C:\\Users\\me\\a.py"


def test_handler_returning_false_stops_the_loop():
    registry = CommandRegistry()
    registry.register(Command("back", "help", lambda args: False))
    assert registry.dispatch("back") is False


def test_handler_returning_none_keeps_the_loop_going():
    registry = CommandRegistry()
    registry.register(Command("noop", "help", lambda args: None))
    assert registry.dispatch("noop") is True


def test_help_lines_reflects_every_registered_command_in_order():
    registry = CommandRegistry()
    registry.register(Command("a", "help a", lambda args: None))
    registry.register(Command("b", "help b", lambda args: None))
    assert registry.help_lines() == [("a", "help a"), ("b", "help b")]


def test_bad_flag_prints_error_and_does_not_call_handler(capsys):
    called = {"ran": False}

    def handler(args):
        called["ran"] = True

    registry = CommandRegistry()
    registry.register(Command("set_file", "help text", handler, _add_path_arg))

    registry.dispatch("set_file --nope")

    assert called["ran"] is False
    assert "set_file" in capsys.readouterr().out
