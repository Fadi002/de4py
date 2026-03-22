# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QKeySequence, QShortcut

from .context import context
from .event_bus import bus
from .proxy.animation import DevAnimationController
from .hooks.ui_inspector import UIInspectorHook
from de4py.lang import tr, keys

class DeveloperMenuManager(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        context.app = app
        
        self._panel = None
        self._inspector_hook = UIInspectorHook()
        
        DevAnimationController.inject()
        
        self._app.installEventFilter(self._inspector_hook)
        
        self.shortcut_d = QShortcut(QKeySequence("Ctrl+Shift+D"), self._app)
        self.shortcut_d.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut_d.activated.connect(self.toggle_panel)
        
        self.shortcut_f12 = QShortcut(QKeySequence("F12"), self._app)
        self.shortcut_f12.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.shortcut_f12.activated.connect(self.toggle_panel)
        
        bus.toggle_panel.connect(self.toggle_panel)
        logging.info(tr(keys.DEV_LOG_INIT))

    def toggle_panel(self):
        if not self._panel:
            self._load_panel()
            if not self._panel: return
            
        if self._panel.isVisible():
            self._panel.hide()
            bus.log.emit("DEBUG", tr(keys.DEV_LOG_HIDDEN))
        else:
            self._sync_context()
            self._panel.show()
            self._panel.raise_()
            self._panel.activateWindow()
            bus.log.emit("DEBUG", tr(keys.DEV_LOG_SHOWN))

    def _sync_context(self):
        win = QApplication.activeWindow()
        if win and win != self._panel:
            context.main_window = win
            if hasattr(win, 'sidebar'):
                context.navigation_manager = win

    def _load_panel(self):
        from .panel import DeveloperPanel
        
        main_win = QApplication.activeWindow()
        if not main_win:
            QTimer.singleShot(100, self._load_panel)
            return
            
        self._panel = DeveloperPanel(main_win)
        context.devtools_panel = self._panel
        
        from .overlay import DebugOverlay
        self._overlay = DebugOverlay(main_win)
        context.overlay = self._overlay
        self._overlay.show()
        self._overlay.raise_()

def init_devtools(app: QApplication):
    dev_mode = str(os.getenv("DEV_MODE", "")).lower()
    if dev_mode not in ("1", "true", "on", "yes"):
        return None
        
    assert dev_mode in ("1", "true", "on", "yes"), "SAFETY: DevTools loaded in production environment!"
    
    return DeveloperMenuManager(app)
