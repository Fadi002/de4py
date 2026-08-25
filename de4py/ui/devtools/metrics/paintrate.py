# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from collections import deque

from PySide6.QtCore import QObject, QTimer

from ..context import context

_SAMPLE_MAX = 30

class PaintRateTracker(QObject):
    def __init__(self):
        super().__init__()
        self._frame_count = 0
        self.rate = 0
        self.samples = deque(maxlen=_SAMPLE_MAX)

        self._report_timer = QTimer(self)
        self._report_timer.timeout.connect(self._report)
        self._report_timer.start(1000)

    def tick(self):
        self._frame_count += 1

    def _report(self):
        panel = getattr(context, "devtools_panel", None)
        if panel is None or not panel.isVisible():
            self._frame_count = 0
            self.rate = 0
            return
        self.rate = self._frame_count
        self.samples.append(self._frame_count)
        self._frame_count = 0

paint_rate = PaintRateTracker()
