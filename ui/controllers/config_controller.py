from config import config


def get_config():
    return config.get_config()


def update_config(key, value):
    return config.update_json(key, value)


def get_rpc():
    return config.__RPC__


def get_stealth_title():
    return config.__STEALTH_TITLE__


def get_load_plugins():
    return config.__LOAD_PLUGINS__


def get_version():
    return config.__VERSION__


def get_build_num():
    return config.__BUILD_NUM__


def get_changelog_url():
    return config.__CHANGELOG_URL__
