"""
De4py Configuration Module
Loads and manages application configuration from config.json
"""
import json

JSON_FILE_NAME = 'config/config.json'


def get_config():
    """Load and return the configuration dictionary from JSON file."""
    with open(JSON_FILE_NAME, 'r') as f:
        return json.load(f)


def update_json(key, value):
    """Update a configuration value and refresh module-level constants."""
    global __VERSION__, __CHANGELOG_URL__, __VERSION_URL__, __RPC__, __STEALTH_TITLE__, __LOAD_PLUGINS__, __BUILD_NUM__
    global __API_BASE_URL__, __API_TIMEOUT__, __POLL_INTERVAL__
    
    config_data = get_config()
    config_data[key] = value
    with open(JSON_FILE_NAME, 'w') as file:
        json.dump(config_data, file, indent=4)
    
    # Refresh runtime constants
    _refresh_constants()


def _refresh_constants():
    """Refresh all module-level constants from config."""
    global __VERSION__, __CHANGELOG_URL__, __VERSION_URL__, __RPC__, __STEALTH_TITLE__, __LOAD_PLUGINS__, __BUILD_NUM__
    global __API_BASE_URL__, __API_TIMEOUT__, __POLL_INTERVAL__
    
    config = get_config()
    __VERSION__ = config["__VERSION__"]
    __CHANGELOG_URL__ = config["__CHANGELOG_URL__"]
    __VERSION_URL__ = config["__VERSION_URL__"]
    __RPC__ = config["__RPC__"]
    __STEALTH_TITLE__ = config["__STEALTH_TITLE__"]
    __LOAD_PLUGINS__ = config["__LOAD_PLUGINS__"]
    __BUILD_NUM__ = config["__BUILD_NUM__"]
    __API_BASE_URL__ = config.get("__API_BASE_URL__", "https://de4py-api.vercel.app")
    __API_TIMEOUT__ = config.get("__API_TIMEOUT__", 30)
    __POLL_INTERVAL__ = config.get("__POLL_INTERVAL__", 2.0)


# Initialize module-level constants
__VERSION__ = get_config()["__VERSION__"]
__CHANGELOG_URL__ = get_config()["__CHANGELOG_URL__"]
__VERSION_URL__ = get_config()["__VERSION_URL__"]
__RPC__ = get_config()["__RPC__"]
__STEALTH_TITLE__ = get_config()["__STEALTH_TITLE__"]
__LOAD_PLUGINS__ = get_config()["__LOAD_PLUGINS__"]
__BUILD_NUM__ = get_config()["__BUILD_NUM__"]

# API Configuration
__API_BASE_URL__ = get_config().get("__API_BASE_URL__", "https://de4py-api.vercel.app")
__API_TIMEOUT__ = get_config().get("__API_TIMEOUT__", 30)
__POLL_INTERVAL__ = get_config().get("__POLL_INTERVAL__", 2.0)