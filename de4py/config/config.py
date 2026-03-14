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

PROJECT_SIGNATURE = "de4py-core-signature-7f3a91"

@dataclass
class Settings:
    version: str = "V2.2.5"
    changelog_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/changelog.json"
    version_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/version"
    rpc: bool = True
    stealth_title: bool = True
    load_plugins: bool = True
    build_num: str = "2.2.5.260314083-stable-de4py"
    api_base_url: str = "https://de4py-api.vercel.app"
    api_timeout: int = 700
    poll_interval: float = 2.0
    active_theme: Optional[str] = None
    language: str = "en"
    transparent_ui: bool = False    
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
                     
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    def save(self):
        try:
            data = asdict(self)
            data.pop('_path', None)

            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

settings = Settings()


def get_config() -> dict:
    return asdict(settings)


def update_json(key: str, value) -> None:
    attr = key.lower().strip("_")
    if hasattr(settings, attr):
        setattr(settings, attr, value)
        settings.save()
