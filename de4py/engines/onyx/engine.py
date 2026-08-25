# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
from typing import Optional

from de4py.engines.onyx.pipeline import Pipeline

logger = logging.getLogger(__name__)

_WORKER_TIMEOUT_S = float(os.environ.get("DE4PY_ONYX_TIMEOUT", "1800"))


def run_pipeline_rendered(source: str, filename: str = "file.py",
                          ai_overrides: Optional[dict] = None,
                          engine_options: Optional[dict] = None) -> str:
    """Run the pipeline and render the final user-facing text."""
    try:
        pipeline_kwargs = {}
        if ai_overrides:
            for key in ("use_llm", "annotate", "ai_explain", "ai_simplify"):
                if key in ai_overrides:
                    pipeline_kwargs[key] = ai_overrides[key]
        if engine_options is not None:
            pipeline_kwargs["engine_options"] = engine_options
        pipeline = Pipeline(**pipeline_kwargs)
        result = pipeline.run(source, filename=filename)
    except RecursionError:
        logger.error("[Onyx] FATAL: RecursionError — source is too deeply nested")
        return (
            f"# de4py Onyx-Alpha: RecursionError\n"
            f"# The source code is too deeply nested for safe processing.\n"
            f"# Original code preserved below:\n\n{source}"
        )
    except MemoryError:
        logger.error("[Onyx] FATAL: MemoryError — source is too large")
        return (
            f"# de4py Onyx-Alpha: MemoryError\n"
            f"# The system ran out of memory while processing.\n"
            f"# Original code preserved below:\n\n{source}"
        )
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error("[Onyx] FATAL: Unhandled pipeline error: %s", e)
        return (
            f"# de4py Onyx-Alpha: Internal error\n"
            f"# {type(e).__name__}: {e}\n"
            f"# Original code preserved below:\n\n{source}"
        )

    if not result.success:
        return (
            f"de4py Onyx-Alpha failed (Syntax Error in output)\n{'-'*40}\n"
            f"Log: {result.log}\n{'-'*40}\n"
            f"Original code preserved:\n\n{result.original}"
        )

    header = [
        "# Cleaned by de4py Onyx-Alpha",
        f"# Engines used: {', '.join(result.log) if result.log else 'None'}",
        f"# Triage Score: {result.triage.score:.1f}/10.0" if result.triage else "",
        "\n",
    ]

    if result.ai_summary:
        summary_block = "\n".join(
            f"# {line}" if line else "#"
            for line in result.ai_summary.splitlines()
        )
        header.append(f"# {'='*50} AI REVIEW START {'='*50}")
        header.append(f"# AI Analysis:\n{summary_block}")
        header.append(f"# {'='*50} AI REVIEW END {'='*51}")

    if result.explain_text:
        header.append(f"# {'='*20} ENGINE EXPLAIN {'='*20}")
        header.extend("# " + line for line in result.explain_text.splitlines())

    if result.stats:
        pairs = ", ".join(f"{k}={v}" for k, v in sorted(result.stats.items()) if v)
        if pairs:
            header.append(f"# Stats: {pairs}")

    return "\n".join(header) + "\n" + result.cleaned


def _repo_root() -> str:
    import de4py
    return os.path.dirname(os.path.dirname(os.path.abspath(de4py.__file__)))


def run_isolated(source: str, filename: str, ai_overrides: Optional[dict],
                 engine_options: Optional[dict]) -> str:
    """Run the engine in a throwaway interpreter process.

    A native crash inside the child (deep-AST C-stack overflow, extension
    fault) cannot touch the host: it surfaces here as an exit code and becomes
    a graceful preserved-source message.
    """
    workdir = tempfile.mkdtemp(prefix="onyx-worker-")
    job_path = os.path.join(workdir, "job.json")
    out_path = os.path.join(workdir, "result.txt")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump({"source": source, "filename": filename,
                   "ai_overrides": ai_overrides,
                   "engine_options": engine_options}, f)

    proc = subprocess.run(
        [sys.executable, "-m", "de4py.engines.onyx.worker", job_path, out_path],
        stderr=subprocess.PIPE, text=True, timeout=_WORKER_TIMEOUT_S,
        cwd=_repo_root(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"worker exited with code {proc.returncode}")
    if not os.path.exists(out_path):
        raise RuntimeError("worker produced no result")
    with open(out_path, "r", encoding="utf-8") as f:
        text = f.read()
    if not text:
        raise RuntimeError("worker produced an empty result")
    return text


class OnyxAlpha:
    def deobfuscate(self, file_path: str, ai_overrides: Optional[dict] = None,
                    engine_options: Optional[dict] = None) -> str:
        if not os.path.exists(file_path):
            return f"Error: File not found: {file_path}"

        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
        except Exception as e:
            return f"Error reading file: {e}"
        source = raw.decode('utf-8', errors='ignore')

        def _feed():
            try:
                from de4py.engines.onyx.feeder import feed_bytes_bg
                feed_bytes_bg(os.path.basename(file_path), raw)
            except Exception:
                pass

        threading.Thread(target=_feed, daemon=True).start()

        filename = os.path.basename(file_path)

        if os.environ.get("DE4PY_INPROCESS") != "1":
            try:
                return run_isolated(source, filename, ai_overrides, engine_options)
            except subprocess.TimeoutExpired:
                logger.error("[Onyx] Worker timed out after %ss", _WORKER_TIMEOUT_S)
                return (
                    f"# de4py Onyx-Alpha: the engine gave up on this file "
                    f"after {_WORKER_TIMEOUT_S:.0f}s\n"
                    f"# The host application is unaffected.\n"
                    f"# Original code preserved below:\n\n{source}"
                )
            except RuntimeError as e:
                logger.error("[Onyx] Worker crashed: %s", e)
                return (
                    f"# de4py Onyx-Alpha: the engine could not survive this "
                    f"sample internally ({e})\n"
                    f"# The host application is unaffected.\n"
                    f"# Original code preserved below:\n\n{source}"
                )
            except OSError as e:
                logger.warning("[Onyx] Worker spawn failed (%s) — running "
                               "in-process", e)

        return run_pipeline_rendered(source, filename, ai_overrides, engine_options)
