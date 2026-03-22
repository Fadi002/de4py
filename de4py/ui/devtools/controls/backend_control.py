# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                             QRadioButton, QButtonGroup, QSpinBox, QGridLayout, QHBoxLayout)
from de4py.lang import tr, keys
from ..context import context
from ..event_bus import bus

class BackendControl(QWidget):
    """
    Control panel for managing the API state and simulated failures.
    """
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # 1. API Mode (Horizontal Row)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_BACKEND_STATE_TITLE)}</b>"))
        self.mode_group = QButtonGroup(self)
        mode_row = QHBoxLayout()
        
        modes = [
            (tr(keys.DEV_BACKEND_MODE_NORMAL), "Normal"),
            (tr(keys.DEV_BACKEND_MODE_FAIL), "Fail"),
            (tr(keys.DEV_BACKEND_MODE_EMPTY), "Empty")
        ]
        for i, (label, m) in enumerate(modes):
            radio = QRadioButton(label)
            if m == "Normal": radio.setChecked(True)
            radio.toggled.connect(lambda checked, m=m: self.set_api_mode(m) if checked else None)
            self.mode_group.addButton(radio, i)
            mode_row.addWidget(radio)
        self.layout.addLayout(mode_row)
            
        # 2. Latency (Compact)
        latency_box = QHBoxLayout()
        latency_box.addWidget(QLabel(tr(keys.DEV_BACKEND_LATENCY)))
        self.latency_spin = QSpinBox()
        self.latency_spin.setRange(0, 10000)
        self.latency_spin.setSingleStep(100)
        self.latency_spin.setFixedWidth(80)
        self.latency_spin.valueChanged.connect(self.set_latency)
        latency_box.addWidget(self.latency_spin)
        latency_box.addStretch()
        self.layout.addLayout(latency_box)
        
        # 3. Network Presets (Grid)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_BACKEND_CONDITIONS_TITLE)}</b>"))
        grid = QGridLayout()
        grid.setSpacing(5)
        presets = {
            tr(keys.DEV_BACKEND_PRESET_SLOW3G): 3000, 
            tr(keys.DEV_BACKEND_PRESET_2GEDGE): 8000, 
            tr(keys.DEV_BACKEND_OFFLINE): -1
        }
        for i, (name, val) in enumerate(presets.items()):
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, v=val: self.apply_preset(v))
            grid.addWidget(btn, 0, i)
        self.layout.addLayout(grid)

        self.layout.addStretch()

    def set_api_mode(self, mode: str):
        context.dev_flags["api_fail"] = (mode == "Fail")
        context.dev_flags["api_empty"] = (mode == "Empty")
        bus.log.emit("DEBUG", f"API Mode changed to: {mode}")

    def set_latency(self, ms: int):
        context.dev_flags["api_delay"] = ms
        bus.log.emit("DEBUG", f"API Latency set to: {ms}ms")

    def apply_preset(self, val: int):
        if val == -1: # Offline
            context.dev_flags["api_fail"] = True
            self.mode_group.button(1).setChecked(True)
        else:
            self.latency_spin.setValue(val)
