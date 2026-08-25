# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QHBoxLayout,
                              QPushButton, QLabel, QComboBox, QCheckBox, QListWidgetItem,
                              QSizePolicy)

from .elided import ElidedCheckBox

from de4py.lang import tr, keys
from de4py.ui.constants import COLOR_ACCENT, COLOR_TEXT_DIM, qcolor_rgba
from ..event_bus import bus
from ..hooks.app_log_handler import bridge

_MAX_LOG_ENTRIES = 500

_LEVELS = ("INFO", "WARNING", "ERROR", "DEBUG")
_LEVEL_COLORS = {
    "ERROR": "#ff6b6b",
    "WARNING": "#ffb020",
    "INFO": COLOR_TEXT_DIM,
    "DEBUG": COLOR_ACCENT,
}
_LEVEL_KEYS = [
    keys.DEV_LOG_LEVEL_ALL,
    keys.DEV_LOG_LEVEL_INFO,
    keys.DEV_LOG_LEVEL_WARNING,
    keys.DEV_LOG_LEVEL_ERROR,
    keys.DEV_LOG_LEVEL_DEBUG,
]

class LogPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        bus.log.connect(self.add_log)
        bridge.record.connect(self.add_log)

    def _shrinkable(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        widget.setSizePolicy(policy)

    def _shrinkable_label(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        widget.setSizePolicy(policy)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(tr(keys.DEV_LOG_TITLE))
        self._shrinkable_label(self.title_label)
        header.addWidget(self.title_label)

        self.level_filter = QComboBox()
        self.level_filter.addItems([tr(k) for k in _LEVEL_KEYS])
        self.level_filter.currentIndexChanged.connect(self.apply_filter)
        header.addWidget(self.level_filter)

        self.auto_scroll_check = ElidedCheckBox(tr(keys.DEV_LOG_AUTOSCROLL))
        self.auto_scroll_check.setChecked(True)
        self._shrinkable_label(self.auto_scroll_check)
        header.addWidget(self.auto_scroll_check)

        header.addStretch()
        self.btn_clear = QPushButton(tr(keys.BTN_CLEAR))
        header.addWidget(self.btn_clear)
        self.layout.addLayout(header)

        self.log_list = QListWidget()
        self.btn_clear.clicked.connect(self.log_list.clear)
        self.layout.addWidget(self.log_list, 1)

    def _level_index(self, level):
        if level not in _LEVELS:
            return 1
        return _LEVELS.index(level) + 1

    def _matches_filter(self, level):
        idx = self.level_filter.currentIndex()
        return idx == 0 or idx == self._level_index(level)

    def add_log(self, level, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{timestamp}] [{level}] {message}")
        item.setData(Qt.ItemDataRole.UserRole, level)
        item.setForeground(qcolor_rgba(_LEVEL_COLORS.get(level, COLOR_TEXT_DIM)))
        item.setHidden(not self._matches_filter(level))
        self.log_list.addItem(item)
        if self.auto_scroll_check.isChecked():
            self.log_list.scrollToBottom()

        while self.log_list.count() > _MAX_LOG_ENTRIES:
            self.log_list.takeItem(0)

    def apply_filter(self, index):
        for i in range(self.log_list.count()):
            item = self.log_list.item(i)
            level = item.data(Qt.ItemDataRole.UserRole) or "INFO"
            item.setHidden(not self._matches_filter(level))

    def retranslate_ui(self):
        self.title_label.setText(tr(keys.DEV_LOG_TITLE))
        self.level_filter.blockSignals(True)
        for i, key in enumerate(_LEVEL_KEYS):
            self.level_filter.setItemText(i, tr(key))
        self.level_filter.blockSignals(False)
        self.auto_scroll_check.setText(tr(keys.DEV_LOG_AUTOSCROLL))
        self.btn_clear.setText(tr(keys.BTN_CLEAR))
        self.apply_filter(self.level_filter.currentIndex())
