"""
De4py Analyzer Worker - Runs analyzer functions in background thread
One task only, emits result signal, no direct UI updates
"""
from PySide6.QtCore import QThread, Signal

from ui.controllers import analyzer_controller


class AnalyzerWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, command: str, file_path: str, parent=None):
        super().__init__(parent)
        self._command = command
        self._file_path = file_path

    def run(self):
        try:
            result = ""
            if self._command == "detect_packer":
                result = str(analyzer_controller.run_detect_packer(self._file_path))
            elif self._command == "unpack_exe":
                result = str(analyzer_controller.run_unpack_file(self._file_path))
            elif self._command == "sus_strings_lookup":
                result = analyzer_controller.run_sus_strings_lookup(self._file_path)
            elif self._command == "all_strings_lookup":
                result = analyzer_controller.run_all_strings_lookup(self._file_path)
            elif self._command == "get_file_hashs":
                result = analyzer_controller.run_get_file_hashs(self._file_path)
            
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(f"Error: {str(e)}")
