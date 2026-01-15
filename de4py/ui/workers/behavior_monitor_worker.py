"""
De4py Behavior Monitor Worker - Reads from analyzer pipe in background
One task only, emits text updates via signal, no direct UI updates
"""
from PySide6.QtCore import QThread, Signal

from de4py.ui.controllers import pyshell_controller


class BehaviorMonitorWorker(QThread):
    text_received = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        try:
            while self._running and not pyshell_controller.get_stop_threads():
                try:
                    message = pyshell_controller.read_from_analyzer_pipe()
                    if message:
                        self.text_received.emit(message)
                except Exception:
                    break
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._running = False
