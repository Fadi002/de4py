import sys
import os
import random
import string
import ctypes
import logging
import argparse
import colorama
import msvcrt

# Prevent creation of __pycache__
sys.dont_write_bytecode = True

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QFile, QTextStream
from PySide6.QtGui import QIcon

from ui.main_window import MainWindow
from ui.controllers import config_controller
from util import rpc, tui, update, setup_logging

# Initialize colorama for terminal support
colorama.init(autoreset=True)


def load_stylesheet(app: QApplication):
    """Loads the dark theme QSS stylesheet."""
    theme_path = os.path.join(os.path.dirname(__file__), "ui", "themes", "dark_theme.qss")
    if os.path.exists(theme_path):
        file = QFile(theme_path)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            app.setStyleSheet(stream.readAll())
            file.close()

def set_stealth_title():
    """Sets a random console title for stealth if enabled."""
    if config_controller.get_stealth_title():
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
    print(tui.__BANNER__)
    logging.info("Starting de4py")

    # Check for updates
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

    # Handle Modes
    if args.test:
        logging.info("Starting in Test mode...")
        from util.test import main as run_tests
        run_tests([])
        return

    if args.cli:
        logging.info("Starting in CLI mode...")
        from TUI import cli
        cli.start()
        return

    # Default: GUI Mode
    logging.info("Starting in GUI mode...")
    app = QApplication(sys.argv)
    app.setApplicationName("de4py")
    
    # Updated icon path
    icon_path = os.path.join(os.path.dirname(__file__), "ui", "resources", "de4py.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    load_stylesheet(app)
    stealth_title = set_stealth_title()
    
    if config_controller.get_rpc():
        try:
            rpc.start_RPC()
        except Exception:
            pass
    
    window = MainWindow(title=stealth_title)
    window.show()
    
    exit_code = app.exec()
    
    # Cleanup
    rpc.KILL_THREAD = True
    logging.info("De4py shutting down")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
