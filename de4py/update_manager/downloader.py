# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
Secure file downloader with integrity verification.

Handles streaming downloads with progress reporting and
SHA256 hash verification for update packages.
"""

import hashlib
import logging
import os
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

CHUNK_SIZE = 8192
DEFAULT_TIMEOUT = 60


class DownloadError(Exception):
    """Raised when a download fails."""
    pass


class IntegrityError(Exception):
    """Raised when integrity verification fails."""
    pass


def download_file(
    url: str,
    dest: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """
    Download a file with streaming and optional progress reporting.

    Args:
        url: URL to download from.
        dest: Destination file path. Parent directories are created if needed.
        progress_callback: Optional callable(downloaded_bytes, total_bytes).
        timeout: Request timeout in seconds.

    Returns:
        Absolute path to the downloaded file.

    Raises:
        DownloadError: On network or filesystem errors.
    """
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0

        logger.info(f"Downloading update ({_format_size(total_size)}) from {url}")

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        logger.info(f"Download complete: {dest} ({_format_size(downloaded)})")
        return os.path.abspath(dest)

    except requests.exceptions.RequestException as e:
        # Clean up partial download
        _safe_remove(dest)
        raise DownloadError(f"Download failed: {e}") from e
    except OSError as e:
        _safe_remove(dest)
        raise DownloadError(f"Failed to write file: {e}") from e


def verify_integrity(file_path: str, expected_sha256: str) -> bool:
    """
    Verify a file's SHA256 hash against an expected value.

    Args:
        file_path: Path to the file to verify.
        expected_sha256: Expected SHA256 hex digest (case-insensitive).

    Returns:
        True if the hash matches.

    Raises:
        IntegrityError: If the hash does not match.
        FileNotFoundError: If the file does not exist.
    """
    if not expected_sha256:
        logger.warning("No SHA256 hash provided — skipping integrity check")
        return True

    actual = compute_sha256(file_path)
    expected = expected_sha256.lower().strip()

    if actual != expected:
        raise IntegrityError(
            f"Integrity check failed for {os.path.basename(file_path)}.\n"
            f"  Expected: {expected}\n"
            f"  Actual:   {actual}"
        )

    logger.info(f"Integrity verified: {os.path.basename(file_path)} (SHA256 OK)")
    return True


def compute_sha256(file_path: str) -> str:
    """Compute the SHA256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes == 0:
        return "unknown size"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _safe_remove(path: str) -> None:
    """Remove a file if it exists, silently ignoring errors."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
