# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Main update orchestrator.

Coordinates the entire update lifecycle:
check → download → verify → stage → backup → apply → cleanup/rollback.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Callable

from .versioning import parse_version, is_newer, format_version_info
from .github_api import (
    get_latest_release,
    get_latest_version_raw,
    ReleaseInfo,
    GitHubAPIError,
)
from .downloader import download_file, verify_integrity, DownloadError, IntegrityError
from .installer import (
    get_update_dirs,
    stage_update,
    backup_current,
    apply_update,
    cleanup,
    InstallError,
)
from .rollback import rollback as do_rollback, has_backup, RollbackError

logger = logging.getLogger(__name__)


class UpdateManager:
    """
    Production-grade update manager for de4py.

    Supports auto-update on startup, manual update checks,
    safe installation with rollback capability.
    """

    def __init__(
        self,
        current_version: str,
        repo: Optional[str] = None,
        channel: str = "stable",
        auto_update: bool = True,
        base_dir: Optional[str] = None,
    ):
        from de4py.config.config import settings
        self.current_version = current_version
        self.repo = repo or getattr(settings, "github_repo", "Fadi002/de4py")
        self.channel = channel
        self.auto_update_enabled = auto_update
        self.base_dir = base_dir

        from de4py.config.config import settings
        self.api_timeout = getattr(settings, "api_timeout", 7)
        self.download_timeout = getattr(settings, "download_timeout", 30)

    # ── Check ────────────────────────────────────────────────────────

    def check(self) -> Optional[ReleaseInfo]:
        """
        Check for available updates.

        Tries the GitHub Releases API first, then falls back to
        the raw version file.

        Returns:
            ReleaseInfo if an update is available, None if up-to-date.
        """
        release = None

        # Primary: GitHub Releases API
        try:
            release = get_latest_release(
                self.repo, channel=self.channel, timeout=self.api_timeout
            )
        except GitHubAPIError:
            logger.info("Releases API unavailable, trying fallback...")

        # Fallback: raw version file
        if release is None:
            from de4py.config.config import settings
            raw_version = get_latest_version_raw(settings.version_url, timeout=self.api_timeout)
            if raw_version:
                release = ReleaseInfo(version=raw_version.lstrip("Vv"))

        if release is None:
            logger.warning("Could not determine latest version from any source")
            return None

        if is_newer(self.current_version, release.version):
            logger.info(format_version_info(self.current_version, release.version))
            return release
        else:
            logger.info(format_version_info(self.current_version, release.version))
            return None

    # ── Download & Install ───────────────────────────────────────────

    def download_and_install(
        self,
        release: ReleaseInfo,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Full update flow: download → verify → stage → backup → apply.

        Args:
            release: Release info from check().
            progress_callback: Optional download progress callback.

        Returns:
            True on success, False on failure (with rollback attempted).
        """
        dirs = get_update_dirs(self.base_dir)

        if not release.download_url:
            logger.error("No download URL available for this release")
            return False

        try:
            # 1. Download
            dest = os.path.join(dirs["downloads"], f"de4py-{release.version}.zip")
            download_file(
                release.download_url,
                dest,
                progress_callback=progress_callback,
                timeout=self.download_timeout,
            )

            # 2. Verify integrity (if SHA256 is available)
            if release.sha256:
                verify_integrity(dest, release.sha256)
            else:
                logger.warning("No SHA256 hash available — skipping integrity check")

            # 3. Stage
            stage_update(dest, self.base_dir)

            # 4. Backup current
            backup_current(self.base_dir)

            # 5. Apply
            apply_update(self.base_dir)

            # 6. Cleanup
            cleanup(self.base_dir)

            logger.info(
                f"Update to {release.version} installed successfully. "
                f"Please restart de4py to apply changes."
            )
            return True

        except (DownloadError, IntegrityError, InstallError) as e:
            logger.error(f"Update failed: {e}")
            self._attempt_rollback()
            return False

    # ── Auto Update (Startup Flow) ──────────────────────────────────

    def auto_check(self) -> Optional[ReleaseInfo]:
        """
        Startup auto-update check.

        Returns:
            ReleaseInfo if update is available and auto_update is enabled,
            None otherwise.
        """
        if not self.auto_update_enabled:
            logger.debug("Auto-update is disabled")
            return None

        try:
            return self.check()
        except Exception as e:
            logger.error(f"Auto-update check failed: {e}")
            return None

    # ── Rollback ─────────────────────────────────────────────────────

    def rollback(self) -> bool:
        """
        Rollback to the previous version.

        Returns:
            True on success.
        """
        try:
            return do_rollback(self.base_dir)
        except RollbackError as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def has_rollback_available(self) -> bool:
        """Check if a backup is available for rollback."""
        return has_backup(self.base_dir)

    # ── Private ──────────────────────────────────────────────────────

    def _attempt_rollback(self) -> None:
        """Try to rollback after a failed update."""
        if has_backup(self.base_dir):
            logger.warning("Attempting automatic rollback...")
            try:
                do_rollback(self.base_dir)
                logger.info("Automatic rollback successful")
            except RollbackError as e:
                logger.critical(f"Automatic rollback also failed: {e}")
        else:
            logger.warning("No backup available for automatic rollback")
