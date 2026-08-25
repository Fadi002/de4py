# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QObject, QEvent, QPoint, QTimer
from PySide6.QtWidgets import QWidget

from ..context import context
from ..event_bus import bus
from ..metrics.paintrate import paint_rate
from ..metrics.repaint import repaint_tracker

_HOVER_TIMEOUT = 600

class UIInspectorHook(QObject):
    def __init__(self):
        super().__init__()
        self._hovered_widget = None
        self._explicit_widget = None
        bus.inspect_widget.connect(self.set_explicit_highlight)

    def _is_alive(self, widget):
        if not widget:
            return False
        try:
            widget.metaObject()
            return True
        except RuntimeError:
            return False

    def _panel_widget(self, obj):
        panel = getattr(context, "devtools_panel", None)
        if panel is None:
            return False
        try:
            return obj is panel or obj.window() is panel
        except RuntimeError:
            return False

    def _overlay(self):
        return getattr(context, "overlay", None)

    def _map_to_main(self, obj):
        main_win = getattr(context, "main_window", None)
        if main_win is None:
            return None
        try:
            g_pos = obj.mapToGlobal(QPoint(0, 0))
            return main_win.mapFromGlobal(g_pos)
        except RuntimeError:
            return None

    def set_explicit_highlight(self, widget):
        if not self._is_alive(widget):
            return
        self._explicit_widget = widget
        overlay = self._overlay()
        if overlay:
            pos = self._map_to_main(widget)
            if pos is not None:
                overlay.set_highlight((pos.x(), pos.y(), widget.width(), widget.height()))
                overlay.set_highlight_mode(True)
        QTimer.singleShot(_HOVER_TIMEOUT, self.clear_explicit_highlight)

    def clear_explicit_highlight(self):
        self._explicit_widget = None
        overlay = self._overlay()
        if overlay:
            overlay.clear_highlight()

    def eventFilter(self, obj, event):
        if not isinstance(obj, QWidget):
            return False

        is_panel_widget = self._panel_widget(obj)

        if event.type() == QEvent.Type.Paint:
            if not is_panel_widget:
                overlay = self._overlay()
                if overlay is not None and obj is overlay:
                    return False
                panel = getattr(context, "devtools_panel", None)
                if panel is not None and panel.isVisible():
                    paint_rate.tick()
                    repaint_tracker.track(obj)
                    if context.dev_flags.get("repaint_regions"):
                        if overlay:
                            pos = self._map_to_main(obj)
                            if pos is not None:
                                overlay.set_repaint_region(
                                    (pos.x(), pos.y(), obj.width(), obj.height()))
            return False

        if is_panel_widget:
            return False

        overlay = self._overlay()
        if overlay is None:
            return False

        if context.dev_flags.get("highlight_mode"):
            if event.type() == QEvent.Type.Enter:
                self._hovered_widget = obj
                pos = self._map_to_main(obj)
                if pos is not None:
                    overlay.set_highlight((pos.x(), pos.y(), obj.width(), obj.height()))
                    overlay.set_highlight_mode(True)
            elif event.type() == QEvent.Type.Leave:
                if obj is self._hovered_widget:
                    self._hovered_widget = None
                    if self._explicit_widget is None and not context.dev_flags.get("inspect_mode"):
                        overlay.clear_highlight()
                        overlay.set_highlight_mode(False)

        if context.dev_flags.get("inspect_mode"):
            if event.type() == QEvent.Type.MouseButtonPress:
                pos = self._map_to_main(obj)
                if pos is not None:
                    overlay.set_inspect_rect((pos.x(), pos.y(), obj.width(), obj.height()))
                    overlay.set_inspect_mode(True)
                bus.inspect_widget.emit(obj)
                return True

        return False
