import os, importlib.util, inspect, logging, traceback, requests

html_result = ''
def build_html(plugin):
    global html_result
    html_result += f'''
<div class="plugin-frame">
    <div class="plugin-info"><a href="{plugin['link']}" target="_blank">{plugin['name']}</a></div>
    <div class="created-by">Made by: {plugin['creator']}</div>
    
</div>
'''
    return html_result

def send_error(exctype, value, tb):
     try:
         error_info = {
              "type": str(exctype),
              "message": str(value),
              "traceback": traceback.format_exception(exctype, value, tb)
              }
         api_url = "https://de4py-api.onrender.com/error"
         response = requests.post(api_url, json=error_info, timeout=60) 
         if response.status_code == 200:
              print("Error has been reported")
         else:
              print("Failed to send error Status code:", response.status_code)
     except:
          pass

class DeobfuscatorPlugin:
    def __init__(self, plugin_name, creator, link, regex, deobfuscator_function):
        self.plugin_name = plugin_name
        self.creator = creator
        self.link = link
        self.regex = regex
        self.deobfuscator_function = deobfuscator_function
class ThemePlugin:
    def __init__(self, plugin_name, creator, link, css):
        self.plugin_name = plugin_name
        self.creator = creator
        self.link = link
        self.css = css

def load_plugins(senderr):
    plugins_folder = 'plugins'
    plugins = []
    for plugin_file in [f for f in os.listdir(plugins_folder) if f.endswith(".py") and not f.startswith("__") and f != "plugins.py"]:
        try:
            plugin_path = os.path.join(plugins_folder, plugin_file)
            plugin_class = load_plugin(plugin_path, senderr)
            if plugin_class:
                plugins.append({"type": "deobfuscator" if issubclass(plugin_class, DeobfuscatorPlugin) else "theme", "instance": plugin_class()})
        except Exception as e:
            logging.error(f"Failed to load plugin {plugin_file} ERROR:\n{e}")
    return plugins

def load_plugin(plugin_path, senderr):
    try:
        spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
        plugin_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(plugin_module)
        return get_class(plugin_module)
    except Exception as e:
        logging.error(f"Error loading plugin from {plugin_path}: {e}")
        if senderr:send_error(type(e), e, e.__traceback__)
        return None

def get_class(module, exclude_module='plugins.plugins'):
    for obj in module.__dict__.values():
        if inspect.isclass(obj) and not (exclude_module and obj.__module__.startswith(exclude_module)):
            return obj
    return None