# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
de4py.utils — Shared utilities package.

Submodules:
    logging     — File + console log setup
    errors      — Global exception hook (call errors.install() to activate)
    sentry      — Sentry SDK integration
    rpc         — Discord Rich Presence
    tui         — Console display (banners, formatting, animations)
    fs          — Filesystem helpers: temp paths + checksum generation
    shell       — Native process injection helpers (pyshell)
    test        — Diagnostic self-test
"""

# Commonly imported symbols re-exported for convenience.
from .logging import setup_logging                                      # noqa: F401
from .errors import custom_error                                        # noqa: F401
from .tui import clear_console, fade_type, __BANNER__                   # noqa: F401
from .fs import gen_path                                                # noqa: F401
