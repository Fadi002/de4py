# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
de4py - Python Deobfuscator & Analyzer
"""

from de4py.config.config import settings
__version__ = settings.version
from de4py._meta import (
    PROJECT_NAME,
    AUTHOR,
    COPYRIGHT,
    LICENSE,
    PROJECT_URL,
    PROJECT_SIGNATURE,
)

__all__ = [
    "__version__",
    "PROJECT_NAME",
    "AUTHOR",
    "COPYRIGHT",
    "LICENSE",
    "PROJECT_URL",
    "PROJECT_SIGNATURE",
]
