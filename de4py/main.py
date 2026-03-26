# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import sys
import os
import argparse

# Global configuration and meta
from de4py.config.config import settings
__version__ = settings.version

# Module-level store for the default QSS stylesheet
DEFAULT_QSS = ""

def check_dependencies():
    """Verify that all required libraries are installed."""
    REQUIRED_LIBS = {
        "PySide6": "PySide6",
        "requests": "requests",
        "psutil": "psutil",
        "colorama": "colorama",
        "Crypto": "pycryptodome",
        "pypresence": "pypresence",
        "xdis": "xdis",
        "sentry_sdk": "sentry-sdk",
        "pefile": "pefile",
        "msvcrt": "msvcrt"
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

def load_stylesheet(app):
    """Loads the dark theme QSS stylesheet."""
    global DEFAULT_QSS
    from PySide6.QtCore import QFile, QTextStream
    theme_path = os.path.join(os.path.dirname(__file__), "ui", "themes", "dark_theme.qss")
    if os.path.exists(theme_path):
        file = QFile(theme_path)
        if file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text):
            stream = QTextStream(file)
            qss = stream.readAll()
            app.setStyleSheet(qss)
            file.close()
            DEFAULT_QSS = qss
            return qss
    return ""

def set_stealth_title():
    """Sets a random console title for stealth if enabled."""
    import random
    import string
    import ctypes
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
    parser.add_argument("--about", action="store_true", help="Show project info and exit")
    parser.add_argument("--checksums-gen", action="store_true", help="Generate project checksums")
    parser.add_argument("--update-check", action="store_true", help="Check for available updates")
    parser.add_argument("--update", action="store_true", help="Download and install the latest update")
    parser.add_argument("--rollback", action="store_true", help="Rollback to the previous version")
    args = parser.parse_args()

    if args.about:
        from de4py.about import print_about
        print_about()
        return

    if args.checksums_gen:
        from de4py.utils.checksums import main as run_checksum_gen
        run_checksum_gen()
        return

    # ── UpdateManager CLI commands ──────────────────────────────────
    if args.update_check or args.update or args.rollback:
        from de4py.update_manager import UpdateManager
        mgr = UpdateManager(
            current_version=settings.version,
            channel=getattr(settings, 'update_channel', 'stable'),
            auto_update=getattr(settings, 'auto_update', True),
        )

        if args.rollback:
            if mgr.has_rollback_available():
                print("[*] Rolling back to previous version...")
                if mgr.rollback():
                    print("[+] Rollback successful. Please restart de4py.")
                else:
                    print("[!] Rollback failed.")
            else:
                print("[!] No backup available for rollback.")
            return

        release = mgr.check()
        if release:
            print(f"[+] Update available: {release.version}")
            if release.changelog:
                print(f"    Changelog: {release.changelog[:200]}...")
            if args.update:
                print("[*] Downloading and installing update...")
                if mgr.download_and_install(release):
                    print("[+] Update installed. Please restart de4py.")
                else:
                    print("[!] Update failed. Use --rollback if needed.")
        else:
            print(f"[+] You are running the latest version ({settings.version})")
        return

    # For any other mode, check dependencies first
    check_dependencies()
    
    # Delayed imports to avoid errors if dependencies were missing
    import logging
    import colorama
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from de4py.ui.main_window import MainWindow
    from de4py.utils import rpc, sentry, setup_logging
    from de4py.utils import tui
    import signal
    import msvcrt
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    colorama.init(autoreset=True)
    setup_logging()
    sentry.init()
    
    # OS specifics
    _IS_WINDOWS = sys.platform == "win32"
    
    # Show Banner
    tui.clear_console()
    print(tui.__BANNER__)


    logging.info("Starting de4py")

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
        
        # Initialize Developer Tools if in DEV_MODE
        try:
            from de4py.ui.devtools.manager import init_devtools
            from de4py.ui.devtools.context import context
            app._dev_manager = init_devtools(app)
            if app._dev_manager:
                print("\n" + "="*40)
                print("[+] Developer Mode ACTIVE")
                print("[+] Press Ctrl+Shift+D to open Control Panel")
                print("="*40 + "\n")
        except Exception as e:
            logging.error(f"[DevTools] Failed to initialize: {e}")
            import traceback
            traceback.print_exc()
        
        if settings.rpc:
            try:
                rpc.start_RPC()
            except Exception:
                pass
        
        if os.getenv("DEV_MODE") == "1":
            try:
                import de4py.api.client
                from de4py.ui.devtools.proxy.api import DevApiProxy
                de4py.api.client.De4pyApiClient = DevApiProxy
                logging.info("[DevTools] API Client Class hijacked for proxying.")
            except Exception as e:
                logging.debug(f"[DevTools] Proxy injection failed: {e}")
        
        window = MainWindow(title=stealth_title)
        context.main_window = window
        
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
