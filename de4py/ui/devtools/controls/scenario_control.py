# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QGridLayout
from de4py.lang import tr, keys
from ..scenarios import ScenarioEngine

class ScenarioControl(QWidget):
    """
    UI for triggering predefined application scenarios.
    """
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_SCENARIO_TITLE)}</b>"))
        
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        grid.setSpacing(5)
        
        scenarios = [
            (tr(keys.DEV_SCENARIO_NETWORK), ScenarioEngine.trigger_network_blackout),
            (tr(keys.DEV_SCENARIO_UI_STRESS), ScenarioEngine.trigger_ui_stress),
            (tr(keys.DEV_SCENARIO_FIRST_RUN), ScenarioEngine.trigger_first_run),
        ]
        
        for i, (name, func) in enumerate(scenarios):
            btn = QPushButton(name)
            btn.setMinimumHeight(35)
            btn.clicked.connect(func)
            grid.addWidget(btn, 0, i)
            
        self.layout.addLayout(grid)
        
        self.layout.addSpacing(10)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_SCENARIO_MAINTENANCE)}</b>"))
        btn_reset = QPushButton(f"♻ {tr(keys.DEV_SCENARIO_RESET)}")
        btn_reset.setStyleSheet("background-color: #331111; color: #ff8888; font-weight: bold; border: 1px solid #442222;")
        btn_reset.clicked.connect(ScenarioEngine.reset_all)
        self.layout.addWidget(btn_reset)
        
        self.layout.addStretch()
