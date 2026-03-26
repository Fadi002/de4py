# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Semantic versioning utilities.

Handles version parsing, comparison, and formatting for de4py's
update system. Supports the project's "V3.1.1" format.
"""

from typing import Tuple


def parse_version(version_string: str) -> Tuple[int, ...]:
    """
    Parse a version string into a comparable tuple of integers.

    Strips leading 'V'/'v' prefix and splits on '.'.
    Falls back to (0, 0, 0) on malformed input.

    Examples:
        >>> parse_version("V3.1.1")
        (3, 1, 1)
        >>> parse_version("3.1.1")
        (3, 1, 1)
        >>> parse_version("V2.0.0-beta")
        (2, 0, 0)
    """
    cleaned = version_string.strip().lstrip("Vv").strip()
    # Strip any pre-release suffix (e.g., "-beta", "-rc1")
    base = cleaned.split("-")[0]
    try:
        return tuple(int(part) for part in base.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def version_to_str(version_tuple: Tuple[int, ...], prefix: str = "V") -> str:
    """
    Convert a version tuple back to a display string.

    Examples:
        >>> version_to_str((3, 1, 1))
        'V3.1.1'
        >>> version_to_str((3, 1, 1), prefix="")
        '3.1.1'
    """
    return f"{prefix}{'.'.join(str(p) for p in version_tuple)}"


def is_newer(local: str, remote: str) -> bool:
    """
    Compare two version strings. Returns True if remote is newer than local.

    Examples:
        >>> is_newer("V3.1.1", "V3.2.0")
        True
        >>> is_newer("V3.1.1", "V3.1.1")
        False
        >>> is_newer("V3.2.0", "V3.1.1")
        False
    """
    return parse_version(remote) > parse_version(local)


def format_version_info(local: str, remote: str) -> str:
    """Format a human-readable version comparison string."""
    local_t = parse_version(local)
    remote_t = parse_version(remote)

    if remote_t > local_t:
        return (
            f"Update available: {version_to_str(local_t)} → {version_to_str(remote_t)}"
        )
    elif remote_t == local_t:
        return f"You are running the latest version ({version_to_str(local_t)})"
    else:
        return f"You are running a newer version ({version_to_str(local_t)}) than the latest release ({version_to_str(remote_t)})"
