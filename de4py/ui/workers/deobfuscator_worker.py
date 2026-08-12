# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from typing import Optional

from PySide6.QtCore import QThread, Signal


class DeobfuscatorWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, file_path: str, parent=None, ai_overrides: Optional[dict] = None):
        super().__init__(parent)
        self._file_path = file_path
        self._ai_overrides = ai_overrides

    def run(self):
        from de4py.utils import sentry
        with sentry.transaction("Deobfuscator Task", "worker.deobfuscator"):
            try:
                from de4py.engines.legacy.detector import detect_obfuscator
                result = detect_obfuscator(self._file_path, self._ai_overrides)
                self.finished.emit(str(result))
            except Exception as e:
                self.error.emit(f"Error: {e}")
