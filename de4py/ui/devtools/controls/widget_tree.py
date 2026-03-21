# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                              QLabel, QHBoxLayout, QPushButton, QLineEdit, QCheckBox)
from PySide6.QtCore import Qt, QTimer
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

class WidgetTree(QWidget):
    """
    Live explorer of the application's widget hierarchy.
    """
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self.populate_tree)
        self.refresh_timer.start()

    def setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        header_row = QHBoxLayout()
        header_row.addWidget(QLabel(f"<b>{tr(keys.DEV_TREE_TITLE)}</b>"))
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedWidth(30)
        btn_refresh.clicked.connect(self.populate_tree)
        header_row.addWidget(btn_refresh)
        self.layout.addLayout(header_row)
        
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr(keys.DEV_TREE_SEARCH))
        self.search.textChanged.connect(self.filter_tree)
        self.layout.addWidget(self.search)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            tr(keys.DEV_TREE_HEADER_WIDGET), 
            tr(keys.DEV_TREE_HEADER_NAME), 
            tr(keys.DEV_TREE_HEADER_TYPE), 
            tr(keys.DEV_TREE_HEADER_STATUS)
        ])
        self.tree.setColumnWidth(0, 160)
        self.tree.setColumnWidth(1, 100)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                color: #c9d1d9;
                font-family: 'Consolas', monospace;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #161b22;
                color: #8b949e;
                border: none;
                border-bottom: 2px solid #007AFF;
                padding: 4px;
            }
            QTreeWidget::item:selected {
                background-color: rgba(0, 122, 255, 0.2);
                color: #007AFF;
                outline: 1px solid #007AFF;
            }
        """)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.layout.addWidget(self.tree)
        
        self.auto_refresh_check = QCheckBox(tr(keys.DEV_TREE_SYNC))
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self.toggle_sync)
        self.layout.addWidget(self.auto_refresh_check)
        
        self.populate_tree()

    def _is_alive(self, widget):
        """Safely check if a widget's C++ object still exists."""
        if not widget: return False
        if shiboken:
            return shiboken.isValid(widget)
        try:
            # Fallback check
            widget.parent()
            return True
        except (RuntimeError, AttributeError):
            return False

    def toggle_sync(self, enabled):
        if enabled: self.refresh_timer.start()
        else: self.refresh_timer.stop()

    def populate_tree(self):
        if not context.app: return
        
        # Save state: expanded paths and selection
        expanded_paths = self._get_expanded_paths()
        selected_widget = None
        if self.tree.currentItem():
            selected_widget = self.tree.currentItem().data(0, Qt.UserRole)
            if not self._is_alive(selected_widget):
                selected_widget = None

        self.tree.clear()
        
        main_windows = [w for w in context.app.topLevelWidgets() if self._is_alive(w) and w.isVisible()]
        if context.devtools_panel:
            main_windows = [w for w in main_windows if w != context.devtools_panel]
            
        for win in main_windows:
            self.add_widget_item(None, win)
            
        # Restore state
        self._restore_expanded_paths(expanded_paths)
        if selected_widget and self._is_alive(selected_widget):
            self._select_widget_item(selected_widget)

    def _get_expanded_paths(self):
        expanded = set()
        def _collect(item, path):
            current_path = f"{path}/{item.text(0)}[{item.text(1)}]"
            if item.isExpanded():
                expanded.add(current_path)
            for i in range(item.childCount()):
                _collect(item.child(i), current_path)
        
        for i in range(self.tree.topLevelItemCount()):
            _collect(self.tree.topLevelItem(i), "")
        return expanded

    def _restore_expanded_paths(self, paths):
        def _apply(item, path):
            current_path = f"{path}/{item.text(0)}[{item.text(1)}]"
            if current_path in paths:
                item.setExpanded(True)
            for i in range(item.childCount()):
                _apply(item.child(i), current_path)
        
        for i in range(self.tree.topLevelItemCount()):
            _apply(self.tree.topLevelItem(i), "")

    def _select_widget_item(self, widget):
        def _find(item):
            w = item.data(0, Qt.UserRole)
            if self._is_alive(w) and w == widget:
                self.tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if _find(item.child(i)): return True
            return False
        
        for i in range(self.tree.topLevelItemCount()):
            if _find(self.tree.topLevelItem(i)): break

    def add_widget_item(self, parent_item, widget):
        if not self._is_alive(widget): return
        
        item = QTreeWidgetItem(parent_item or self.tree)
        item.setText(0, widget.metaObject().className())
        item.setText(1, widget.objectName() or "-")
        item.setText(2, tr(keys.DEV_TREE_TYPE_WINDOW) if widget.isWindow() else tr(keys.DEV_TREE_TYPE_CHILD))
        
        is_visible = widget.isVisible()
        item.setText(3, tr(keys.DEV_TREE_STATUS_VISIBLE) if is_visible else tr(keys.DEV_TREE_STATUS_HIDDEN))
        
        if not is_visible:
            item.setForeground(0, QColor("#484f58"))
            item.setForeground(3, QColor("#f85149"))
        else:
            item.setForeground(3, QColor("#3fb950"))
            
        item.setData(0, Qt.UserRole, widget)
        
        from PySide6.QtWidgets import QWidget
        for child in widget.findChildren(QWidget, options=Qt.FindDirectChildrenOnly):
            if self._is_alive(child):
                self.add_widget_item(item, child)

    def on_item_clicked(self, item, column):
        widget = item.data(0, Qt.UserRole)
        if self._is_alive(widget):
            bus.inspect_widget.emit(widget)
            bus.log.emit("DEBUG", f"Selected: {widget.metaObject().className()}")

    def filter_tree(self, text):
        import re
        pattern = re.compile(text, re.IGNORECASE)
        def _filter(parent):
            shown = False
            for i in range(parent.childCount()):
                child = parent.child(i)
                match = pattern.search(child.text(0)) or pattern.search(child.text(1))
                child_shown = _filter(child)
                child.setHidden(not (match or child_shown))
                if not child.isHidden(): shown = True
            return shown
        _filter(self.tree.invisibleRootItem())
