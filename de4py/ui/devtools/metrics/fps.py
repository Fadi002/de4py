# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QObject, QElapsedTimer, QTimer
from ..event_bus import bus

class FPSTracker(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QElapsedTimer()
        self.timer.start()
        self.frame_count = 0
        self.fps = 0
        
        self.report_timer = QTimer(self)
        self.report_timer.timeout.connect(self._report)
        self.report_timer.start(1000)

    def tick(self):
        self.frame_count += 1

    def _report(self):
        self.fps = self.frame_count
        self.frame_count = 0
        bus.metric_updated.emit("FPS", self.fps)

fps_tracker = FPSTracker()
