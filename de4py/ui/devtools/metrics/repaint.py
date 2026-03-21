# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QObject, Signal
from ..event_bus import bus

class RepaintTracker(QObject):
    def __init__(self):
        super().__init__()
        self._counts = {}

    def track(self, widget):
        w_id = id(widget)
        self._counts[w_id] = self._counts.get(w_id, 0) + 1
        bus.metric_updated.emit("REPAINT", self._counts[w_id])
        
        if self._counts[w_id] > 100:
            bus.log_message.emit("WARNING", f"Widget {widget.objectName()} repainted {self._counts[w_id]} times!")

repaint_tracker = RepaintTracker()
