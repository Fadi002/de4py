# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                              QCheckBox, QHBoxLayout, QGridLayout,
                              QSlider, QTableWidget, QTableWidgetItem, QHeaderView,
                              QComboBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

try:
    import shiboken6 as shiboken
except ImportError:
    try:
        import shiboken
    except ImportError:
        shiboken = None

from de4py.lang import tr, keys
from ..context import context
from ..event_bus import bus

class UIControl(QWidget):
    """
    Control panel for UI inspection, highlighting, and property editing.
    """
    def __init__(self):
        super().__init__()
        self.current_inspect_widget = None
        self.setup_ui()
        bus.inspect_widget.connect(self.show_widget_info)
        bus.trigger_ui_stress.connect(self.break_ui)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # 1. Inspection Toggles
        toggle_grid = QGridLayout()
        self.highlight_check = QCheckBox(tr(keys.DEV_UI_HIGHLIGHT))
        self.highlight_check.toggled.connect(self.set_highlight)
        toggle_grid.addWidget(self.highlight_check, 0, 0)
        
        self.inspect_check = QCheckBox(tr(keys.DEV_UI_INSPECT))
        self.inspect_check.toggled.connect(self.set_inspect)
        toggle_grid.addWidget(self.inspect_check, 0, 1)

        self.fps_check = QCheckBox(tr(keys.DEV_UI_FPS))
        self.fps_check.toggled.connect(self.set_fps)
        toggle_grid.addWidget(self.fps_check, 1, 0)
        self.layout.addLayout(toggle_grid)
        
        # 2. Global Speed Control (0.1x to 5.0x)
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_UI_ANIM_SPEED)}</b>"))
        anim_row = QHBoxLayout()
        self.anim_slider = QSlider(Qt.Orientation.Horizontal)
        self.anim_slider.setRange(1, 50) 
        current_speed = int(context.dev_flags.get("anim_speed", 1.0) * 10)
        self.anim_slider.setValue(current_speed)
        self.anim_slider.valueChanged.connect(self.update_anim_speed)
        
        self.anim_val_label = QLabel(f"{current_speed/10:.1f}x")
        self.anim_val_label.setFixedWidth(40)
        anim_row.addWidget(self.anim_slider)
        anim_row.addWidget(self.anim_val_label)
        self.layout.addLayout(anim_row)

        # 3. Property Inspector
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel(f"<b>{tr(keys.DEV_UI_PROP_INSPECTOR)}</b>"))
        header_row.addStretch()
        btn_refresh = QPushButton(tr(keys.DEV_UI_REFRESH))
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(lambda: self.show_widget_info(self.current_inspect_widget))
        header_row.addWidget(btn_refresh)
        self.layout.addLayout(header_row)

        self.prop_table = QTableWidget(0, 2)
        self.prop_table.setHorizontalHeaderLabels([tr(keys.DEV_PROP_HEADER_PROPERTY), tr(keys.DEV_PROP_HEADER_VALUE)])
        self.prop_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.prop_table.verticalHeader().setVisible(False)
        self.prop_table.setShowGrid(False)
        self.prop_table.setAlternatingRowColors(True)
        self.prop_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.prop_table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed)
        self.prop_table.setMinimumHeight(280)
        self.prop_table.setStyleSheet("""
            QTableWidget {
                background-color: #0d1117;
                alternate-background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                color: #c9d1d9;
                font-family: 'Segoe UI', system-ui;
                gridline-color: transparent;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #30363d;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 10px;
            }
            QTableWidget::item {
                padding: 10px;
                border-bottom: 1px solid #21262d;
            }
            QTableWidget::item:selected {
                background-color: rgba(0, 122, 255, 0.1);
                color: #007AFF;
            }
        """)
        self.prop_table.itemChanged.connect(self.on_property_changed)
        self.layout.addWidget(self.prop_table)
        
        # 4. Stress Tests
        self.layout.addWidget(QLabel(f"<b>{tr(keys.DEV_UI_STRESS_TITLE)}</b>"))
        stress_row = QHBoxLayout()
        stress_row.setSpacing(5)
        
        btn_break = QPushButton(tr(keys.DEV_UI_BREAK))
        btn_break.clicked.connect(self.break_ui)
        stress_row.addWidget(btn_break)
        
        btn_autofill = QPushButton(tr(keys.DEV_UI_AUTOFILL))
        btn_autofill.clicked.connect(self.autofill_inputs)
        stress_row.addWidget(btn_autofill)
        self.layout.addLayout(stress_row)
        
        self.layout.addStretch()

    def _is_alive(self, widget):
        if not widget: return False
        if shiboken: return shiboken.isValid(widget)
        try:
            widget.parent()
            return True
        except:
            return False

    def update_anim_speed(self, value):
        speed = value / 10.0
        context.dev_flags["anim_speed"] = speed
        self.anim_val_label.setText(f"{speed:.1f}x")

    def on_property_changed(self, item):
        if not self._is_alive(self.current_inspect_widget) or item.column() != 1:
            return
            
        row_item = self.prop_table.item(item.row(), 0)
        prop_raw_name = row_item.data(Qt.ItemDataRole.UserRole) or row_item.text()
        new_val = item.text()
        self._apply_property(prop_raw_name, new_val)

    def _apply_property(self, name, value):
        if not self._is_alive(self.current_inspect_widget): return
        try:
            widget = self.current_inspect_widget
            if name == "objectName": widget.setObjectName(value)
            elif name == "toolTip": widget.setToolTip(value)
            elif name == "styleSheet": widget.setStyleSheet(value)
            elif name == "enabled": widget.setEnabled(str(value).lower() == "true")
            elif name == "visible": widget.setVisible(str(value).lower() == "true")
            elif name == "text" and hasattr(widget, 'setText'): widget.setText(value)
            bus.log.emit("INFO", tr(keys.DEV_LOG_PROP_SET).format(name=name, value=value))
        except Exception as e:
            bus.log.emit("ERROR", tr(keys.DEV_LOG_PROP_FAIL).format(error=str(e)))

    def show_widget_info(self, widget):
        if not self._is_alive(widget): return
        self.current_inspect_widget = widget
        
        self.prop_table.blockSignals(True)
        self.prop_table.setRowCount(0)
        
        props = [
            (tr(keys.DEV_PROP_CLASS), widget.metaObject().className(), "label", "class"),
            (tr(keys.DEV_PROP_NAME), widget.objectName() or "", "text", "objectName"),
            (tr(keys.DEV_PROP_TEXT), widget.text() if hasattr(widget, 'text') else None, "text", "text"),
            (tr(keys.DEV_PROP_ENABLED), widget.isEnabled(), "bool", "enabled"),
            (tr(keys.DEV_PROP_VISIBLE), widget.isVisible(), "bool", "visible"),
            (tr(keys.DEV_PROP_STYLE), widget.styleSheet(), "text", "styleSheet"),
            (tr(keys.DEV_PROP_TOOLTIP), widget.toolTip() or "", "text", "toolTip"),
            (tr(keys.DEV_PROP_GEOMETRY), f"{widget.width()}x{widget.height()} @ {widget.x()},{widget.y()}", "label", "geometry"),
        ]
        
        for display_name, val, ptype, raw_name in props:
            if val is None and ptype != "label": continue
            row = self.prop_table.rowCount()
            self.prop_table.insertRow(row)
            
            name_item = QTableWidgetItem(display_name)
            name_item.setData(Qt.ItemDataRole.UserRole, raw_name)
            name_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            name_item.setForeground(QColor("#8b949e"))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
            self.prop_table.setItem(row, 0, name_item)
            
            if ptype == "label":
                val_item = QTableWidgetItem(str(val))
                val_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                val_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self.prop_table.setItem(row, 1, val_item)
            elif ptype == "text":
                val_item = QTableWidgetItem(str(val))
                val_item.setForeground(QColor("#007AFF"))
                val_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter)
                self.prop_table.setItem(row, 1, val_item)
            elif ptype == "bool":
                container = QWidget()
                container.setFixedHeight(30)
                clayout = QHBoxLayout(container)
                clayout.setContentsMargins(10, 0, 10, 0)
                clayout.setSpacing(0)
                
                combo = QComboBox()
                combo.addItems(["True", "False"])
                combo.setCurrentText("True" if val else "False")
                combo.currentTextChanged.connect(lambda v, n=raw_name: self._apply_property(n, v))
                combo.setStyleSheet("""
                    QComboBox { 
                        background: transparent; 
                        color: #007AFF; 
                        border: none;
                        font-weight: bold;
                        padding-left: 0px;
                    }
                    QComboBox::drop-down { border: none; }
                    QComboBox QAbstractItemView {
                        background-color: #161b22;
                        color: #007AFF;
                        selection-background-color: #007AFF;
                        selection-color: #ffffff;
                        border: 1px solid #30363d;
                    }
                """)
                clayout.addWidget(combo)
                clayout.addStretch()
                self.prop_table.setCellWidget(row, 1, container)
            
        self.prop_table.blockSignals(False)

    def set_highlight(self, enabled):
        context.dev_flags["highlight_mode"] = enabled
        if hasattr(context, 'overlay'):
            context.overlay.show_highlight = enabled

    def set_inspect(self, enabled):
        context.dev_flags["inspect_mode"] = enabled
        if hasattr(context, 'overlay'):
            context.overlay.show_inspector = enabled

    def set_fps(self, enabled):
        context.dev_flags["show_fps"] = enabled
        if hasattr(context, 'overlay'):
            context.overlay.show_fps = enabled

    def break_ui(self):
        if not context.main_window: return
        from PySide6.QtWidgets import QLabel
        for lbl in context.main_window.findChildren(QLabel):
            if self._is_alive(lbl) and lbl.text(): 
                try: lbl.setText("UI STRESS " * 10)
                except: pass
        bus.log.emit("WARNING", tr(keys.DEV_LOG_STRESS_APPLIED))

    def autofill_inputs(self):
        if not context.main_window: return
        from PySide6.QtWidgets import QLineEdit, QTextEdit
        for e in context.main_window.findChildren(QLineEdit):
            if self._is_alive(e): e.setText("DE4PY AUTOFILL TEST")
        for t in context.main_window.findChildren(QTextEdit):
            if self._is_alive(t): t.setPlainText("Stress Testing Body Content for De4py DevTools...")
        bus.log.emit("INFO", tr(keys.DEV_LOG_AUTOFILL_DONE))
