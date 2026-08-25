# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""Regression test for a missing reentrancy guard on the main Deobfuscate
button. _on_test_ai already refused to start a second AITestWorker while one
was running (`if self._ai_test_worker and self._ai_test_worker.isRunning():
return`); _on_deobfuscate had no equivalent check, so clicking Deobfuscate
twice quickly (or the consent-accepted path re-invoking it while a run was
still in flight) started a second DeobfuscatorWorker, overwriting
self._worker while the first worker's finished/error signals stayed
connected and could still fire later against stale state."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeMainWindow(QWidget):
    """_on_deobfuscate reaches self.window().show_loading()/hide_loading() —
    those only exist on the real MainWindow, so give the screen a top-level
    parent that has them rather than dragging in the whole MainWindow."""

    def show_loading(self):
        pass

    def hide_loading(self):
        pass

    def show_notification(self, *args, **kwargs):
        pass


class _FakeWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._running = True

    def isRunning(self):
        return self._running

    def start(self):
        pass


def test_deobfuscate_reentrancy_guard_blocks_second_worker(qapp, monkeypatch, tmp_path):
    import de4py.ui.screens.deobfuscator_screen as mod

    monkeypatch.setattr(mod, "DeobfuscatorWorker", _FakeWorker)

    sample = tmp_path / "sample.py"
    sample.write_text("print(1)\n")

    main = _FakeMainWindow()
    screen = mod.DeobfuscatorScreen(main)
    main.show()
    qapp.processEvents()
    try:
        screen._file_path = str(sample)
        screen.ai_enable_checkbox.setChecked(False)

        screen._on_deobfuscate()
        first = screen._worker
        assert first is not None
        assert first.isRunning()

        screen._on_deobfuscate()
        assert screen._worker is first, "a second worker replaced the first while it was still running"

        first._running = False
        screen._on_deobfuscate()
        assert screen._worker is not first, "a new run must be allowed once the previous worker finished"
    finally:
        main.close()
