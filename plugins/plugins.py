import os, importlib.util, inspect, logging, requests

# Plugin System Core


class DeobfuscatorPlugin:
    def __init__(self, plugin_name, creator, link, regex, deobfuscator_function):
        self.plugin_name = plugin_name
        self.creator = creator
        self.link = link
        self.regex = regex
        self.deobfuscator_function = deobfuscator_function
class ThemePlugin:
    """
    Plugin for customizing the UI appearance using QSS (Qt Style Sheet).
    """
    def __init__(self, plugin_name, creator, link, qss):
        self.plugin_name = plugin_name
        self.creator = creator
        self.link = link
        self.qss = qss

def load_plugins():
    plugins_folder = 'plugins'
    plugins = []
    for plugin_file in [f for f in os.listdir(plugins_folder) if f.endswith(".py") and not f.startswith("__") and f != "plugins.py"]:
        try:
            plugin_path = os.path.join(plugins_folder, plugin_file)
            plugin_class = load_plugin(plugin_path)
            if plugin_class:
                plugins.append({"type": "deobfuscator" if issubclass(plugin_class, DeobfuscatorPlugin) else "theme", "instance": plugin_class()})
        except Exception as e:
            logging.error(f"Failed to load plugin {plugin_file} ERROR:\n{e}")
    return plugins

def load_plugin(plugin_path):
    try:
        spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
        plugin_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin_module)
        return get_class(plugin_module)
    except Exception as e:
        logging.error(f"Error loading plugin from {plugin_path}: {e}")
        return None

def get_class(module, exclude_module='plugins.plugins'):
    for obj in module.__dict__.values():
        if inspect.isclass(obj) and not (exclude_module and obj.__module__.startswith(exclude_module)):
            return obj
    return None