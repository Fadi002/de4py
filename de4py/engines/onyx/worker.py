# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Isolated engine worker: argv[1] = job JSON, argv[2] = result file.

Launched as a subprocess so a pathological sample can never take the host
app down; a native crash here surfaces in the parent as an exit code.
Job: {"source", "filename", "ai_overrides", "engine_options"}.
Result: UTF-8 text of the full render, or nothing on failure."""

import json
import logging
import os
import sys


def _setup_worker_logging():
    log_dir = os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        "logs")
    os.makedirs(log_dir, exist_ok=True)
    from datetime import datetime
    log_file = os.path.join(
        log_dir,
        f"de4py-worker-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s"))
    logging.getLogger("de4py.engines.onyx").addHandler(handler)
    logging.getLogger("de4py.engines.onyx").setLevel(logging.DEBUG)
    return log_file


def main(argv):
    if len(argv) != 3:
        return 2
    if os.environ.get("DE4PY_WORKER_TEST_CRASH") == "1":
        os._exit(1)
    with open(argv[1], "r", encoding="utf-8") as f:
        job = json.load(f)

    _setup_worker_logging()

    from de4py.engines.onyx.engine import run_pipeline_rendered

    result_text = run_pipeline_rendered(job["source"], job.get("filename", "file.py"),
                                        job.get("ai_overrides"),
                                        job.get("engine_options"))
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(result_text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
