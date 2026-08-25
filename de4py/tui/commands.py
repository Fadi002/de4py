# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import argparse
import shlex
from dataclasses import dataclass
from typing import Callable, Optional, Tuple


class CommandError(Exception):
    pass


class _ReplArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise CommandError(message)

    def exit(self, status=0, message=None):
        if message:
            raise CommandError(message)


def _no_arguments(parser: argparse.ArgumentParser) -> None:
    return None


def _split_command_line(line: str) -> list:
    lexer = shlex.shlex(line, posix=True)
    lexer.whitespace_split = True
    lexer.escape = ""
    lexer.escapedquotes = ""
    return list(lexer)


@dataclass
class Command:
    name: str
    help: str
    handler: Callable[[argparse.Namespace], object]
    add_arguments: Callable[[argparse.ArgumentParser], None] = _no_arguments
    aliases: Tuple[str, ...] = ()


class CommandRegistry:
    def __init__(self):
        self._commands = {}
        self._order = []

    def register(self, command: Command) -> None:
        self._commands[command.name] = command
        self._order.append(command.name)
        for alias in command.aliases:
            self._commands[alias] = command

    def get(self, name: str) -> Optional[Command]:
        return self._commands.get(name)

    def help_lines(self):
        return [(name, self._commands[name].help) for name in self._order]

    def dispatch(self, line: str) -> bool:
        line = line.strip()
        if not line:
            return True
        try:
            tokens = _split_command_line(line)
        except ValueError as e:
            print(f"Could not parse command line: {e}")
            return True

        name, raw_args = tokens[0], tokens[1:]
        command = self._commands.get(name)
        if command is None:
            print(f"Unknown command: {name}")
            return True

        parser = _ReplArgumentParser(prog=command.name, add_help=False)
        command.add_arguments(parser)
        try:
            args = parser.parse_args(raw_args)
        except CommandError as e:
            print(f"{command.name}: {e}")
            return True

        return command.handler(args) is not False


def run_repl(registry: CommandRegistry, prompt_fn: Callable[[], None]) -> None:
    while True:
        prompt_fn()
        line = input()
        if not registry.dispatch(line):
            break
