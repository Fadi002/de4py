# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
GitHub API communication layer.

Handles fetching release information from the GitHub Releases API
with a fallback to the raw version file.
"""

import logging
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT = 15


class GitHubAPIError(Exception):
    """Raised when GitHub API communication fails."""
    pass


class ReleaseInfo:
    """Structured representation of a GitHub release."""

    __slots__ = (
        "version", "tag_name", "changelog", "download_url",
        "sha256", "published_at", "prerelease", "assets",
    )

    def __init__(
        self,
        version: str,
        tag_name: str = "",
        changelog: str = "",
        download_url: str = "",
        sha256: str = "",
        published_at: str = "",
        prerelease: bool = False,
        assets: Optional[List[Dict[str, Any]]] = None,
    ):
        self.version = version
        self.tag_name = tag_name
        self.changelog = changelog
        self.download_url = download_url
        self.sha256 = sha256
        self.published_at = published_at
        self.prerelease = prerelease
        self.assets = assets or []

    def __repr__(self) -> str:
        return f"ReleaseInfo(version={self.version!r}, prerelease={self.prerelease})"


def get_latest_release(
    repo: str,
    channel: str = "stable",
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[ReleaseInfo]:
    """
    Fetch the latest release from GitHub Releases API.

    Args:
        repo: Repository in "owner/repo" format (e.g., "Fadi002/de4py").
        channel: "stable" for latest release, "beta"/"dev" for pre-releases.
        timeout: Request timeout in seconds.

    Returns:
        ReleaseInfo on success, None if no suitable release found.

    Raises:
        GitHubAPIError: On network/API errors.
    """
    try:
        if channel == "stable":
            url = f"{GITHUB_API_BASE}/repos/{repo}/releases/latest"
            response = requests.get(url, timeout=timeout, headers=_headers())
            response.raise_for_status()
            data = response.json()
            return _parse_release(data)
        else:
            # For beta/dev channels, fetch all releases and find first matching pre-release
            url = f"{GITHUB_API_BASE}/repos/{repo}/releases"
            response = requests.get(url, timeout=timeout, headers=_headers())
            response.raise_for_status()
            releases = response.json()

            for release in releases:
                if channel == "beta" and release.get("prerelease"):
                    return _parse_release(release)
                elif channel == "dev":
                    # Dev channel gets the absolute latest, including drafts
                    return _parse_release(release)

            # Fallback to latest stable if no pre-release found
            if releases:
                return _parse_release(releases[0])
            return None

    except requests.exceptions.RequestException as e:
        logger.warning(f"GitHub Releases API failed: {e}")
        raise GitHubAPIError(f"Failed to fetch releases from GitHub: {e}") from e
    except (KeyError, ValueError) as e:
        logger.warning(f"Failed to parse GitHub release data: {e}")
        raise GitHubAPIError(f"Invalid release data from GitHub: {e}") from e


def get_latest_version_raw(
    url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[str]:
    """
    Fallback: fetch version string from a raw text file on GitHub.

    This is the legacy method used by the original update.py.

    Args:
        url: Direct URL to the raw version file.
        timeout: Request timeout in seconds.

    Returns:
        Version string on success, None on failure.
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.text.strip()
    except requests.exceptions.RequestException as e:
        logger.warning(f"Raw version check failed: {e}")
        return None


def _parse_release(data: Dict[str, Any]) -> ReleaseInfo:
    """Parse a GitHub release JSON object into a ReleaseInfo."""
    tag = data.get("tag_name", "")
    version = tag.lstrip("vV")

    # Find the best download asset (prefer .zip source)
    assets = data.get("assets", [])
    download_url = ""
    sha256 = ""

    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".zip"):
            download_url = asset.get("browser_download_url", "")
            break

    # If no .zip asset, use the source tarball/zipball
    if not download_url:
        download_url = data.get("zipball_url", "")

    # Try to extract SHA256 from release body (convention: "SHA256: <hash>")
    body = data.get("body", "") or ""
    for line in body.splitlines():
        line_stripped = line.strip().lower()
        if line_stripped.startswith("sha256:"):
            sha256 = line_stripped.split(":", 1)[1].strip()
            break

    return ReleaseInfo(
        version=version or tag,
        tag_name=tag,
        changelog=body,
        download_url=download_url,
        sha256=sha256,
        published_at=data.get("published_at", ""),
        prerelease=data.get("prerelease", False),
        assets=[
            {
                "name": a.get("name"),
                "url": a.get("browser_download_url"),
                "size": a.get("size"),
            }
            for a in assets
        ],
    )


def _headers() -> Dict[str, str]:
    """Standard headers for GitHub API requests."""
    return {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
