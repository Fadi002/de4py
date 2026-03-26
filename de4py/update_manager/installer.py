# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Safe update installer using a staging-based strategy.

Never overwrites running files directly. Uses a three-phase approach:
1. Extract update to a staging directory (update_temp/)
2. Backup current installation (backup/)
3. Atomic swap: replace current with staged update

If anything fails, the rollback module can restore from backup.
"""

import logging
import os
import shutil
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)


class InstallError(Exception):
    """Raised when update installation fails."""
    pass


def get_update_dirs(base_dir: Optional[str] = None) -> dict:
    """
    Get the standard update directory paths.

    Args:
        base_dir: Base directory for update operations.
                  Defaults to the de4py project root.

    Returns:
        Dict with 'staging', 'backup', and 'downloads' paths.
    """
    if base_dir is None:
        # Default to two levels up from this file (de4py project root)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    return {
        "staging": os.path.join(base_dir, ".update_temp"),
        "backup": os.path.join(base_dir, ".update_backup"),
        "downloads": os.path.join(base_dir, ".update_downloads"),
    }


def stage_update(zip_path: str, base_dir: Optional[str] = None) -> str:
    """
    Extract an update ZIP to the staging directory.

    Args:
        zip_path: Path to the downloaded update ZIP.
        base_dir: Base directory for update operations.

    Returns:
        Path to the staging directory containing the extracted files.

    Raises:
        InstallError: If extraction fails.
    """
    dirs = get_update_dirs(base_dir)
    staging_dir = dirs["staging"]

    try:
        # Clean any previous staging attempt
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)

        os.makedirs(staging_dir, exist_ok=True)

        logger.info(f"Extracting update to staging: {staging_dir}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Security: check for path traversal attacks
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(staging_dir, member))
                if not member_path.startswith(os.path.realpath(staging_dir)):
                    raise InstallError(
                        f"Zip path traversal detected: {member}"
                    )

            zf.extractall(staging_dir)

        # Handle nested directories (GitHub ZIPs often have a single root folder)
        contents = os.listdir(staging_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(staging_dir, contents[0])):
            nested = os.path.join(staging_dir, contents[0])
            # Move contents up one level
            for item in os.listdir(nested):
                shutil.move(
                    os.path.join(nested, item),
                    os.path.join(staging_dir, item),
                )
            os.rmdir(nested)

        logger.info(f"Staging complete: {len(os.listdir(staging_dir))} items")
        return staging_dir

    except zipfile.BadZipFile as e:
        raise InstallError(f"Corrupt update package: {e}") from e
    except OSError as e:
        raise InstallError(f"Failed to stage update: {e}") from e


def backup_current(base_dir: Optional[str] = None) -> str:
    """
    Create a backup of the current installation.

    Args:
        base_dir: Base directory containing the current installation.

    Returns:
        Path to the backup directory.

    Raises:
        InstallError: If backup fails.
    """
    dirs = get_update_dirs(base_dir)
    backup_dir = dirs["backup"]

    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        # Remove old backup if it exists
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

        os.makedirs(backup_dir, exist_ok=True)

        # Back up the de4py package directory
        src = os.path.join(base_dir, "de4py")
        dest = os.path.join(backup_dir, "de4py")

        if os.path.exists(src):
            shutil.copytree(src, dest, dirs_exist_ok=True)
            logger.info(f"Backed up current installation to: {backup_dir}")
        else:
            logger.warning(f"Source directory not found for backup: {src}")

        return backup_dir

    except OSError as e:
        raise InstallError(f"Failed to create backup: {e}") from e


def apply_update(base_dir: Optional[str] = None) -> bool:
    """
    Apply a staged update by swapping it with the current installation.

    This is the critical operation. The sequence is:
    1. Verify staging directory exists and has content
    2. Backup is already created (by backup_current)
    3. Remove current de4py package
    4. Move staged files into place

    Args:
        base_dir: Base directory for update operations.

    Returns:
        True on success.

    Raises:
        InstallError: If the swap fails (rollback should be triggered).
    """
    dirs = get_update_dirs(base_dir)
    staging_dir = dirs["staging"]

    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if not os.path.exists(staging_dir) or not os.listdir(staging_dir):
        raise InstallError("No staged update found. Run stage_update() first.")

    target = os.path.join(base_dir, "de4py")

    try:
        # Check if staged update has a de4py directory
        staged_de4py = os.path.join(staging_dir, "de4py")
        if os.path.isdir(staged_de4py):
            source = staged_de4py
        else:
            source = staging_dir

        # Remove current and replace
        if os.path.exists(target):
            shutil.rmtree(target)

        shutil.copytree(source, target, dirs_exist_ok=True)

        logger.info("Update applied successfully")
        return True

    except OSError as e:
        raise InstallError(
            f"CRITICAL: Failed to apply update. Run --rollback to restore. Error: {e}"
        ) from e


def cleanup(base_dir: Optional[str] = None) -> None:
    """Remove staging and download directories after a successful update."""
    dirs = get_update_dirs(base_dir)

    for key in ("staging", "downloads"):
        path = dirs[key]
        if os.path.exists(path):
            try:
                shutil.rmtree(path)
                logger.debug(f"Cleaned up: {path}")
            except OSError as e:
                logger.warning(f"Failed to clean up {path}: {e}")
