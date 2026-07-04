# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Runs black on Python source code.
"""

import ast
import subprocess
import sys
from functools import lru_cache
from importlib.util import find_spec
from shutil import which
from typing import Optional


@lru_cache(maxsize=1)
def _resolve_black_command() -> Optional[tuple[str, ...]]:
    """Resolve the cheapest usable Black entrypoint once per process."""
    black_exe = which("black")
    if black_exe:
        return (
            black_exe,
            "-",
            "--quiet",
            "--line-length",
            str(Formatter.LINE_LENGTH),
            "--target-version",
            "py39",
        )

    if find_spec("black") is not None:
        return (
            sys.executable,
            "-m",
            "black",
            "-",
            "--quiet",
            "--line-length",
            str(Formatter.LINE_LENGTH),
            "--target-version",
            "py39",
        )

    return None


class Formatter:

    LINE_LENGTH = 100  # black default is 88; 100 gives more breathing room

    def format(self, source: str) -> str:
        """
        Format source with black. Returns formatted source or original on failure.
        Never raises — formatting failure is non-fatal.
        """
        if not source.strip():
            return source

        result = self._run_black(source)
        return result if result is not None else source

    def _run_black(self, source: str) -> Optional[str]:
        cmd = _resolve_black_command()
        if cmd is None:
            return None

        if not self._is_valid_python(source):
            return None

        try:
            proc = subprocess.run(
                list(cmd),
                input=source.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return proc.stdout.decode("utf-8")
            # black exit code 123 means the code has syntax errors — non-fatal
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return None

    @staticmethod
    def _is_valid_python(source: str) -> bool:
        try:
            ast.parse(source)
        except SyntaxError:
            return False
        return True
