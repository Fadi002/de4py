# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import QMessageBox

from de4py.lang import tr
from de4py.lang.keys import PYARMOR_BOX_TITLE, PYARMOR_BOX_TEXT, PYARMOR_BTN_STATIC, PYARMOR_BTN_DYNAMIC


class _PyArmorModeBridge(QObject):
    def ask(self, result_holder: list) -> None:
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr(PYARMOR_BOX_TITLE))
        box.setText(tr(PYARMOR_BOX_TEXT))
        static_btn = box.addButton(tr(PYARMOR_BTN_STATIC), QMessageBox.ButtonRole.AcceptRole)
        dynamic_btn = box.addButton(tr(PYARMOR_BTN_DYNAMIC), QMessageBox.ButtonRole.DestructiveRole)
        box.setDefaultButton(static_btn)
        box.exec()
        result_holder[0] = "hooking" if box.clickedButton() is dynamic_btn else "static"


class DeobfuscatorWorker(QThread):
    finished = Signal(str)
    error = Signal(str)
    _pyarmor_mode_requested = Signal(list)

    def __init__(self, file_path: str, parent=None, ai_overrides: Optional[dict] = None,
                 engine_options: Optional[dict] = None):
        super().__init__(parent)
        self._file_path = file_path
        self._ai_overrides = ai_overrides
        self._engine_options = engine_options
        # Constructed here so it lives on the caller's (main) thread, not on
        # this QThread once run() starts -- QMessageBox is only safe to show
        # from the thread that owns it.
        self._pyarmor_bridge = _PyArmorModeBridge()
        self._pyarmor_mode_requested.connect(
            self._pyarmor_bridge.ask, Qt.ConnectionType.BlockingQueuedConnection
        )

    def _confirm_pyarmor_dynamic(self) -> str:
        result_holder = ["static"]
        if QThread.currentThread() is self._pyarmor_bridge.thread():
            # Same thread as the bridge (e.g. run() invoked directly, not via
            # start()) -- a blocking queued connection here would deadlock.
            self._pyarmor_bridge.ask(result_holder)
        else:
            self._pyarmor_mode_requested.emit(result_holder)
        return result_holder[0]

    def run(self):
        from de4py.utils import sentry
        with sentry.transaction("Deobfuscator Task", "worker.deobfuscator"):
            try:
                from de4py.engines.legacy.detector import detect_obfuscator
                result = detect_obfuscator(
                    self._file_path, self._ai_overrides,
                    self._confirm_pyarmor_dynamic,
                    engine_options=self._engine_options)
                self.finished.emit(str(result))
            except Exception as e:
                self.error.emit(f"Error: {e}")
