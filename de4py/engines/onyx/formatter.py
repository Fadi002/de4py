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

import subprocess
import sys
from typing import Optional


class Formatter:

    LINE_LENGTH = 100  # black default is 88; 100 gives more breathing room

    def format(self, source: str) -> str:
        """
        Format source with black. Returns formatted source or original on failure.
        Never raises — formatting failure is non-fatal.
        """
        result = self._run_black(source)
        return result if result is not None else source

    def _run_black(self, source: str) -> Optional[str]:
        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "black",
                    "-",                          # Read from stdin
                    "--quiet",
                    "--line-length", str(self.LINE_LENGTH),
                    "--target-version", "py39",
                ],
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
