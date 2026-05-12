# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Rollback system for failed updates.

Restores the previous installation from the backup created
during the update process.
"""

import logging
import os
import shutil
from typing import Optional

from .installer import get_update_dirs, MANAGED_ROOT_ITEMS

logger = logging.getLogger(__name__)


class RollbackError(Exception):
    """Raised when rollback fails."""
    pass


def has_backup(base_dir: Optional[str] = None) -> bool:
    """
    Check if a valid backup exists.

    Args:
        base_dir: Base directory for update operations.

    Returns:
        True if a backup directory exists and contains files.
    """
    dirs = get_update_dirs(base_dir)
    backup_dir = dirs["backup"]
    return os.path.isdir(backup_dir) and bool(os.listdir(backup_dir))


def rollback(base_dir: Optional[str] = None) -> bool:
    """
    Restore the previous installation from backup.

    Args:
        base_dir: Base directory for update operations.

    Returns:
        True on successful rollback.

    Raises:
        RollbackError: If no backup exists or restoration fails.
    """
    dirs = get_update_dirs(base_dir)
    backup_dir = dirs["backup"]

    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if not has_backup(base_dir):
        raise RollbackError(
            "No backup available. Cannot rollback.\n"
            "This may mean no update has been applied, or the backup was already cleaned up."
        )

    try:
        logger.warning("Rolling back to previous version...")

        for item in MANAGED_ROOT_ITEMS:
            target = os.path.join(base_dir, item)
            if os.path.isdir(target):
                shutil.rmtree(target)
            elif os.path.exists(target):
                os.remove(target)

        restored_any = False
        for item in MANAGED_ROOT_ITEMS:
            backup_source = os.path.join(backup_dir, item)
            if not os.path.exists(backup_source):
                continue

            target = os.path.join(base_dir, item)
            if os.path.isdir(backup_source):
                shutil.copytree(backup_source, target, dirs_exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(backup_source, target)
            restored_any = True

        if not restored_any:
            raise RollbackError("Backup exists but contains no managed files to restore.")

        logger.info("Rollback successful. Previous version restored.")

        # Clean up staging artifacts
        _cleanup_after_rollback(base_dir)

        return True

    except OSError as e:
        raise RollbackError(
            f"CRITICAL: Rollback failed. Manual restoration required.\n"
            f"Backup location: {backup_dir}\n"
            f"Error: {e}"
        ) from e


def clear_backup(base_dir: Optional[str] = None) -> None:
    """
    Remove the backup directory after confirming the update is stable.

    Args:
        base_dir: Base directory for update operations.
    """
    dirs = get_update_dirs(base_dir)
    backup_dir = dirs["backup"]

    if os.path.exists(backup_dir):
        try:
            shutil.rmtree(backup_dir)
            logger.info("Backup cleared")
        except OSError as e:
            logger.warning(f"Failed to clear backup: {e}")


def _cleanup_after_rollback(base_dir: Optional[str] = None) -> None:
    """Remove staging and download artifacts after a rollback."""
    dirs = get_update_dirs(base_dir)
    for key in ("staging", "downloads"):
        path = dirs[key]
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
            except OSError:
                pass
