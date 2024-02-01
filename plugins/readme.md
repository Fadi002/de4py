# [de4py plugins API Documentation](https://de4py.000.pe/plugins.html)
<details>
<summary>Deobfuscator Plugin</summary>

## Deobfuscator Plugin

### Introduction

The `DeobfuscatorPlugin` class in the `de4py` API allows you to create deobfuscator plugins to simplify code by removing obfuscation. 

#### Example:

```python
from plugins.plugins import DeobfuscatorPlugin
import re

class DeobfuscatorExample(DeobfuscatorPlugin):
    def __init__(self):
        super().__init__(
            plugin_name="deobfuscator",
            creator="creator",
            link="https://github.com/Fadi002/de4py-plugins-repo/blob/main/example1.py",
            regex=re.compile(r'regex'),
            deobfuscator_function=self.deobfuscator_function
        )

    def deobfuscator_function(self, file_path) -> str:
        # Implement your deobfuscation logic here
        # ...
```

#### Parameters:

- `plugin_name`: A unique name for your deobfuscator plugin. (ex. BlankOBF_deobfuscator)
- `creator`: The name of the plugin creator. (ex. Ryan)
- `link`: A link to the plugin's source code of the plugin.
- `regex`: A regular expression to identify obfuscated code patterns.
- `deobfuscator_function`: The function that performs the deobfuscation. It takes a `file_path` as an argument and returns the deobfuscated code as a string.

### Usage

1. Create a class that inherits from `DeobfuscatorPlugin`.
2. Implement the `__init__` method, setting the required parameters.
3. Implement the `deobfuscator_function` method to perform the actual deobfuscation.
</details>



<details>
<summary>Theme Plugin</summary>

## Theme Plugin

### Introduction

The `ThemePlugin` class in the `de4py` API allows you to create theme plugins to customize the appearance of the de4py interface. Themes are defined using CSS code.

#### Example:

```python
from plugins.plugins import ThemePlugin

class LightThemeExample(ThemePlugin):
    def __init__(self):
        super().__init__(
            plugin_name="Light theme example plugin",
            creator="Fadi002",
            link="https://github.com/Fadi002/de4py-plugins-repo/blob/main/example2.py",
            css="""
            body {
                background-color: lightpink;
            }
            h1, h2, h3, h4, h5, h6, p, span, a, ul, li, #clock, label {
                color: darkred;
            }
            .frame {
                border: 2px solid #4ba3e2;
                background-color: #f8f9fa;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 0 10px #4ba3e2;
            }
            btn {
                color: darkred;
            }
            #changeLog, #outputanalyzer, #outputwinapihooks, #outputDEOBF, .scroll-box, textarea {
                background-color: #f8f9fa;
                color: darkred;
            }
            .custom-input {
                background-color: #9e9e9e;
                color: #333;
            }
            
            .custom-input:hover {
                background-color: #e1ecf4;
            }
            
            .custom-input:focus {
                background-color: #d0e5f5;
            }
            """
        )
```

#### Parameters:

- `plugin_name`: A unique name for your theme plugin. (ex. Neon Dark theme)
- `creator`: The name of the plugin creator. (ex. Ryan)
- `link`: A link to the plugin's source code.
- `css`: The CSS code defining the theme.

### Usage

1. Create a class that inherits from `ThemePlugin`.
2. Implement the `__init__` method, setting the required parameters.
3. Define the theme using CSS code in the `css` parameter.

### Note

Make sure to read the CSS [source code](https://github.com/Fadi002/de4py/blob/main/GUI/css/styles.css) of the main GUI to understand how to modify the appearance and to create your own themes accordingly.
</details>


<details>
<summary>Help?</summary>

**Looking for Assistance?**

If you need support or want to share your plugin with us, don't hesitate to reach out through our Discord server.

Join us on [Discord](https://discord.gg/GCpHp2xs)

</details>
