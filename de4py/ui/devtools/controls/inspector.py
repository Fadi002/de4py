# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import re

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
                              QSplitter, QScrollArea, QFrame, QGridLayout, QLineEdit,
                              QSpinBox, QSlider, QPlainTextEdit, QPushButton,
                              QGraphicsOpacityEffect, QColorDialog, QSizePolicy, QLayout)

from .elided import ElidedCheckBox

try:
    import shiboken6 as shiboken
except ImportError:
    try:
        import shiboken
    except ImportError:
        shiboken = None

from de4py.lang import tr, keys
from de4py.ui.constants import (COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                                FONT_FAMILY_MONO)
from ..context import context
from ..event_bus import bus
from .widget_tree import WidgetTree

_COLOR_RULE = re.compile(r"color\s*:\s*([^;{}]+);")


class InspectorTab(QWidget):
    def __init__(self):
        super().__init__()
        self.current_widget = None
        self._editor_widget = None
        self._original_snapshot = None
        self._syncing = False
        self._color_dirty = False
        self.setup_ui()
        bus.inspect_widget.connect(self.show_widget_info)

        self.apply_timer = QTimer(self)
        self.apply_timer.setSingleShot(True)
        self.apply_timer.setInterval(300)
        self.apply_timer.timeout.connect(self.apply_edits)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(8)

        toolbar = QHBoxLayout()
        self.highlight_check = ElidedCheckBox(tr(keys.DEV_UI_HIGHLIGHT))
        self._shrinkable_label(self.highlight_check)
        self.highlight_check.toggled.connect(self.set_highlight)
        toolbar.addWidget(self.highlight_check)

        self.inspect_check = ElidedCheckBox(tr(keys.DEV_UI_INSPECT))
        self._shrinkable_label(self.inspect_check)
        self.inspect_check.toggled.connect(self.set_inspect)
        toolbar.addWidget(self.inspect_check)

        toolbar.addStretch()
        self.layout.addLayout(toolbar)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = WidgetTree()
        self.splitter.addWidget(self.tree)

        self.detail = QFrame()
        self.detail_layout = QGridLayout(self.detail)
        self.detail_layout.setContentsMargins(8, 8, 8, 8)
        self.detail_layout.setVerticalSpacing(6)
        self.detail_layout.setHorizontalSpacing(8)

        self._detail_headers = []
        self._detail_values = []
        self._edit_labels = []

        detail_scroll = QScrollArea()
        detail_scroll.setWidget(self.detail)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setMinimumWidth(0)
        self.splitter.addWidget(detail_scroll)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([380, 300])
        self.layout.addWidget(self.splitter, 1)

        self._build_detail_rows()
        self._build_edit_section()
        self.detail_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)

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

    def _build_detail_rows(self):
        labels = [
            keys.DEV_PROP_CLASS,
            keys.DEV_PROP_NAME,
            keys.DEV_PROP_GEOMETRY,
            keys.DEV_PROP_GLOBAL_GEOMETRY,
            keys.DEV_PROP_VISIBLE,
            keys.DEV_PROP_ENABLED,
            keys.DEV_PROP_PARENT_CHAIN,
            keys.DEV_PROP_CHILD_COUNT,
        ]
        for row, key in enumerate(labels):
            header = QLabel(tr(key))
            header.setWordWrap(True)
            header.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px;")
            value = QLabel("-")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet(f"color: {COLOR_TEXT}; font-size: 11px;")
            self._shrinkable_label(header)
            self._shrinkable_label(value)
            self.detail_layout.addWidget(header, row, 0, Qt.AlignmentFlag.AlignTop)
            self.detail_layout.addWidget(value, row, 1, Qt.AlignmentFlag.AlignTop)
            self._detail_headers.append(header)
            self._detail_values.append(value)
        self.detail_layout.setColumnStretch(1, 1)

    def _edit_label(self, key):
        lbl = QLabel(tr(key))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: 10px;")
        self._shrinkable_label(lbl)
        self._edit_labels.append((lbl, key))
        return lbl

    def _build_edit_section(self):
        g = self.detail_layout
        start = len(self._detail_headers)

        header_row = QHBoxLayout()
        title = QLabel(tr(keys.DEV_EDIT_TITLE))
        title.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-family: {FONT_FAMILY_MONO};"
            " font-size: 10px; letter-spacing: 1px;"
        )
        self._edit_title = title
        header_row.addWidget(title)
        header_row.addStretch()
        self.btn_reset = QPushButton(tr(keys.DEV_EDIT_RESET))
        self.btn_reset.setFixedWidth(64)
        self.btn_reset.clicked.connect(self.reset_edits)
        header_row.addWidget(self.btn_reset)
        g.addLayout(header_row, start, 0, 1, 2)

        self.object_name = QLineEdit()
        self._shrinkable(self.object_name)
        self.object_name.textChanged.connect(self.schedule_apply)
        g.addWidget(self._edit_label(keys.DEV_EDIT_OBJECT_NAME), start + 1, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(self.object_name, start + 1, 1)

        self.spin_x = QSpinBox()
        self.spin_y = QSpinBox()
        self.spin_w = QSpinBox()
        self.spin_h = QSpinBox()
        self.spin_x.setRange(-10000, 10000)
        self.spin_y.setRange(-10000, 10000)
        self.spin_w.setRange(0, 10000)
        self.spin_h.setRange(0, 10000)
        geo_row = QHBoxLayout()
        for spin in (self.spin_x, self.spin_y, self.spin_w, self.spin_h):
            self._shrinkable(spin)
            spin.valueChanged.connect(self.schedule_apply)
            geo_row.addWidget(spin)
        g.addWidget(self._edit_label(keys.DEV_EDIT_GEOMETRY), start + 2, 0, Qt.AlignmentFlag.AlignTop)
        g.addLayout(geo_row, start + 2, 1)

        self.visible_check = QCheckBox()
        self.visible_check.toggled.connect(self.schedule_apply)
        g.addWidget(self._edit_label(keys.DEV_EDIT_VISIBLE), start + 3, 0)
        g.addWidget(self.visible_check, start + 3, 1)

        self.enabled_check = QCheckBox()
        self.enabled_check.toggled.connect(self.schedule_apply)
        g.addWidget(self._edit_label(keys.DEV_EDIT_ENABLED), start + 4, 0)
        g.addWidget(self.enabled_check, start + 4, 1)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.valueChanged.connect(self.schedule_apply)
        self.opacity_value = QLabel()
        self._shrinkable_label(self.opacity_value)
        self.opacity_value.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-family: {FONT_FAMILY_MONO}; font-size: 10px;"
        )
        op_row = QHBoxLayout()
        op_row.addWidget(self.opacity_slider, 1)
        op_row.addWidget(self.opacity_value)
        g.addWidget(self._edit_label(keys.DEV_EDIT_OPACITY), start + 5, 0, Qt.AlignmentFlag.AlignTop)
        g.addLayout(op_row, start + 5, 1)

        self.text_label = self._edit_label(keys.DEV_EDIT_TEXT)
        self.text_edit = QLineEdit()
        self._shrinkable(self.text_edit)
        self.text_edit.textChanged.connect(self.schedule_apply)
        g.addWidget(self.text_label, start + 6, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(self.text_edit, start + 6, 1)
        self.text_label.setVisible(False)
        self.text_edit.setVisible(False)

        self.color_label = self._edit_label(keys.DEV_EDIT_TEXT_COLOR)
        self.color_edit = QLineEdit()
        self.color_edit.setPlaceholderText("#ffffff")
        self.color_edit.setMinimumWidth(110)
        self.color_edit.textChanged.connect(self.schedule_apply)
        self.btn_color = QPushButton(tr(keys.DEV_EDIT_COLOR_PICK))
        self._shrinkable_label(self.btn_color)
        self.btn_color.clicked.connect(self.pick_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_edit)
        color_row.addWidget(self.btn_color)
        color_row.addStretch()
        g.addWidget(self.color_label, start + 7, 0, Qt.AlignmentFlag.AlignTop)
        g.addLayout(color_row, start + 7, 1)

        self.qss_label = self._edit_label(keys.DEV_EDIT_STYLESHEET)
        self.qss_edit = QPlainTextEdit()
        self._shrinkable(self.qss_edit)
        self.qss_edit.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 11px;"
        )
        self.qss_edit.setMinimumHeight(80)
        self.qss_edit.textChanged.connect(self.schedule_apply)
        g.addWidget(self.qss_label, start + 8, 0, Qt.AlignmentFlag.AlignTop)
        g.addWidget(self.qss_edit, start + 8, 1)

        self.detail_layout.setColumnStretch(1, 1)

    def _is_alive(self, widget):
        if not widget:
            return False
        if shiboken:
            return shiboken.isValid(widget)
        try:
            widget.parent()
            return True
        except Exception:
            return False

    def show_widget_info(self, widget):
        if not self._is_alive(widget):
            return
        self.current_widget = widget
        self.tree.select_widget(widget)

        values = [
            widget.metaObject().className(),
            widget.objectName() or "-",
            f"{widget.width()}x{widget.height()} @ {widget.x()},{widget.y()}",
            self._global_geometry(widget),
            tr(keys.DEV_PROP_BOOL_YES) if widget.isVisible() else tr(keys.DEV_PROP_BOOL_NO),
            tr(keys.DEV_PROP_BOOL_YES) if widget.isEnabled() else tr(keys.DEV_PROP_BOOL_NO),
            self._parent_chain(widget),
            str(len(widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly))),
        ]
        for value_label, text in zip(self._detail_values, values):
            value_label.setText(text)

        if widget is not self._editor_widget:
            self.load_editor(widget)

    def load_editor(self, widget):
        if not self._is_alive(widget):
            return
        self._syncing = True
        self._editor_widget = widget
        self._color_dirty = False

        self.object_name.setText(widget.objectName())
        self.spin_x.setValue(widget.x())
        self.spin_y.setValue(widget.y())
        self.spin_w.setValue(widget.width())
        self.spin_h.setValue(widget.height())
        self.visible_check.setChecked(widget.isVisible())
        self.enabled_check.setChecked(widget.isEnabled())

        effect = widget.graphicsEffect()
        opacity = effect.opacity() if isinstance(effect, QGraphicsOpacityEffect) else 1.0
        self.opacity_slider.setValue(int(round(opacity * 100)))
        self.opacity_value.setText(f"{self.opacity_slider.value()}%")

        text_prop = self._has_property(widget, "text")
        has_text = text_prop
        self.text_label.setVisible(has_text)
        self.text_edit.setVisible(has_text)
        if has_text:
            try:
                self.text_edit.setText(widget.text() or "")
            except Exception:
                self.text_edit.setText("")

        qss = widget.styleSheet()
        self.qss_edit.setPlainText(qss)
        color = self._color_from_qss(qss) or self._palette_text_color(widget)
        self.color_edit.setText(color)

        self._original_snapshot = {
            "stylesheet": qss,
            "object_name": widget.objectName(),
            "geometry": (widget.x(), widget.y(), widget.width(), widget.height()),
            "visible": widget.isVisible(),
            "enabled": widget.isEnabled(),
            "opacity": opacity,
            "text": widget.text() if has_text else None,
        }
        self._syncing = False

    def schedule_apply(self, *args):
        if self._syncing or self._editor_widget is None:
            return
        sender = self.sender()
        if sender is self.color_edit:
            self._color_dirty = True
        elif sender is self.qss_edit:
            self._color_dirty = False
        self.opacity_value.setText(f"{self.opacity_slider.value()}%")
        self.apply_timer.start()

    def apply_edits(self):
        widget = self._editor_widget
        if not self._is_alive(widget):
            return

        if self.object_name.text() != widget.objectName():
            widget.setObjectName(self.object_name.text())

        geometry = (self.spin_x.value(), self.spin_y.value(),
                    self.spin_w.value(), self.spin_h.value())
        if geometry != (widget.x(), widget.y(), widget.width(), widget.height()):
            widget.setGeometry(*geometry)

        if self.visible_check.isChecked() != widget.isVisible():
            widget.setVisible(self.visible_check.isChecked())
        if self.enabled_check.isChecked() != widget.isEnabled():
            widget.setEnabled(self.enabled_check.isChecked())
        self._set_opacity(widget, self.opacity_slider.value() / 100.0)

        if self._has_property(widget, "text"):
            try:
                if self.text_edit.text() != widget.text():
                    widget.setText(self.text_edit.text())
            except Exception:
                pass

        qss = self.qss_edit.toPlainText()
        if self._color_dirty:
            qss = self._set_color(qss, self.color_edit.text().strip())
            self.qss_edit.setPlainText(qss)
            self._color_dirty = False
        widget.setStyleSheet(qss)

        color = self._color_from_qss(qss)
        if color:
            self._syncing = True
            self.color_edit.setText(color)
            self._syncing = False

    def pick_color(self):
        current = QColor(self.color_edit.text().strip() or "#ffffff")
        chosen = QColorDialog.getColor(current, self, tr(keys.DEV_EDIT_TEXT_COLOR))
        if chosen.isValid():
            self.color_edit.setText(chosen.name().upper())

    def reset_edits(self):
        widget = self._editor_widget
        if not self._is_alive(widget) or self._original_snapshot is None:
            return
        snap = self._original_snapshot
        widget.setStyleSheet(snap["stylesheet"])
        self._set_opacity(widget, snap["opacity"])
        if snap["text"] is not None:
            try:
                widget.setText(snap["text"])
            except Exception:
                pass
        widget.setObjectName(snap["object_name"])
        widget.setGeometry(*snap["geometry"])
        widget.setVisible(snap["visible"])
        widget.setEnabled(snap["enabled"])
        self.load_editor(widget)

    def _set_opacity(self, widget, value):
        effect = widget.graphicsEffect()
        if value >= 1.0:
            if isinstance(effect, QGraphicsOpacityEffect):
                widget.setGraphicsEffect(None)
        else:
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)
            effect.setOpacity(value)

    def _set_color(self, qss, color):
        color = color.strip()
        if not self._valid_color(color):
            return qss
        match = _COLOR_RULE.search(qss)
        if match:
            return qss[:match.start(1)] + color + qss[match.end(1):]
        return f"color: {color}; " + qss

    def _color_from_qss(self, qss):
        match = _COLOR_RULE.search(qss)
        return match.group(1).strip() if match else None

    def _valid_color(self, color):
        if not color:
            return False
        try:
            return QColor(color).isValid()
        except Exception:
            return False

    def _has_property(self, widget, name):
        try:
            return widget.metaObject().indexOfProperty(name) != -1
        except Exception:
            return False

    def _palette_text_color(self, widget):
        try:
            return widget.palette().color(QPalette.ColorRole.WindowText).name().upper()
        except Exception:
            return "#FFFFFF"

    def _global_geometry(self, widget):
        try:
            top_left = widget.mapToGlobal(QPoint(0, 0))
            return f"{widget.width()}x{widget.height()} @ {top_left.x()},{top_left.y()}"
        except Exception:
            return "-"

    def _parent_chain(self, widget):
        chain = []
        w = widget.parentWidget()
        while w is not None and self._is_alive(w):
            chain.append(w.metaObject().className())
            w = w.parentWidget()
        return " > ".join(chain) if chain else "-"

    def set_highlight(self, enabled):
        context.dev_flags["highlight_mode"] = enabled
        overlay = getattr(context, "overlay", None)
        if overlay:
            overlay.set_highlight_mode(enabled)
            if not enabled:
                overlay.clear_highlight()

    def set_inspect(self, enabled):
        context.dev_flags["inspect_mode"] = enabled
        overlay = getattr(context, "overlay", None)
        if overlay:
            overlay.set_inspect_mode(enabled)
            if not enabled:
                overlay.clear_inspect_rect()

    def retranslate_ui(self):
        self.highlight_check.setText(tr(keys.DEV_UI_HIGHLIGHT))
        self.inspect_check.setText(tr(keys.DEV_UI_INSPECT))
        for header, key in zip(self._detail_headers, [
            keys.DEV_PROP_CLASS,
            keys.DEV_PROP_NAME,
            keys.DEV_PROP_GEOMETRY,
            keys.DEV_PROP_GLOBAL_GEOMETRY,
            keys.DEV_PROP_VISIBLE,
            keys.DEV_PROP_ENABLED,
            keys.DEV_PROP_PARENT_CHAIN,
            keys.DEV_PROP_CHILD_COUNT,
        ]):
            header.setText(tr(key))
        self._edit_title.setText(tr(keys.DEV_EDIT_TITLE))
        self.btn_reset.setText(tr(keys.DEV_EDIT_RESET))
        self.btn_color.setText(tr(keys.DEV_EDIT_COLOR_PICK))
        for lbl, key in self._edit_labels:
            lbl.setText(tr(key))
        if self.current_widget is not None:
            self.show_widget_info(self.current_widget)
        self.tree.retranslate_ui()