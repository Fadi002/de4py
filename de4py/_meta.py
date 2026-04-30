# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Central project metadata and about-info for de4py.

All modules should reference this file for project metadata rather than
hardcoding values. The print_about() / get_project_info() helpers formerly
in about.py now live here so callers have a single canonical import.
"""

PROJECT_NAME = "de4py"
AUTHOR = "Fadi002, Advdebug"
COPYRIGHT = "Copyright (c) 2026 Fadi002"
LICENSE = "CC BY-NC 4.0"
PROJECT_URL = "https://github.com/Fadi002/de4py"
PROJECT_SIGNATURE = "de4py-core-02f446fc20d6"


# ── Project info helpers (previously in about.py) ─────────────────────────────

def get_project_info() -> dict:
    """Return project metadata as a dictionary (version read from settings)."""
    from de4py.config.config import settings
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
