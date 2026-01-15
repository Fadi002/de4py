from pathlib import Path
import importlib.util
import logging
from typing import List, Dict, Any

try:
    from . import DeobfuscatorPlugin, ThemePlugin, REGISTER_FUNCTION
except ImportError:
    # Fallback for direct execution or if package structure isn't recognized yet
    from plugins import DeobfuscatorPlugin, ThemePlugin, REGISTER_FUNCTION

logger = logging.getLogger(__name__)

def load_plugins() -> List[Dict[str, Any]]:
    """
    Loads all plugins from the plugins directory.
    Isolates failures per plugin to ensure application startup is not affected.
    """
    plugins_dir = Path(__file__).parent
    loaded_plugins = []

    # Iterate through all .py files in the plugins folder
    for plugin_file in plugins_dir.glob("*.py"):
        if plugin_file.name in ("__init__.py", "plugins.py"):
            continue

        try:
            plugin_instance = _load_single_plugin(plugin_file)
            if plugin_instance:
                plugin_type = "deobfuscator" if isinstance(plugin_instance, DeobfuscatorPlugin) else "theme"
                loaded_plugins.append({
                    "type": plugin_type,
                    "instance": plugin_instance
                })
                logger.debug(f"Successfully loaded plugin: {getattr(plugin_instance, 'name', plugin_file.stem)}")
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_file.name}: {e}")

    return loaded_plugins

def _load_single_plugin(file_path: Path):
    """Loads a single plugin from a file path using the register contract."""
    try:
        spec = importlib.util.spec_from_file_location(file_path.stem, str(file_path))
        if spec is None or spec.loader is None:
            return None
            
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check for the register() function (the new contract)
        if hasattr(module, REGISTER_FUNCTION):
            register_fn = getattr(module, REGISTER_FUNCTION)
            return register_fn()
            
        # Fallback to old class-based detection for backward compatibility
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, (DeobfuscatorPlugin, ThemePlugin)) and attr not in (DeobfuscatorPlugin, ThemePlugin):
                return attr()
                
        return None
    except Exception as e:
        logger.error(f"Error executing plugin {file_path.name}: {e}")
        return None