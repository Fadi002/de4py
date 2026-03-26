# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
de4py UpdateManager — Production-grade auto-update, manual update, and rollback.
"""

from .updater import UpdateManager
from .versioning import parse_version, version_to_str

__all__ = ["UpdateManager", "parse_version", "version_to_str"]
