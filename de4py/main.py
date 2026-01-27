import sys
import os

REQUIRED_LIBS = {
    "PySide6": "PySide6",
    "requests": "requests",
    "psutil": "psutil",
    "colorama": "colorama",
    "Crypto": "pycryptodome",
    "pypresence": "pypresence",
    "xdis": "xdis",
    "sentry_sdk": "sentry-sdk",
    "pefile": "pefile"
}

missing = []
for module_name, pip_name in REQUIRED_LIBS.items():
    try:
        __import__(module_name)
    except ImportError:
        missing.append(pip_name)

if missing:
    print("\n" + "!" * 60)
    print(f"[!] CRITICAL ERROR: Missing {len(missing)} required libraries:")
    for lib in missing:
        print(f"    - {lib}")
    print("\n[!] Please install the missing requirements by running:")
    print("    pip install -r requirements.txt")
    print("!" * 60 + "\n")
    sys.exit(1)

import random
import string
import ctypes
import logging
import argparse
import colorama
import msvcrt
import signal

# Handle Ctrl+C gracefully
signal.signal(signal.SIGINT, signal.SIG_DFL)

sys.dont_write_bytecode = True

os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile, QTextStream, Qt
from PySide6.QtGui import QIcon

from de4py.ui.main_window import MainWindow
from de4py.config.config import settings
from de4py.utils import rpc, tui, update, setup_logging, sentry

colorama.init(autoreset=True)
sentry.init()

DEFAULT_QSS = ""

def load_stylesheet(app: QApplication):
    """Loads the dark theme QSS stylesheet."""
    global DEFAULT_QSS
    theme_path = os.path.join(os.path.dirname(__file__), "ui", "themes", "dark_theme.qss")
    if os.path.exists(theme_path):
        file = QFile(theme_path)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            qss = stream.readAll()
            DEFAULT_QSS = qss
            app.setStyleSheet(qss)
            file.close()
            return qss
    return ""

def set_stealth_title():
    """Sets a random console title for stealth if enabled."""
    if settings.stealth_title:
        random_title = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(10, 40)))
        try:
            ctypes.windll.kernel32.SetConsoleTitleW(random_title)
            return random_title
        except Exception:
            pass
    return None

def main():
    parser = argparse.ArgumentParser(description="de4py - Python Deobfuscator & Analyzer")
    parser.add_argument("--cli", action="store_true", help="Start in CLI mode")
    parser.add_argument("--test", action="store_true", help="Run internal tests")
    args = parser.parse_args()

    # Setup environment
    setup_logging()
    
    # Show Banner
    tui.clear_console()
    print(tui.__BANNER__)
    logging.info("Starting de4py")

    # Check for updates
    try:
        if update.check_update():
                logging.info("You are using the latest version")
        else:
            logging.warning("There's a new version. Are you sure you want to use this version?")
            tui.fade_type('Answer [y/n]\n')
            if not input(">>> ").lower() == 'y':
                 logging.warning("Download it from here : https://github.com/Fadi002/de4py")
                 logging.warning("Press any key to exit...")
                 while True:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        logging.warning("Exiting...")
                        rpc.KILL_THREAD = True
                        ctypes.windll.kernel32.ExitProcess(0)
    except:
        logging.error("Failed to check for updates")
    # Handle Modes
    if args.test:
        with sentry.transaction("Test Session", "app.test"):
            logging.info("Starting in Test mode...")
            from de4py.utils.test import main as run_tests
            run_tests([])
            return

    if args.cli:
        with sentry.transaction("CLI Session", "app.cli"):
            logging.info("Starting in CLI mode...")
            from de4py.tui import cli
            cli.start()
            return

    # Default: GUI Mode
    with sentry.transaction("GUI Session", "app.gui"):
        sentry.breadcrumb("GUI Application starting", category="lifecycle")
        logging.info("Starting in GUI mode...")
        app = QApplication(sys.argv)
        app.setApplicationName("de4py")
        
        sentry.set_extra_context("app_config", {
            "mode": "GUI",
            "rpc_enabled": settings.rpc,
            "stealth_title": settings.stealth_title
        })

        # Updated icon path
        icon_path = os.path.join(os.path.dirname(__file__), "ui", "resources", "de4py.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        load_stylesheet(app)
        stealth_title = set_stealth_title()
        
        if settings.rpc:
            try:
                rpc.start_RPC()
            except Exception:
                pass
        
        window = MainWindow(title=stealth_title)
        
        if settings.active_theme:
            try:
                from plugins import load_plugins
                loaded_plugins = load_plugins()
                for plugin_data in loaded_plugins:
                    plugin_instance = plugin_data.get("instance")
                    if plugin_instance and plugin_instance.name == settings.active_theme:
                        if hasattr(plugin_instance, 'qss'):
                            app.setStyleSheet(plugin_instance.qss)
                        break
            except Exception as e:
                logging.error(f"Failed to load persistent theme: {e}")
                settings.active_theme = None
                settings.save()

        window.show()
        
        exit_code = app.exec()
        
        # Cleanup
        rpc.KILL_THREAD = True
        logging.info("De4py shutting down")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
