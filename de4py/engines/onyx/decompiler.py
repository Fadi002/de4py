# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import subprocess
import sys
import pathlib
import tempfile
import os
from typing import Optional


class Decompiler:

    def decompile(self, pyc_path: str) -> str:
        """
        Attempt to decompile a .pyc file to Python source.
        Returns the source string, or a comment explaining failure.
        """
        methods = [
            ("decompile3",  self._try_decompile3),
            ("pycdc",       self._try_pycdc),
            ("uncompyle6",  self._try_uncompyle6),
        ]

        for name, method in methods:
            result = method(pyc_path)
            if result and len(result.strip()) > 10:
                header = f"# Decompiled with {name}\n# Source: {pyc_path}\n\n"
                return header + result

        return (
            f"# ERROR: All decompilers failed for {pyc_path}\n"
            f"# Try installing: pip install decompile3 uncompyle6\n"
            f"# Or build pycdc from: https://github.com/zrax/pycdc\n"
        )

    def decompile_from_bytes(self, pyc_bytes: bytes, filename: str = "temp.pyc") -> str:
        """Decompile from raw bytes (useful when processing in memory)"""
        with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as f:
            f.write(pyc_bytes)
            tmp_path = f.name
        try:
            return self.decompile(tmp_path)
        finally:
            os.unlink(tmp_path)

    # --- Backend methods ------------------------------------------------------

    def _try_decompile3(self, path: str) -> Optional[str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "decompile3", path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            # decompile3 sometimes writes to stderr on success
            if result.stderr and "def " in result.stderr:
                return result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return None

    def _try_pycdc(self, path: str) -> Optional[str]:
        try:
            result = subprocess.run(
                ["pycdc", path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                # pycdc sometimes outputs non-Python header lines â€” strip them
                lines = result.stdout.splitlines()
                py_lines = [l for l in lines if not l.startswith("#\t") or "decompiled" in l.lower()]
                return "\n".join(py_lines)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _try_uncompyle6(self, path: str) -> Optional[str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "uncompyle6", path],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            pass
        return None

