# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import psutil
import os
from PySide6.QtCore import QTimer, QObject
from ..event_bus import bus

class ResourceTracker(QObject):
    def __init__(self):
        super().__init__()
        self.process = psutil.Process(os.getpid())
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)
        self.timer.start(2000)

    def _update(self):
        cpu_usage = self.process.cpu_percent()
        mem_info = self.process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        
        bus.metric_updated.emit("CPU", cpu_usage)
        bus.metric_updated.emit("MEMORY", mem_mb)

resource_tracker = ResourceTracker()
