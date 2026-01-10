"""
De4py Deobfuscator Worker - Runs deobfuscation in background thread
One task only, emits result signal, no direct UI updates
"""
from PySide6.QtCore import QThread, Signal

from ui.controllers import deobfuscator_controller


class DeobfuscatorWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path

    def run(self):
        try:
            result = deobfuscator_controller.run_detect_obfuscator(self._file_path)
            self.finished.emit(str(result))
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
