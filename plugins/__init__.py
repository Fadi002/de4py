"""
De4py Plugin System - Package Initialization
Defines the standard contract for plugins.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Type


class BasePlugin:
    """Base class for all plugins."""
    def __init__(self):
        self.name: str = "Unknown"
        self.creator: str = "Unknown"
        self.link: str = ""
        self.version: str = "1.0.0"


class DeobfuscatorPlugin(BasePlugin):
    """Contract for deobfuscator plugins."""
    def __init__(self):
        super().__init__()
        self.type = "deobfuscator"
        self.regex = None  # Compiled regex pattern

    def deobfuscate(self, file_path: Path) -> str:
        """Entry point for deobfuscation logic."""
        raise NotImplementedError("Plugins must implement deobfuscate()")


class ThemePlugin(BasePlugin):
    """Contract for theme plugins."""
    def __init__(self):
        super().__init__()
        self.type = "theme"
        self.qss: str = ""


# Standard entry point name for plugins
REGISTER_FUNCTION = "register"

from .plugins import load_plugins
