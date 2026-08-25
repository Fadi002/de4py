# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QThread, Signal

from de4py.ui.controllers import pyshell_controller


class BehaviorMonitorWorker(QThread):
    text_received = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        from de4py.utils import sentry
        with sentry.transaction("Behavior Monitor Task", "worker.behavior_monitor"):
            while self._running:
                data = pyshell_controller.read_analyzer_chunk()
                if data is None:
                    break
                if data:
                    self.text_received.emit(data)
                else:
                    self.msleep(60)

    def stop(self):
        self._running = False
