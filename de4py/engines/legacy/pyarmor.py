# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from de4py.utils.platform_utils import IS_WINDOWS

STATIC_MODE = "static"
HOOKING_MODE = "hooking"

_SIGNATURE = "# Cleaned with de4py | https://github.com/Fadi002/de4py\n"

_STATIC_TIMEOUT = 120
_HOOKING_TIMEOUT = 60


def resolve_mode(confirm_dynamic) -> str:
    if confirm_dynamic is None:
        return STATIC_MODE
    mode = confirm_dynamic()
    return mode if mode == HOOKING_MODE else STATIC_MODE


def _run_worker(worker_filename: str, file_path: str, timeout: int) -> str:
    worker_path = str(Path(__file__).with_name(worker_filename))
    fd, output_path = tempfile.mkstemp(suffix=".txt", prefix="de4py_pyarmor_")
    os.close(fd)
    try:
        proc = subprocess.run(
            [sys.executable, worker_path, file_path, "-o", output_path],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        report = ""
        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8", errors="replace") as f:
                report = f.read()
        if report.strip():
            return _SIGNATURE + report
        stderr_tail = "\n".join((proc.stderr or "").strip().splitlines()[-20:])
        return (
            f"# ERROR: PyArmor recovery produced no output.\n"
            f"# exit code: {proc.returncode}\n"
            f"# stderr:\n{stderr_tail}"
        )
    except subprocess.TimeoutExpired:
        return f"# ERROR: PyArmor recovery timed out after {timeout}s."
    finally:
        try:
            os.unlink(output_path)
        except OSError:
            pass


def pyarmor(file_path: str, confirm_dynamic=None) -> str:
    mode = resolve_mode(confirm_dynamic)

    if mode == HOOKING_MODE:
        if not IS_WINDOWS:
            return (
                "# ERROR: dynamic/hooking PyArmor recovery is Windows-only "
                "(it patches the target's native runtime in memory). Use the "
                "static recovery mode on this platform."
            )
        return _run_worker("_pyarmor_hooking.py", file_path, _HOOKING_TIMEOUT)

    return _run_worker("_pyarmor_static.py", file_path, _STATIC_TIMEOUT)
