# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, QLabel, QLineEdit
from PySide6.QtCore import Qt
from de4py.lang import tr, keys
from ..event_bus import bus

class LogPanel(QWidget):
    """
    Live event stream for DevTools events, API calls, and UI interactions.
    """
    def __init__(self):
        super().__init__()
        self.setup_ui()
        bus.log.connect(self.add_log)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        
        # 1. Initialize Log List first (so other elements can ref it)
        self.log_list = QListWidget()
        self.log_list.setStyleSheet("""
            background-color: #000;
            color: #0f0;
            font-family: monospace;
            font-size: 11px;
            border-radius: 4px;
        """)
        
        self.header = QHBoxLayout()
        self.header.addWidget(QLabel(f"<b>{tr(keys.DEV_LOG_TITLE)}</b>"))
        
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr(keys.DEV_LOG_FILTER))
        self.search.setFixedWidth(120)
        self.search.textChanged.connect(self.filter_logs)
        self.header.addWidget(self.search)
        
        btn_clear = QPushButton(tr(keys.BTN_CLEAR))
        btn_clear.setFixedWidth(50)
        btn_clear.clicked.connect(self.log_list.clear)
        self.header.addWidget(btn_clear)
        
        btn_stress = QPushButton(tr(keys.DEV_LOG_STRESS))
        btn_stress.setFixedWidth(50)
        btn_stress.clicked.connect(self.stress_test)
        self.header.addWidget(btn_stress)
        
        self.layout.addLayout(self.header)
        self.layout.addWidget(self.log_list)

    def add_log(self, level: str, message: str):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        text = f"[{timestamp}] [{level}] {message}"
        self.log_list.addItem(text)
        self.log_list.scrollToBottom()
        
        # Color coding
        item = self.log_list.item(self.log_list.count() - 1)
        if level == "ERROR": item.setForeground(Qt.red)
        elif level == "WARNING": item.setForeground(Qt.yellow)
        elif level == "DEBUG": item.setForeground(Qt.cyan)

    def filter_logs(self, text: str):
        for i in range(self.log_list.count()):
            item = self.log_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def stress_test(self):
        """Flushes 100 log entries rapidly to test performance."""
        for i in range(100):
             bus.log.emit("DEBUG", f"STRESS TEST ENTRY #{i}: System stability verification in progress...")
