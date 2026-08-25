# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import time

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from de4py.api.client import ApiError, De4pyApiClient
from ..context import context
from ..event_bus import bus

class DevApiProxy(De4pyApiClient):
    def _delay(self):
        return max(0, int(context.dev_flags.get("api_delay", 0)))

    def _wait(self):
        delay = self._delay()
        if delay <= 0:
            return
        bus.log.emit("DEBUG", f"Simulated latency {delay}ms")
        if QCoreApplication.instance() is not None:
            loop = QEventLoop()
            QTimer.singleShot(delay, loop.quit)
            loop.exec()
        else:
            time.sleep(delay / 1000.0)

    def _force_fail(self, method, endpoint):
        bus.log.emit("ERROR", f"Forced failure: {method} {endpoint}")
        raise ApiError(0, f"DevTools: forced failure on {endpoint}", "DevTools")

    def _force_empty(self, method, endpoint):
        bus.log.emit("WARNING", f"Forced empty response: {method} {endpoint}")
        if method == "POST":
            return {"identifier": "", "cached": False}
        return {}

    def get(self, endpoint, params=None):
        bus.api_call.emit("GET", endpoint)
        if context.dev_flags.get("api_fail"):
            self._force_fail("GET", endpoint)
        if context.dev_flags.get("api_empty"):
            return self._force_empty("GET", endpoint)
        self._wait()
        start = time.monotonic()
        result = super().get(endpoint, params=params)
        bus.log.emit("INFO", f"GET {endpoint} -> OK ({self._elapsed(start)}ms)")
        return result

    def post(self, endpoint, json=None, data=None, files=None):
        bus.api_call.emit("POST", endpoint)
        if context.dev_flags.get("api_fail"):
            self._force_fail("POST", endpoint)
        if context.dev_flags.get("api_empty"):
            return self._force_empty("POST", endpoint)
        self._wait()
        start = time.monotonic()
        result = super().post(endpoint, json=json, data=data, files=files)
        bus.log.emit("INFO", f"POST {endpoint} -> OK ({self._elapsed(start)}ms)")
        return result

    @staticmethod
    def _elapsed(start):
        return int((time.monotonic() - start) * 1000)
