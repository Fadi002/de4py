# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
About module for de4py.

Provides programmatic access to project information
and a formatted print function for CLI/startup use.
"""

from de4py._meta import (
    PROJECT_NAME,
    AUTHOR,
    COPYRIGHT,
    LICENSE,
    PROJECT_URL,
)
from de4py.config.config import settings


def get_project_info() -> dict:
    """Return project metadata as a dictionary."""
    return {
        "name": PROJECT_NAME,
        "author": AUTHOR,
        "copyright": COPYRIGHT,
        "license": LICENSE,
        "url": PROJECT_URL,
        "version": settings.version,
    }


def print_about() -> None:
    """Print formatted project information to stdout."""
    info = get_project_info()
    print(f"\n  {info['name']} {info['version']}")
    print(f"  Author: {info['author']}")
    print(f"  License: {info['license']}")
    print(f"  Repository: {info['url']}")
    print(f"  {info['copyright']}")
    print()
