# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import sys

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTabWidget,
                              QSizePolicy)
from PySide6.QtCore import Qt

from de4py.config.config import settings
from de4py.lang import tr, keys, translation_manager
from de4py.ui.constants import (COLOR_BG_DARK, COLOR_BG_FRAME, COLOR_BG_INPUT,
                               COLOR_BG_INPUT_HOVER, COLOR_ACCENT, COLOR_ACCENT_DIM,
                               COLOR_TEXT, COLOR_TEXT_DIM,
                               FONT_FAMILY_MONO, FONT_FAMILY_UI, BUTTON_RADIUS, FRAME_RADIUS)
from .hooks.app_log_handler import app_log_handler
from .controls.elided import ElidedLabel

class DeveloperPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr(keys.DEV_TITLE))
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.resize(720, 520)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setup_ui()
        self.apply_styles()
        self.retranslate_ui()

        translation_manager.language_changed.connect(self.retranslate_ui)
        app_log_handler.attach()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("DevToolsTabs")
        self.main_layout.addWidget(self.tabs)

        from .controls.inspector import InspectorTab
        from .controls.perf import PerfTab
        from .controls.backend_control import BackendControl
        from .controls.log_panel import LogPanel

        self._tabs = [
            (InspectorTab(), keys.DEV_TAB_INSPECT),
            (PerfTab(), keys.DEV_TAB_PERF),
            (BackendControl(), keys.DEV_TAB_NETWORK),
            (LogPanel(), keys.DEV_TAB_LOGS),
        ]
        for tab, key in self._tabs:
            self.tabs.addTab(tab, tr(key).upper())

        self.footer = QFrame()
        self.footer.setObjectName("DevToolsFooter")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(12, 4, 12, 4)
        self.footer_label = ElidedLabel()
        self.footer_label.setMinimumWidth(0)
        policy = self.footer_label.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        self.footer_label.setSizePolicy(policy)
        self.footer_layout.addWidget(self.footer_label)
        self.footer_layout.addStretch()
        self.main_layout.addWidget(self.footer)

    def apply_styles(self):
        self.setStyleSheet(f"""
            DeveloperPanel {{
                background-color: {COLOR_BG_DARK};
            }}
            #DevToolsTabs {{
                background-color: {COLOR_BG_DARK};
                border: none;
                font-family: {FONT_FAMILY_UI};
            }}
            QTabWidget::pane {{
                border-top: 1px solid {COLOR_BG_FRAME};
                background-color: {COLOR_BG_DARK};
                border-radius: {FRAME_RADIUS}px;
            }}
            QTabBar::tab {{
                background: {COLOR_BG_DARK};
                color: {COLOR_TEXT_DIM};
                padding: 8px 18px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 12px;
                border: none;
            }}
            QTabBar::tab:selected {{
                color: {COLOR_ACCENT};
                border-bottom: 2px solid {COLOR_ACCENT};
                background: {COLOR_BG_FRAME};
            }}
            QTabBar::tab:hover:!selected {{
                color: {COLOR_TEXT};
                background: {COLOR_BG_FRAME};
            }}
            #DevToolsFooter {{
                background-color: {COLOR_BG_FRAME};
                border-top: 1px solid {COLOR_BG_DARK};
                max-height: 26px;
            }}
            #DevToolsFooter QLabel {{
                color: {COLOR_TEXT_DIM};
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(2, 135, 207, 0.55);
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(2, 135, 207, 0.9);
            }}
            QScrollBar:horizontal {{
                background: transparent;
                height: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(2, 135, 207, 0.55);
                min-width: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgba(2, 135, 207, 0.9);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            QLabel {{ color: {COLOR_TEXT}; font-size: 11px; font-family: {FONT_FAMILY_UI}; }}
            QPushButton {{
                background-color: {COLOR_BG_INPUT};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BG_FRAME};
                padding: 5px 12px;
                border-radius: {BUTTON_RADIUS}px;
                font-size: 11px;
                font-family: {FONT_FAMILY_UI};
            }}
            QPushButton:hover {{
                background-color: {COLOR_BG_INPUT_HOVER};
                border: 1px solid {COLOR_ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {COLOR_ACCENT};
                color: {COLOR_TEXT};
            }}
            QCheckBox {{ color: {COLOR_TEXT_DIM}; spacing: 6px; font-size: 11px; }}
            QCheckBox::indicator {{
                width: 14px; height: 14px; border-radius: 4px;
                border: 1px solid {COLOR_BG_INPUT}; background: {COLOR_BG_DARK};
            }}
            QCheckBox::indicator:checked {{
                background: {COLOR_ACCENT}; border-color: {COLOR_ACCENT};
            }}
            QLineEdit, QComboBox, QSlider, QTreeWidget, QTableWidget, QListWidget,
            QPlainTextEdit, QSpinBox {{
                background: {COLOR_BG_INPUT};
                border: 1px solid {COLOR_BG_FRAME};
                border-radius: 6px;
                color: {COLOR_TEXT};
                padding: 4px;
                font-size: 11px;
                font-family: {FONT_FAMILY_UI};
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {COLOR_ACCENT};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLOR_BG_INPUT};
                color: {COLOR_TEXT};
                selection-background-color: {COLOR_ACCENT};
                selection-color: {COLOR_TEXT};
                border: 1px solid {COLOR_BG_FRAME};
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background: {COLOR_BG_INPUT_HOVER};
                border: none;
                width: 14px;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 6px;
                height: 6px;
            }}
            QTreeWidget::item:selected, QTableWidget::item:selected {{
                background-color: {COLOR_ACCENT_DIM};
                color: {COLOR_TEXT};
            }}
            QHeaderView::section {{
                background-color: {COLOR_BG_FRAME};
                color: {COLOR_TEXT_DIM};
                border: none;
                padding: 4px;
                font-size: 10px;
                font-family: {FONT_FAMILY_MONO};
            }}
            #DevRateValue {{
                font-family: {FONT_FAMILY_MONO};
                font-size: 34px;
                color: {COLOR_ACCENT};
            }}
            QListWidget {{ font-family: {FONT_FAMILY_MONO}; }}
        """)

    def retranslate_ui(self):
        self.setWindowTitle(tr(keys.DEV_TITLE))
        for i, (tab, key) in enumerate(self._tabs):
            self.tabs.setTabText(i, tr(key).upper())
            if hasattr(tab, 'retranslate_ui'):
                tab.retranslate_ui()

        metric_text = f"{settings.version} | {settings.build_num} | {sys.platform.upper()} | DEV"
        self.footer_label.setText(metric_text)

    def closeEvent(self, event):
        app_log_handler.detach()
        super().closeEvent(event)
