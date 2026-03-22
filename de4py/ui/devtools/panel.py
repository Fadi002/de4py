# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QListWidget, 
                             QStackedWidget, QLabel, QFrame, QPushButton, QSizePolicy)
from PySide6.QtCore import Qt, QSize

from de4py.config.config import settings
from de4py.lang import tr, keys

class DeveloperPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr(keys.DEV_TITLE))
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.resize(450, 600) # Balanced compact size
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        from PySide6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("DevToolsTabs")
        self.main_layout.addWidget(self.tabs)
        
        from .controls.app_control import AppControl
        from .controls.ui_control import UIControl
        from .controls.backend_control import BackendControl
        from .controls.log_panel import LogPanel
        from .controls.scenario_control import ScenarioControl
        from .controls.widget_tree import WidgetTree
        
        self.tabs.addTab(AppControl(), f"🚀 {tr(keys.DEV_TAB_APP)}")
        self.tabs.addTab(ScenarioControl(), f"🧪 {tr(keys.DEV_TAB_SCENARIOS)}")
        self.tabs.addTab(WidgetTree(), f"🌳 {tr(keys.DEV_TAB_TREE)}")
        self.tabs.addTab(UIControl(), f"🖥 {tr(keys.DEV_TAB_UI)}")
        self.tabs.addTab(BackendControl(), f"🌐 {tr(keys.DEV_TAB_BACKEND)}")
        self.tabs.addTab(LogPanel(), f"📝 {tr(keys.DEV_TAB_LOGS)}")
        
        self.footer = QFrame()
        self.footer.setObjectName("DevToolsFooter")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(10, 5, 10, 5)
        
        metric_text = f"{settings.version} | Build {settings.build_num} | {sys.platform.upper()}"
        self.footer_label = QLabel(metric_text)
        self.footer_label.setStyleSheet("font-size: 10px; color: #555;")
        self.footer_layout.addWidget(self.footer_label)
        self.footer_layout.addStretch()
        
        self.main_layout.addWidget(self.footer)

    def apply_styles(self):
        self.setStyleSheet("""
            DeveloperPanel {
                background-color: #0d1117;
            }
            #DevToolsTabs {
                background-color: #0d1117;
                border: none;
            }
            QTabWidget::pane {
                border-top: 1px solid #30363d;
                background-color: #0d1117;
            }
            QTabBar::tab {
                background: #0d1117;
                color: #8b949e;
                padding: 10px 15px;
                font-size: 11px;
                font-weight: 600;
                border: none;
            }
            QTabBar::tab:selected {
                color: #007AFF;
                border-bottom: 2px solid #007AFF;
                background: #161b22;
            }
            QTabBar::tab:hover:!selected {
                color: #c9d1d9;
                background: #161b22;
            }
            
            #DevToolsFooter {
                background-color: #161b22;
                border-top: 1px solid #30363d;
                max-height: 25px;
            }
            
            /* Compact Scrollbar */
            QScrollBar:vertical {
                background: #0d1117;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #007AFF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QLabel { color: #8b949e; font-size: 11px; }
            
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                padding: 6px 12px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { 
                background-color: #30363d;
                border: 1px solid #007AFF;
                color: #007AFF;
            }
            QPushButton:pressed { 
                background-color: #007AFF; 
                color: #ffffff; 
            }
            
            QCheckBox { color: #8b949e; spacing: 8px; font-size: 11px; }
            QCheckBox::indicator { 
                width: 14px; 
                height: 14px; 
                border-radius: 4px; 
                border: 1px solid #30363d; 
                background: #0d1117; 
            }
            QCheckBox::indicator:checked { 
                background: #007AFF; 
                border-color: #007AFF; 
                image: none;
            }
            
            QLineEdit, QSpinBox, QSlider {
                background: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                color: #c9d1d9;
                padding: 4px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #007AFF;
            }
        """)
