# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Fire-and-forget telemetry ping.

Import this module from anywhere in the app (e.g. the core package) and it
immediately requests a single telemetry ping on a daemon thread. It never
blocks startup and never raises -- if the network call fails, it silently
no-ops.
"""

import logging
import threading

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()


def _fire():
    try:
        from de4py.api.telemetry import send_ping
        send_ping()
    except Exception as e:
        logger.debug(f"Telemetry ping skipped: {e}")


def start():
    """Start the one-shot ping on a daemon thread exactly once."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    try:
        t = threading.Thread(target=_fire, daemon=True)
        t.start()
    except Exception:
        pass


start()