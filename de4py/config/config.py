# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from dataclasses import dataclass, field, asdict
import json
import os
import logging
from typing import Optional, Dict, Any

VALID_UPDATE_CHANNELS = {"stable", "dev"}
UPDATE_CHANNEL_BRANCHES = {
    "stable": "main",
    "dev": "dev",
}
DEFAULT_GITHUB_REPO = "Fadi002/de4py"

@dataclass
class Settings:
    version: str = "V3.1.1"
    changelog_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/changelog.json"
    version_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/version"
    rpc: bool = True
    stealth_title: bool = True
    load_plugins: bool = True
    build_num: str = "3.1.1.260321656-stable-de4py"
    api_base_url: str = "https://de4py-api.vercel.app"
    api_timeout: int = 700
    poll_interval: float = 2.0
    active_theme: Optional[str] = None
    language: str = "en"
    transparent_ui: bool = False
    auto_update: bool = True
    update_channel: str = "stable"
    pending_update_channel: Optional[str] = None
    installed_update_channel: Optional[str] = None
    last_update_check: Optional[str] = None
    github_repo: str = DEFAULT_GITHUB_REPO
    telemetry: bool = True
    _path: str = field(default=os.path.join(os.path.dirname(__file__), 'config.json'), repr=False, init=False)

    def __post_init__(self):
        self._load()

    def _load(self):
        """Load settings from JSON file if it exists."""
        if not os.path.exists(self._path):
            return

        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for key, value in data.items():
                normalized_key = key.lower().strip('_')
                if hasattr(self, normalized_key):
                     setattr(self, normalized_key, value)
                elif hasattr(self, key):
                     setattr(self, key, value)

            self._normalize()
                     
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    def save(self):
        try:
            self._normalize()
            data = asdict(self)
            data.pop('_path', None)

            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def _normalize(self):
        channel = str(getattr(self, "update_channel", "stable")).strip().lower()
        if channel not in VALID_UPDATE_CHANNELS:
            channel = "dev" if channel in {"beta", "nightly", "preview"} else "stable"
        self.update_channel = channel
        pending = getattr(self, "pending_update_channel", None)
        if pending is not None:
            pending = str(pending).strip().lower()
            if pending not in VALID_UPDATE_CHANNELS or pending == self.update_channel:
                pending = None
        self.pending_update_channel = pending

        installed = getattr(self, "installed_update_channel", None)
        if installed is None:
            installed = self._infer_installed_channel()
        else:
            installed = str(installed).strip().lower()
            if installed not in VALID_UPDATE_CHANNELS:
                installed = self._infer_installed_channel()
        self.installed_update_channel = installed
        self._sync_update_sources()

    def _infer_installed_channel(self) -> str:
        build = str(getattr(self, "build_num", "")).lower()
        if "-dev-" in build or build.endswith("-dev"):
            return "dev"
        return "stable"

    def _sync_update_sources(self) -> None:
        branch = self.get_update_branch(self.update_channel)
        repo = getattr(self, "github_repo", DEFAULT_GITHUB_REPO) or DEFAULT_GITHUB_REPO
        self.version_url = f"https://raw.githubusercontent.com/{repo}/{branch}/INFO/version"
        self.changelog_url = f"https://raw.githubusercontent.com/{repo}/{branch}/INFO/changelog.json"

    def get_update_branch(self, channel: Optional[str] = None) -> str:
        channel = channel or self.update_channel
        return UPDATE_CHANNEL_BRANCHES.get(channel, "main")

    def get_update_download_url(self, channel: Optional[str] = None) -> str:
        branch = self.get_update_branch(channel)
        repo = getattr(self, "github_repo", DEFAULT_GITHUB_REPO) or DEFAULT_GITHUB_REPO
        return f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"

    def request_update_channel_switch(self, channel: str) -> bool:
        channel = str(channel).strip().lower()
        if channel not in VALID_UPDATE_CHANNELS:
            return False
        if channel == self.update_channel and self.pending_update_channel is None:
            return False
        self.pending_update_channel = None if channel == self.update_channel else channel
        self.save()
        return True

    def apply_pending_update_channel(self) -> bool:
        pending = self.pending_update_channel
        if not pending:
            self._sync_update_sources()
            return False
        self.update_channel = pending
        self.pending_update_channel = None
        self.save()
        return True

settings = Settings()


def get_config() -> dict:
    return asdict(settings)


def update_json(key: str, value) -> None:
    attr = key.lower().strip("_")
    if hasattr(settings, attr):
        setattr(settings, attr, value)
        settings.save()
