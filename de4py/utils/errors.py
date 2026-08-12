# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Global exception hook for de4py.

Provides formatted tracebacks and optional telemetry reporting.
"""

import sys
import logging
from traceback import extract_tb
from colorama import Fore, Style


def custom_error(exc_type, exc_value, exc_traceback):
    """Formatted exception hook with optional Sentry + telemetry reporting."""
    if issubclass(exc_type, KeyboardInterrupt):
        return

    print(f"{Fore.RED}=== Start Traceback ==={Style.RESET_ALL}")
    print(f"{Fore.RED}Error Type:{Style.RESET_ALL} {exc_type.__name__}")
    print(f"{Fore.RED}Error Message:{Style.RESET_ALL} {exc_value}")
    print(f"{Fore.RED}Traceback:{Style.RESET_ALL}")

    traceback_lines = []
    for filename, line_num, func_name, line_code in extract_tb(exc_traceback):
        traceback_lines.append(
            f"  File '{filename}', line {line_num}, in {func_name}\n    {line_code}"
        )
    print("\n".join(traceback_lines))
    print(f"{Fore.RED}=== End of Traceback ==={Style.RESET_ALL}")

    from de4py.config.config import settings
    if not settings.telemetry:
        return

    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc_value)
    except Exception:
        pass

    try:
        from de4py.api.telemetry import report_error
        report_error(
            source="core",
            source_name="global_exception",
            severity="critical",
            error_type=exc_type.__name__,
            error_message=str(exc_value),
            traceback_str="\n".join(traceback_lines),
        )
    except Exception as e:
        logging.debug(f"Failed to send telemetry: {e}")


def install():
    """Install the custom exception hook."""
    sys.excepthook = custom_error
