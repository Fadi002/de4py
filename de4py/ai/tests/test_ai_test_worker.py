# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer


def _run_worker(qapp, worker, timeout_ms=3000):
    result = {}
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(timeout_ms)

    def on_done(provider, ok, message, latency):
        result["provider"] = provider
        result["ok"] = ok
        result["message"] = message
        result["latency"] = latency
        timer.stop()
        loop.quit()

    worker.test_complete.connect(on_done)
    worker.start()
    loop.exec()
    if "ok" not in result:
        worker.terminate()
        raise AssertionError("worker did not finish in time")
    return result


class _FakeStatus:
    def __init__(self, connected, message, latency=0.0):
        self.connected = connected
        self.message = message
        self.latency_ms = latency


def test_ai_test_worker_success(monkeypatch):
    from de4py.ui.workers.ai_test_worker import AITestWorker
    from de4py.ai.client import AIConfig

    monkeypatch.setattr("de4py.ai.client.resolve_ai_config",
                        lambda provider=None: AIConfig(provider="openai", base_url="x",
                                                       api_key="k", model="m"))
    monkeypatch.setattr("de4py.ai.client.AIClient.test_connection",
                        lambda self: _FakeStatus(True, "Connected", 42.0))

    app = QCoreApplication.instance() or QCoreApplication([])
    result = _run_worker(app, AITestWorker("openai"))
    assert result["provider"] == "openai"
    assert result["ok"] is True
    assert result["message"] == "Connected"
    assert result["latency"] == 42.0


def test_ai_test_worker_unavailable(monkeypatch):
    from de4py.ui.workers.ai_test_worker import AITestWorker
    from de4py.ai.client import AIConfig

    monkeypatch.setattr("de4py.ai.client.resolve_ai_config",
                        lambda provider=None: AIConfig(provider="gemini", base_url="",
                                                       api_key="", model=""))
    app = QCoreApplication.instance() or QCoreApplication([])
    result = _run_worker(app, AITestWorker("gemini"))
    assert result["ok"] is False
    assert result["provider"] == "gemini"


def test_ai_test_worker_exception(monkeypatch):
    from de4py.ui.workers.ai_test_worker import AITestWorker

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr("de4py.ai.client.resolve_ai_config", boom)
    app = QCoreApplication.instance() or QCoreApplication([])
    result = _run_worker(app, AITestWorker())
    assert result["ok"] is False
    assert "boom" in result["message"]
