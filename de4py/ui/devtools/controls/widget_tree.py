# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                              QLabel, QHBoxLayout, QPushButton, QLineEdit, QCheckBox,
                              QSizePolicy)

from .elided import ElidedCheckBox

try:
    import shiboken6 as shiboken
except ImportError:
    try:
        import shiboken
    except ImportError:
        shiboken = None

from de4py.lang import tr, keys
from de4py.ui.constants import COLOR_ACCENT, COLOR_TEXT_DIM, qcolor_rgba
from ..context import context
from ..event_bus import bus

class WidgetTree(QWidget):
    def __init__(self):
        super().__init__()
        self._filter_text = ""
        self.setup_ui()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.populate_tree)
        self.refresh_timer.start()

    def _shrinkable_label(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Preferred)
        widget.setSizePolicy(policy)

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(6)

        header_row = QHBoxLayout()
        self.title_label = QLabel(tr(keys.DEV_TREE_TITLE))
        self._shrinkable_label(self.title_label)
        header_row.addWidget(self.title_label)
        header_row.addStretch()
        self.btn_refresh = QPushButton(tr(keys.DEV_TREE_REFRESH))
        self.btn_refresh.setFixedWidth(64)
        self.btn_refresh.clicked.connect(self.populate_tree)
        header_row.addWidget(self.btn_refresh)
        self.layout.addLayout(header_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText(tr(keys.DEV_TREE_SEARCH))
        self._shrinkable(self.search)
        self.search.textChanged.connect(self.filter_tree)
        self.layout.addWidget(self.search)

        self.tree = QTreeWidget()
        self._shrinkable(self.tree)
        self.tree.setHeaderLabels([
            tr(keys.DEV_TREE_HEADER_WIDGET),
            tr(keys.DEV_TREE_HEADER_NAME),
            tr(keys.DEV_TREE_HEADER_STATUS),
        ])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 90)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.tree, 1)

        self.auto_refresh_check = ElidedCheckBox(tr(keys.DEV_TREE_SYNC))
        self._shrinkable_label(self.auto_refresh_check)
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self.toggle_sync)
        self.layout.addWidget(self.auto_refresh_check)

    def _is_alive(self, widget):
        if not widget:
            return False
        if shiboken:
            return shiboken.isValid(widget)
        try:
            widget.parent()
            return True
        except (RuntimeError, AttributeError):
            return False

    def _shrinkable(self, widget):
        widget.setMinimumWidth(0)
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        widget.setSizePolicy(policy)

    def _devtools_internal(self, widget):
        panel = getattr(context, "devtools_panel", None)
        if panel is not None:
            try:
                if widget is panel or widget.window() is panel:
                    return True
            except RuntimeError:
                return True
        overlay = getattr(context, "overlay", None)
        if overlay is not None:
            try:
                if widget is overlay:
                    return True
            except RuntimeError:
                return True
        return False

    def toggle_sync(self, enabled):
        if enabled:
            self.refresh_timer.start()
        else:
            self.refresh_timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self.populate_tree()

    def populate_tree(self):
        if not self.isVisible() or not context.app:
            return

        expanded_ids = self._get_expanded_ids()
        selected_widget = None
        if self.tree.currentItem():
            selected_widget = self.tree.currentItem().data(0, Qt.ItemDataRole.UserRole)
            if not self._is_alive(selected_widget):
                selected_widget = None

        self.tree.clear()

        for win in context.app.topLevelWidgets():
            if self._is_alive(win) and win.isVisible() and not self._devtools_internal(win):
                self.add_widget_item(None, win)

        self._restore_expanded_ids(expanded_ids)
        if selected_widget is not None and self._is_alive(selected_widget):
            self._select_widget_item(selected_widget)
        if self._filter_text:
            self.filter_tree(self._filter_text)

    def _get_expanded_ids(self):
        expanded = set()

        def _collect(item):
            if item.isExpanded():
                w = item.data(0, Qt.ItemDataRole.UserRole)
                if self._is_alive(w):
                    expanded.add(id(w))
            for i in range(item.childCount()):
                _collect(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            _collect(self.tree.topLevelItem(i))
        return expanded

    def _restore_expanded_ids(self, ids):
        def _apply(item):
            w = item.data(0, Qt.ItemDataRole.UserRole)
            if self._is_alive(w) and id(w) in ids:
                item.setExpanded(True)
            for i in range(item.childCount()):
                _apply(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            _apply(self.tree.topLevelItem(i))

    def _select_widget_item(self, widget):
        def _find(item):
            w = item.data(0, Qt.ItemDataRole.UserRole)
            if self._is_alive(w) and w is widget:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if _find(item.child(i)):
                    return True
            return False

        for i in range(self.tree.topLevelItemCount()):
            if _find(self.tree.topLevelItem(i)):
                break

    def select_widget(self, widget):
        if self._is_alive(widget):
            self._select_widget_item(widget)

    def add_widget_item(self, parent_item, widget):
        if not self._is_alive(widget):
            return

        item = QTreeWidgetItem(parent_item or self.tree)
        item.setText(0, widget.metaObject().className())
        item.setText(1, widget.objectName() or "-")

        is_visible = widget.isVisible()
        item.setText(2, tr(keys.DEV_TREE_STATUS_VISIBLE) if is_visible
                     else tr(keys.DEV_TREE_STATUS_HIDDEN))

        if not is_visible:
            item.setForeground(0, qcolor_rgba(COLOR_TEXT_DIM))
            item.setForeground(2, QColor("#8a8a8a"))
        else:
            item.setForeground(2, qcolor_rgba(COLOR_ACCENT))

        item.setData(0, Qt.ItemDataRole.UserRole, widget)

        for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if self._is_alive(child) and not self._devtools_internal(child):
                self.add_widget_item(item, child)

    def on_item_clicked(self, item, column):
        widget = item.data(0, Qt.ItemDataRole.UserRole)
        if self._is_alive(widget):
            bus.inspect_widget.emit(widget)

    def filter_tree(self, text):
        self._filter_text = text
        try:
            pattern = re.compile(re.escape(text), re.IGNORECASE)
        except re.error:
            pattern = None

        if pattern is None or not text:
            self._set_subtree_hidden(self.tree.invisibleRootItem(), False)
            return

        self._apply_filter(self.tree.invisibleRootItem(), pattern)

    def _set_subtree_hidden(self, parent, hidden):
        for i in range(parent.childCount()):
            child = parent.child(i)
            child.setHidden(hidden)
            self._set_subtree_hidden(child, hidden)

    def _apply_filter(self, parent, pattern):
        shown = False
        for i in range(parent.childCount()):
            child = parent.child(i)
            match = bool(pattern.search(child.text(0)) or pattern.search(child.text(1)))
            child_shown = self._apply_filter(child, pattern)
            child.setHidden(not (match or child_shown))
            if not child.isHidden():
                shown = True
        return shown

    def retranslate_ui(self):
        self.tree.setHeaderLabels([
            tr(keys.DEV_TREE_HEADER_WIDGET),
            tr(keys.DEV_TREE_HEADER_NAME),
            tr(keys.DEV_TREE_HEADER_STATUS),
        ])
        self.title_label.setText(tr(keys.DEV_TREE_TITLE))
        self.btn_refresh.setText(tr(keys.DEV_TREE_REFRESH))
        self.search.setPlaceholderText(tr(keys.DEV_TREE_SEARCH))
        self.auto_refresh_check.setText(tr(keys.DEV_TREE_SYNC))
        self.populate_tree()
