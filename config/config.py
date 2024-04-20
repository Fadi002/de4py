import json
JSON_FILE_NAME = 'config/config.json'
def get_config():
    with open(JSON_FILE_NAME, 'r') as f:
        return json.load(f)

def update_json(key, value):
    global __VERSION__, __CHANGELOG_URL__, __VERSION_URL__, __RPC__, __STEALTH_TITLE__, __LOAD_PLUGINS__, __BUILD_NUM__
    config_data = get_config()
    config_data[key] = value
    with open(JSON_FILE_NAME, 'w') as file:
        json.dump(config_data, file, indent=4)
    __RPC__ = get_config()["__RPC__"]
    __STEALTH_TITLE__ = get_config()["__STEALTH_TITLE__"]
    __LOAD_PLUGINS__ = get_config()["__LOAD_PLUGINS__"]
    


__VERSION__ = get_config()["__VERSION__"]
__CHANGELOG_URL__ = get_config()["__CHANGELOG_URL__"]
__VERSION_URL__ = get_config()["__VERSION_URL__"]
__RPC__ = get_config()["__RPC__"]
__STEALTH_TITLE__ = get_config()["__STEALTH_TITLE__"]
__LOAD_PLUGINS__ = get_config()["__LOAD_PLUGINS__"]
__BUILD_NUM__ = get_config()["__BUILD_NUM__"]