# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QComboBox, QSlider, QListWidget, QListWidgetItem,
                              QPushButton, QSizePolicy)

from .elided import ElidedLabel

from de4py.lang import tr, keys
from de4py.ui.constants import COLOR_TEXT_DIM, qcolor_rgba
from ..context import context
from ..event_bus import bus

_MAX_FEED = 200

class BackendControl(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        bus.api_call.connect(self.add_call)

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
        self.layout.setSpacing(10)

        mode_row = QHBoxLayout()
        self.mode_label = ElidedLabel(tr(keys.DEV_NET_MODE))
        self._shrinkable_label(self.mode_label)
        mode_row.addWidget(self.mode_label)
        self.mode_combo = QComboBox()
        self._shrinkable(self.mode_combo)
        self.mode_combo.addItems([
            tr(keys.DEV_NET_MODE_NORMAL),
            tr(keys.DEV_NET_MODE_FAIL),
            tr(keys.DEV_NET_MODE_EMPTY),
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        mode_row.addWidget(self.mode_combo)
        mode_row.addStretch()
        self.layout.addLayout(mode_row)

        latency_row = QHBoxLayout()
        self.latency_label = ElidedLabel(tr(keys.DEV_NET_LATENCY))
        self._shrinkable_label(self.latency_label)
        latency_row.addWidget(self.latency_label)
        self.latency_slider = QSlider(Qt.Orientation.Horizontal)
        self.latency_slider.setRange(0, 10000)
        self.latency_slider.setSingleStep(100)
        self.latency_slider.valueChanged.connect(self.on_latency_changed)
        self.latency_val_label = QLabel("0ms")
        self.latency_val_label.setFixedWidth(56)
        latency_row.addWidget(self.latency_slider, 1)
        latency_row.addWidget(self.latency_val_label, 0)
        self.layout.addLayout(latency_row)

        load_row = QHBoxLayout()
        self.load_label = ElidedLabel(tr(keys.DEV_NET_SIMULATE))
        self._shrinkable_label(self.load_label)
        load_row.addWidget(self.load_label)
        self.load_slider = QSlider(Qt.Orientation.Horizontal)
        self.load_slider.setRange(0, 10)
        self.load_slider.setSingleStep(1)
        self.load_slider.setValue(3)
        self.load_slider.valueChanged.connect(self.on_load_changed)
        self.load_val_label = QLabel(self._load_text())
        self.load_val_label.setFixedWidth(56)
        self.load_btn = QPushButton(tr(keys.DEV_NET_TRIGGER))
        self._shrinkable_label(self.load_btn)
        self.load_btn.clicked.connect(self.trigger_loading)
        load_row.addWidget(self.load_slider, 1)
        load_row.addWidget(self.load_val_label, 0)
        load_row.addWidget(self.load_btn, 0)
        self.layout.addLayout(load_row)

        feed_header = QHBoxLayout()
        self.feed_label = ElidedLabel(tr(keys.DEV_NET_FEED))
        feed_header.addWidget(self.feed_label)
        feed_header.addStretch()
        self.btn_clear = QPushButton(tr(keys.BTN_CLEAR))
        self.btn_clear.clicked.connect(self.clear_feed)
        feed_header.addWidget(self.btn_clear)
        self.layout.addLayout(feed_header)

        self.feed = QListWidget()
        self.feed.setWordWrap(True)
        self.layout.addWidget(self.feed, 1)

    def _load_text(self):
        return f"{self.load_slider.value()}s"

    def on_mode_changed(self, index):
        context.dev_flags["api_fail"] = (index == 1)
        context.dev_flags["api_empty"] = (index == 2)
        bus.log.emit("DEBUG", f"API mode set to {self.mode_combo.currentText()}")

    def on_latency_changed(self, ms):
        context.dev_flags["api_delay"] = ms
        self.latency_val_label.setText(f"{ms}ms")

    def on_load_changed(self, value):
        self.load_val_label.setText(self._load_text())

    def trigger_loading(self):
        seconds = self.load_slider.value()
        main_win = getattr(context, "main_window", None)
        if main_win is None or not hasattr(main_win, "show_loading"):
            bus.log.emit("WARNING", "Main window has no loading overlay")
            return
        bus.log.emit("INFO", f"Simulating loading for {seconds}s")
        main_win.show_loading()
        QTimer.singleShot(seconds * 1000, self._end_loading)

    def _end_loading(self):
        main_win = getattr(context, "main_window", None)
        if main_win is not None and hasattr(main_win, "hide_loading"):
            main_win.hide_loading()

    def clear_feed(self):
        self.feed.clear()

    def add_call(self, method, endpoint):
        item = QListWidgetItem(f"{method}  {endpoint}")
        item.setForeground(qcolor_rgba(COLOR_TEXT_DIM))
        self.feed.addItem(item)
        self.feed.scrollToBottom()
        while self.feed.count() > _MAX_FEED:
            self.feed.takeItem(0)

    def retranslate_ui(self):
        self.mode_label.setText(tr(keys.DEV_NET_MODE))
        self.latency_label.setText(tr(keys.DEV_NET_LATENCY))
        self.load_label.setText(tr(keys.DEV_NET_SIMULATE))
        self.load_btn.setText(tr(keys.DEV_NET_TRIGGER))
        self.feed_label.setText(tr(keys.DEV_NET_FEED))
        self.btn_clear.setText(tr(keys.BTN_CLEAR))
        self.mode_combo.blockSignals(True)
        self.mode_combo.setItemText(0, tr(keys.DEV_NET_MODE_NORMAL))
        self.mode_combo.setItemText(1, tr(keys.DEV_NET_MODE_FAIL))
        self.mode_combo.setItemText(2, tr(keys.DEV_NET_MODE_EMPTY))
        self.mode_combo.blockSignals(False)
