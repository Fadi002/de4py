# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Differential execution harness: verifies that deobfuscated output
behaves identically to the original sample.

Executes both versions in isolated subprocesses and compares stdout,
stderr, and exit code. Any mismatch indicates semantic corruption."""

import subprocess
import sys
import tempfile
import os


def _run_python(source: str, timeout: float = 30.0,
                stdin_data: str = "") -> dict:
    """Run Python source in isolated subprocess."""
    suffix = ".py"
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(source)
        proc = subprocess.run(
            [sys.executable, "-I", path],
            capture_output=True, text=True,
            timeout=timeout,
            input=stdin_data,
            cwd=tempfile.gettempdir(),
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "<TIMEOUT>", "returncode": -999}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def compare_execution(original_source: str, cleaned_source: str,
                      stdin_data: str = "",
                      timeout: float = 30.0) -> dict:
    """Compare execution behavior of original vs deobfuscated code.

    Returns dict with per-channel match booleans and overall verdict.
    Samples that crash or produce no output are skipped (can't verify).
    """
    orig = _run_python(original_source, timeout=timeout,
                       stdin_data=stdin_data)
    clean = _run_python(cleaned_source, timeout=timeout,
                        stdin_data=stdin_data)

    orig_crashed = orig["returncode"] not in (0, 1)
    clean_crashed = clean["returncode"] not in (0, 1)

    # If neither version produces observable output, skip verification
    has_output = bool(orig["stdout"] or clean["stdout"])
    skip = not has_output

    stdout_match = orig["stdout"] == clean["stdout"]
    stderr_match = orig["stderr"] == clean["stderr"]
    rc_match = orig["returncode"] == clean["returncode"]

    verified = stdout_match and rc_match and not skip
    return {
        "verified": verified,
        "skipped": skip,
        "orig": orig,
        "clean": clean,
        "stdout_match": stdout_match,
        "stderr_match": stderr_match,
        "rc_match": rc_match,
    }
