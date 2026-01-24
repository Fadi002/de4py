from dataclasses import dataclass, field, asdict
import json
import os
import logging
from typing import Optional, Dict, Any

# =============================================================================
# Configuration Definition
# =============================================================================

@dataclass
class Settings:
    """
    Application configuration.
    Changes here are reflected in `config.json`.
    """
    version: str = "V2.2.4"
    changelog_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/changelog.json"
    version_url: str = "https://raw.githubusercontent.com/Fadi002/de4py/main/INFO/version"
    rpc: bool = True
    stealth_title: bool = True
    load_plugins: bool = True
    build_num: str = "2.2.4.260124645-stable-de4py"
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
            
            # Update fields, mapping keys like '__VERSION__' to 'version' if found (legacy support)
            # or direct mapping for new keys.
            for key, value in data.items():
                # Handle legacy keys (e.g. __RPC__ -> rpc)
                normalized_key = key.lower().strip('_')
                if hasattr(self, normalized_key):
                     setattr(self, normalized_key, value)
                elif hasattr(self, key):
                     setattr(self, key, value)
                     
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    def save(self):
        """Save current settings to JSON file."""
        try:
            # We want to save both the nice names AND maintain compat if other tools read it, 
            # but for this "final" pass, we will save clean names. 
            # If compatibility with external tools is CRITICAL, we can map back to __UPPER__.
            # Assuming cleanup: we save clean names.
            
            data = asdict(self)
            # Remove private fields
            if '_path' in data: del data['_path']
            
            with open(self._path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to save config: {e}")

# =============================================================================
# Singleton Instance
# =============================================================================

settings = Settings()

# =============================================================================
# Legacy Compatibility Layer (Deprecated)
# =============================================================================
# Expose old globals pointing to the new settings object
__VERSION__ = settings.version
__CHANGELOG_URL__ = settings.changelog_url
__VERSION_URL__ = settings.version_url
__RPC__ = settings.rpc
__STEALTH_TITLE__ = settings.stealth_title
__LOAD_PLUGINS__ = settings.load_plugins
__BUILD_NUM__ = settings.build_num
__API_BASE_URL__ = settings.api_base_url
__API_TIMEOUT__ = settings.api_timeout
__POLL_INTERVAL__ = settings.poll_interval

def get_config() -> dict:
    return asdict(settings)

def update_json(key, value):
    # Map legacy key to attribute
    attr = key.lower().strip('_')
    if hasattr(settings, attr):
        setattr(settings, attr, value)
        settings.save()
        # Update legacy global
        globals()[key] = value