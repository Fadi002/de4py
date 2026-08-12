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
from typing import Optional

from PySide6.QtCore import QObject, Signal as QSignal




def _read_local_version() -> str:
    info_path = os.path.join(os.path.dirname(__file__), '..', '..', 'INFO', 'version')
    try:
        with open(info_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return "V0.0.0"


class SettingsEmitter(QObject):
    """Emits signals when settings values change."""
    rpc_changed = QSignal(bool)
    stealth_title_changed = QSignal(bool)
    load_plugins_changed = QSignal(bool)
    transparent_ui_changed = QSignal(bool)
    telemetry_changed = QSignal(bool)
    language_changed = QSignal(str)
    poll_interval_changed = QSignal(float)
    active_theme_changed = QSignal(object)
    auto_update_check_changed = QSignal(bool)
    auto_update_install_changed = QSignal(bool)


_emitter = SettingsEmitter()


def get_settings_emitter() -> SettingsEmitter:
    return _emitter


@dataclass
class Settings:
    version: str = field(default_factory=_read_local_version)
    changelog_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/changelog.json"
    version_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/version"
    releases_base_url: str = "https://github.com/Fadi002/de4py/releases/download"
    rpc: bool = True
    stealth_title: bool = True
    load_plugins: bool = True
    build_num: str = "3.3.2.260812416-stable-de4py"
    api_base_url: str = "https://de4py-api.vercel.app"
    api_timeout: int = 700
    poll_interval: float = 2.0
    active_theme: Optional[str] = None
    language: str = "en"
    transparent_ui: bool = False
    telemetry: bool = False
    telemetry_api_key: str = "os_live_2a8c6be308a4e15defb587d0eb76b78b90ebc0e52ab6465b2060f8b51a9b0a7c"
    telemetry_ping_url: str = "https://chimpanzee.pythonanywhere.com/api/v1/ping"
    auto_update_check: bool = True
    auto_update_install: bool = False
    ai_enabled: bool = False
    ai_provider: str = "ollama"
    ai_annotate: bool = False
    ai_explain: bool = False
    ai_simplify: bool = False
    #: Per-provider privacy consent (cloud providers only).
    ai_consent: dict = field(default_factory=dict)
    ai_ollama_model: str = ""
    ai_ollama_base_url: str = ""
    ai_openai_model: str = ""
    ai_openai_base_url: str = ""
    ai_openrouter_model: str = ""
    ai_openrouter_base_url: str = ""
    ai_opencode_model: str = ""
    ai_opencode_base_url: str = ""
    ai_gemini_model: str = ""
    ai_gemini_base_url: str = ""
    ai_custom_model: str = ""
    ai_custom_base_url: str = ""
    _path: str = field(default=os.path.join(os.path.dirname(__file__), 'config.json'), repr=False, init=False)

    def __post_init__(self):
        self._load()

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            _saved_version = self.version
            for key, value in data.items():
                normalized_key = key.lower().strip('_')
                if hasattr(self, normalized_key):
                     setattr(self, normalized_key, value)
                elif hasattr(self, key):
                     setattr(self, key, value)
            self.version = _saved_version
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    def save(self):
        try:
            data = asdict(self)
            data.pop('_path', None)
            tmp_path = f"{self._path}.tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, self._path)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

    def set_and_emit(self, key: str, value):
        old = getattr(self, key, None)
        if old == value:
            return
        setattr(self, key, value)
        self.save()
        signal_name = f"{key}_changed"
        if hasattr(_emitter, signal_name):
            sig = getattr(_emitter, signal_name)
            sig.emit(value)


settings = Settings()
