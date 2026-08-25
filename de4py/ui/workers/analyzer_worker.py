# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QThread, Signal

from de4py.engines.analyzers import (
    detect_packer, unpack_file, get_file_hashs,
    sus_strings_lookup, all_strings_lookup
)


COMMANDS = {
    "detect_packer": detect_packer,
    "unpack_exe": unpack_file,
    "sus_strings_lookup": sus_strings_lookup,
    "all_strings_lookup": all_strings_lookup,
    "get_file_hashs": get_file_hashs,
}

STR_RESULT_COMMANDS = ("detect_packer", "unpack_exe")


class AnalyzerWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, command: str, file_path: str, parent=None):
        super().__init__(parent)
        self._command = command
        self._file_path = file_path

    def run(self):
        from de4py.utils import sentry
        with sentry.transaction("Analyzer Task", "worker.analyzer"):
            try:
                func = COMMANDS.get(self._command)
                result = func(self._file_path) if func else ""
                if self._command in STR_RESULT_COMMANDS:
                    result = str(result)

                self.finished.emit(result)
            except Exception as e:
                self.error.emit(f"Error: {e}")
