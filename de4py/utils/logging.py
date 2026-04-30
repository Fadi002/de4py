# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Logging configuration for de4py.

Sets up file + console handlers with colorized output.
"""

import os
import logging
import datetime
import platform
from logging.handlers import TimedRotatingFileHandler
from colorama import Fore, Style

_initialized = False


class ColorizingStreamHandler(logging.StreamHandler):
    """Console handler that colorizes log output by severity level."""

    _LEVEL_COLORS = {
        logging.INFO: Fore.LIGHTBLUE_EX,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED,
    }

    def emit(self, record):
        message = self.format(record)
        color = self._LEVEL_COLORS.get(record.levelno, "")
        if color:
            print(f"{color}{message}{Style.RESET_ALL}")
        else:
            print(message)


def setup_logging():
    """Initialize file and console logging. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = os.path.join(logs_dir, f"de4py-logs-{timestamp}.log")

    file_handler = TimedRotatingFileHandler(filename=log_filename)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.addHandler(ColorizingStreamHandler())
    root_logger.addHandler(file_handler)

    logging.info(
        f"System Architecture: {platform.architecture()[0]}, "
        f"OS: {platform.platform()}, "
        f"Python Version: {platform.python_version()}"
    )
    _initialized = True
