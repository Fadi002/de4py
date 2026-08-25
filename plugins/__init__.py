"""
De4py Plugin System - Package Initialization
Defines the standard contract for plugins.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any, Type


class BasePlugin:
    """Base class for all plugins."""
    def __init__(self):
        self.name= "Unknown"
        self.creator= "Unknown"
        self.link= ""
        self.version= "1.0.0"


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
        self.qss= ""
        self.transparent_qss: Optional[str] = None
        self.is_dark: bool = True
        self.colors: Dict[str, str] = {}  # e.g. {"primary": "#HEX", "background": "#HEX"}
        self.disable_glow: bool = False # If True, disables native sidebar glow effects


# Standard entry point name for plugins
REGISTER_FUNCTION = "register"

from .plugins import load_plugins
