# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import os

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

from de4py.lang import keys, tr

from .context import context
from .event_bus import bus
from .hooks.app_log_handler import app_log_handler
from .hooks.ui_inspector import UIInspectorHook
from .proxy.animation import DevAnimationController

class DeveloperMenuManager(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        context.app = app

        self._panel = None
        self._overlay = None
        self._inspector_hook = UIInspectorHook()

        DevAnimationController.inject()

        self._app.installEventFilter(self._inspector_hook)

        self.shortcut_d = QShortcut(QKeySequence("Ctrl+Shift+D"), self._app)
        self.shortcut_d.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut_d.activated.connect(self.toggle_panel)

        self.shortcut_f12 = QShortcut(QKeySequence("F12"), self._app)
        self.shortcut_f12.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut_f12.activated.connect(self.toggle_panel)

        logging.info(tr(keys.DEV_LOG_INIT))

    def toggle_panel(self):
        if not self._panel:
            self._load_panel()
            if not self._panel:
                return

        if self._panel.isVisible():
            self._panel.hide()
            app_log_handler.detach()
            bus.log.emit("DEBUG", tr(keys.DEV_LOG_HIDDEN))
        else:
            self._sync_context()
            app_log_handler.attach()
            self._panel.show()
            self._panel.raise_()
            self._panel.activateWindow()
            bus.log.emit("DEBUG", tr(keys.DEV_LOG_SHOWN))

    def _sync_context(self):
        win = getattr(context, "main_window", None) or QApplication.activeWindow()
        if win and win != self._panel:
            context.main_window = win

    def _load_panel(self):
        from .panel import DeveloperPanel

        main_win = getattr(context, "main_window", None) or QApplication.activeWindow()

        self._panel = DeveloperPanel(main_win)
        context.devtools_panel = self._panel

        if main_win:
            from .overlay import DebugOverlay

            self._overlay = DebugOverlay(main_win)
            context.overlay = self._overlay

    def close(self):
        app_log_handler.detach()
        if self._panel is not None:
            try:
                self._panel.close()
            except RuntimeError:
                pass
            self._panel = None
            context.devtools_panel = None
        if self._overlay is not None:
            try:
                self._overlay.close()
            except RuntimeError:
                pass
            self._overlay = None
            context.overlay = None
        self._app.removeEventFilter(self._inspector_hook)
        DevAnimationController.restore()

def init_devtools(app: QApplication):
    dev_mode = str(os.getenv("DEV_MODE", "")).lower()
    if dev_mode not in ("1", "true", "on", "yes"):
        return None

    return DeveloperMenuManager(app)
