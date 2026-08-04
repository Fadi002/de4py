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

from de4py.core.telemetry_ping import start as _start_telemetry_ping
from de4py.config.config import settings


def check_dependencies():
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
    global DEFAULT_QSS  # noqa: needed for stylesheet caching
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

    args = parser.parse_args()

    if args.about:
        from de4py._meta import print_about
        print_about()
        return

    if args.checksums_gen:
        from de4py.utils.fs import generate_checksums, save_checksums
        checksums = generate_checksums()
        save_checksums(checksums)
        print("Checksums generated successfully.")
        return


    check_dependencies()
    _start_telemetry_ping()

    import logging
    import colorama
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from de4py.ui.main_window import MainWindow
    from de4py.utils import rpc, sentry, setup_logging
    from de4py.utils.errors import install as _install_excepthook
    _install_excepthook()
    from de4py.utils import tui
    import signal
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    colorama.init(autoreset=True)
    setup_logging()
    sentry.init()
    
    _IS_WINDOWS = sys.platform == "win32"
    
    tui.clear_console()
    print(tui.__BANNER__)

    logging.info("Starting de4py")


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

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

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

        icon_path = os.path.join(os.path.dirname(__file__), "ui", "resources", "de4py.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        load_stylesheet(app)
        stealth_title = set_stealth_title()
        
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
                        if hasattr(plugin_instance, 'colors'):
                            from PySide6.QtGui import QColor
                            theme_colors = plugin_instance.colors
                            if "spinner_color" in theme_colors:
                                window.loading_overlay.setBrandColor(QColor(theme_colors["spinner_color"]))
                            if "secondary" in theme_colors:
                                window.drop_overlay.set_border_color(QColor(theme_colors["secondary"]))
                        break
            except Exception as e:
                logging.error(f"Failed to load persistent theme: {e}")
                settings.active_theme = None
                settings.save()

        window.show()

        def _on_rpc_changed(enabled):
            if enabled:
                try:
                    rpc.start_rpc()
                except Exception:
                    pass
            else:
                rpc.stop_rpc()

        def _on_stealth_changed(enabled):
            if enabled:
                set_stealth_title()
            else:
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetConsoleTitleW("de4py")
                except Exception:
                    pass

        def _initialize_optional_services():
            try:
                from de4py.ui.devtools.context import context
                context.main_window = window
            except Exception:
                pass

            try:
                from de4py.ui.devtools.manager import init_devtools
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
                    rpc.start_rpc()
                except Exception:
                    pass

            from de4py.config.config import get_settings_emitter
            emitter = get_settings_emitter()
            emitter.rpc_changed.connect(_on_rpc_changed)
            emitter.stealth_title_changed.connect(_on_stealth_changed)

            if settings.auto_update_check:
                try:
                    from de4py.updater.manager import UpdateManager
                    from de4py.ui.widgets.update_dialog import UpdateDialog
                    from de4py.ui.widgets.notification_widget import NotificationManager

                    updater = UpdateManager.get()

                    def _on_update_available(result):
                        notif_mgr = NotificationManager(window)
                        notif_mgr.show_notification("info", f"Update available: {result.remote}")

                        dialog = UpdateDialog(result, parent=window)
                        dialog.fade_in()

                        def _on_confirmed():
                            updater.start_download(result.remote)

                        updater.download_progress.connect(dialog.set_download_progress)
                        updater.update_ready.connect(lambda _: dialog.show_ready())
                        updater.update_failed.connect(dialog.show_error)
                        dialog.update_confirmed.connect(_on_confirmed)
                        dialog.install_confirmed.connect(updater.apply)
                        dialog.dismissed.connect(dialog.fade_out)

                    updater.update_available.connect(_on_update_available)
                    QTimer.singleShot(3000, updater.check_for_updates)
                except Exception as e:
                    logging.debug(f"Update service init failed: {e}")

            if os.getenv("DEV_MODE") == "1":
                try:
                    import de4py.api.client
                    from de4py.ui.devtools.proxy.api import DevApiProxy
                    de4py.api.client.De4pyApiClient = DevApiProxy
                    logging.info("[DevTools] API Client Class hijacked for proxying.")
                except Exception as e:
                    logging.debug(f"[DevTools] Proxy injection failed: {e}")

        QTimer.singleShot(0, _initialize_optional_services)
        
        exit_code = app.exec()
        
        rpc.KILL_THREAD = True
        logging.info("De4py shutting down")
        sys.exit(exit_code)

if __name__ == "__main__":
    main()
