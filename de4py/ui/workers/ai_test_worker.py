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


class AITestWorker(QThread):
    """Probe one provider's connection on a background thread.

    ``provider`` selects the provider to test; ``None`` uses the active one.
    """

    test_complete = Signal(str, bool, str, float)

    def __init__(self, provider: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._provider = provider

    def run(self):
        provider = self._provider
        try:
            from de4py.ai.client import AIClient, resolve_ai_config
            config = resolve_ai_config(provider=provider)
            if config is None or not config.base_url or not config.model:
                self.test_complete.emit(provider or "", False,
                                        "Not configured", 0.0)
                return
            status = AIClient(config).test_connection()
            self.test_complete.emit(provider or "", status.connected,
                                    status.message, status.latency_ms)
        except Exception as e:
            self.test_complete.emit(provider or "", False, str(e), 0.0)
