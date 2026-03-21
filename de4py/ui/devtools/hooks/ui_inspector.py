# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QObject, QEvent, Qt, QPoint, QTimer
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QColor, QPen
from ..context import context
from ..event_bus import bus

class UIInspectorHook(QObject):
    def __init__(self):
        super().__init__()
        self._hovered_widget = None
        self._explicit_widget = None
        bus.inspect_widget.connect(self.set_explicit_highlight)

    def set_explicit_highlight(self, widget: QWidget):
        if not widget: return
        
        self._explicit_widget = widget
        try:
            widget.update()
            QTimer.singleShot(2000, self.clear_explicit_highlight)
        except:
            self._explicit_widget = None

    def clear_explicit_highlight(self):
        if self._explicit_widget:
            w = self._explicit_widget
            self._explicit_widget = None
            try: w.update()
            except: pass

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not isinstance(obj, QWidget):
            return False

        overlay = getattr(context, 'overlay', None)
        if not overlay: return False

        if context.devtools_panel:
            try:
                if obj == context.devtools_panel or obj.window() == context.devtools_panel:
                    return False
            except: pass

        if context.dev_flags.get("highlight_mode"):
            if event.type() == QEvent.Type.Enter:
                main_win = context.main_window
                if main_win:
                    g_pos = obj.mapToGlobal(QPoint(0, 0))
                    pos = main_win.mapFromGlobal(g_pos)
                    overlay.highlight_rect = (pos.x(), pos.y(), obj.width(), obj.height())
                    overlay.show_highlight = True
            elif event.type() == QEvent.Type.Leave:
                overlay.show_highlight = False
                overlay.highlight_rect = None

        if context.dev_flags.get("inspect_mode"):
            if event.type() == QEvent.Type.MouseButtonPress:
                main_win = context.main_window
                if main_win:
                    g_pos = obj.mapToGlobal(QPoint(0, 0))
                    pos = main_win.mapFromGlobal(g_pos)
                    overlay.inspect_rect = (pos.x(), pos.y(), obj.width(), obj.height())
                    overlay.show_inspector = True
                bus.inspect_widget.emit(obj)
                return True

        return False

    def paint_highlight(self, widget: QWidget):
        pass
