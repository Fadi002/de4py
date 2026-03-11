<a href="#home"><img src="https://github.com/Fadi002/de4py/blob/main/Pictures/de4py.jpg?raw=true"></img></a>
# de4py

> ⚠️ **de4py is FREE & OPEN SOURCE (CC BY-NC 4.0).**  
> **Any paid versions sold elsewhere or commercial use are NOT permitted.**
> **If you paid for de4py, you were misled.**

De4py is an advanced Python deobfuscator with a beautiful UI (PySide6) and a robust set of features for malware analysts and reverse engineers. It supports both automatic deobfuscation of common packers and manual analysis tools.

Maintained by [Fadi002](https://github.com/Fadi002) and [AdvDebug](https://github.com/AdvDebug).

## 🚀 Features

| Feature | Function |
| :--- | :--- |
| **Deobfuscation** | Support for popular obfuscators: **Jawbreaker, BlankOBF, PlusOBF, Wodx, Hyperion, pyobfuscate**. |
| **File Analyzer** | Detection of packers (PyInstaller), hash calculation, suspicious string lookup, and metadata extraction. |
| **PyCode Execution** | Execute Python code inside the target process (useful for bypassing licensing checks). |
| **Pyshell GUI** | Custom GUI to easily inject and execute Python code in valid processes. |
| **Behavior Monitor** | Monitor process handles, memory access, sockets, and dumped content (including decrypted OpenSSL traffic). |
| **Modern UI** | Built with **PySide6** and a custom dark theme for a premium look and feel. CLI mode also supported. |
| **API System** | Use de4py as a library in your own tools. |

## 📦 Installation & Usage

### Prerequisites
- Python 3.8+
- Windows (recommended for full feature support)

### Installation
You can install de4py as a package:

```bash
git clone https://github.com/Fadi002/de4py.git
cd de4py
pip install .
```

### Running

**GUI Mode:**
```bash
python -m de4py
# OR
python main.py
```

**CLI Mode:**
```bash
python -m de4py --cli
```

## 🛠 Project Structure

The project has been refactored for clarity:

```
de4py/
├── de4py/               # Main Package
│   ├── core/            # Core logic (EngineManager, Interfaces)
│   ├── engines/         # Deobfuscators and Analyzers
│   ├── ui/              # PySide6 User Interface
│   ├── config/          # Configuration management
│   └── utils/           # Utilities (RPC, TUI, etc.)
├── plugins/             # External Plugins folder (Root)
├── main.py              # Entry point
└── pyproject.toml       # Project configuration
```

## 🤝 Contributions

All contributions are welcome!

## 🔗 Community

- **Matrix:** [Join our Matrix room](https://matrix.to/#/#de4py_commiunty:matrix.org) 🔒 (recommended)
- **Signal:** [Join our Signal room](https://signal.group/#CjQKIGl8b9tJIMoMpwnrzUIDSqJY5UMJOzpixJklsEgYSrjJEhCw2rBAUFVOWkwIZ-gM3mqS)
- **Discord:** [Join here](https://discord.gg/cYxxUHsbRm) 💬

## 🌐 Help Translate de4py

We use [Crowdin](https://crowdin.com/project/de4py) for translations.  

- Select a language you want to translate.
- Use the Crowdin web editor.
- Submit translations for review.

## ⚠️ Disclaimer

This tool is for **educational purposes only**. Never deobfuscate software without permission. The developers are not responsible for misuse.

## 📄 License

Licensed under **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

## 📝 Attribution Notice

This project was created by **Fadi002**.

If you fork or redistribute this project, you must retain the original copyright notices
and provide appropriate attribution according to the **CC BY-NC 4.0** license.
Commercial use is not permitted without explicit permission from the author.
