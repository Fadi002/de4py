# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QSlider, QHBoxLayout, QGridLayout, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QScreen
from de4py.lang import tr, keys
from ..context import context
from ..event_bus import bus

class AppControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_APP_NAV_TITLE)}</b>"))
        grid = QGridLayout()
        grid.setSpacing(5)
        
        nav_pages = [
            (tr(keys.NAV_HOME), "home"),
            (tr(keys.NAV_ANALYZER), "analyzer"),
            (tr(keys.NAV_SETTINGS), "settings")
        ]
        for i, (label, page) in enumerate(nav_pages):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, p=page: self.navigate_to(p))
            grid.addWidget(btn, 0, i)
            
        presets = {
            tr(keys.DEV_APP_PRESET_MOBILE): (400, 800), 
            tr(keys.DEV_APP_PRESET_TABLET): (800, 1000), 
            tr(keys.DEV_APP_PRESET_DESKTOP): (1200, 900)
        }
        for i, (name, size) in enumerate(presets.items()):
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, s=size: self.resize_app(s))
            grid.addWidget(btn, 1, i)
            
        self.layout.addLayout(grid)
        
        self.layout.addSpacing(10)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_APP_NOTIF_TITLE)}</b>"))
        notif_grid = QGridLayout()
        notif_grid.setSpacing(5)
        notif_types = [
            (tr(keys.COMMON_MSG_SUCCESS), "success"),
            (tr(keys.COMMON_MSG_ERROR), "error"),
            (tr(keys.COMMON_MSG_INFO), "info")
        ]
        for i, (label, ntype) in enumerate(notif_types):
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, t=ntype: self.trigger_notification(t))
            notif_grid.addWidget(btn, 0, i)
        self.layout.addLayout(notif_grid)

        loading_box = QHBoxLayout()
        loading_box.addWidget(QLabel(tr(keys.DEV_APP_LOAD_SIM)))
        self.load_duration = QSlider(Qt.Horizontal)
        self.load_duration.setRange(1, 10)
        self.load_duration.setValue(2)
        loading_box.addWidget(self.load_duration)
        self.load_label = QLabel("2s")
        self.load_duration.valueChanged.connect(lambda v: self.load_label.setText(f"{v}s"))
        loading_box.addWidget(self.load_label)
        btn_loading = QPushButton(f"🚀 {tr(keys.DEV_APP_RUN)}")
        btn_loading.setFixedWidth(80)
        btn_loading.clicked.connect(self.simulate_loading)
        loading_box.addWidget(btn_loading)
        self.layout.addLayout(loading_box)

        self.layout.addSpacing(10)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_APP_SYSTEM_TITLE)}</b>"))
        
        sys_grid = QGridLayout()
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(8, 20)
        self.font_slider.setValue(12)
        self.font_slider.valueChanged.connect(self.update_font_scale)
        sys_grid.addWidget(QLabel(tr(keys.DEV_APP_FONT_SIZE)), 0, 0)
        sys_grid.addWidget(self.font_slider, 0, 1)
        
        btn_reload = QPushButton(f"🔄 {tr(keys.DEV_APP_FORCE_RELOAD)}")
        btn_reload.clicked.connect(self.force_reload)
        sys_grid.addWidget(btn_reload, 1, 0, 1, 2)
        self.layout.addLayout(sys_grid)
        
        self.layout.addStretch()
        
        self.layout.addStretch()

    def force_reload(self):
        if context.main_window and hasattr(context.main_window, 'screen_stack'):
            stack = context.main_window.screen_stack
            idx = stack.currentIndex()
            stack.fade_to_index(idx)
            bus.log.emit("INFO", f"APP: Force reloaded screen index {idx}")

    def navigate_to(self, page_name: str):
        mapping = {
            "dashboard": "home",
            "analyzer": "analyzer",
            "settings": "settings"
        }
        screen_id = mapping.get(page_name.lower(), page_name.lower())
        
        if context.navigation_manager:
            for attr in ['_navigate_to', 'navigate_to']:
                if hasattr(context.navigation_manager, attr):
                    getattr(context.navigation_manager, attr)(screen_id)
                    bus.log.emit("INFO", f"NAV: Navigated to {screen_id}")
                    return
        
        elif context.main_window:
            pass

    def update_font_scale(self, size: int):
        if context.app:
            from PySide6.QtGui import QFont
            font = context.app.font()
            font.setPointSize(size)
            context.app.setFont(font)
            for widget in context.app.topLevelWidgets():
                widget.setFont(font)
            bus.log.emit("INFO", f"APP: Global font scale set to {size}pt")

    def resize_app(self, size):
        if not context.main_window: return
        
        mw = context.main_window
        target_w, target_h = size
        
        mw.setMinimumSize(0, 0)
        mw.setMaximumSize(16777215, 16777215) 
        
        screen = mw.screen()
        if screen:
            avail = screen.availableGeometry()
            max_w = avail.width() - 40
            max_h = avail.height() - 60 
            
            pushed = False
            if target_w > max_w:
                target_w = max_w
                pushed = True
            if target_h > max_h:
                target_h = max_h
                pushed = True
            
            if pushed:
                bus.log.emit("WARNING", f"APP: Screen too small for preset. Clamped to {target_w}x{target_h}")
        
        mw.resize(target_w, target_h)
        mw.setFixedSize(target_w, target_h)
        bus.log.emit("INFO", f"APP: Resized and locked to {target_w}x{target_h}")

    def trigger_notification(self, ntype: str):
        if context.main_window:
            import time
            msg = f"DevTools {ntype.capitalize()} Test at {time.strftime('%H:%M:%S')}"
            context.main_window.show_notification(ntype, msg)
            bus.log.emit("DEBUG", f"Triggered {ntype} notification.")

    def simulate_loading(self):
        if context.main_window:
            duration = self.load_duration.value() * 1000
            context.main_window.show_loading()
            bus.log.emit("INFO", f"Loading overlay active ({duration}ms)")
            QTimer.singleShot(duration, context.main_window.hide_loading)
