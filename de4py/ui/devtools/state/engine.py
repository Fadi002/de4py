# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from ..event_bus import bus

class StateEngine:
    def __init__(self):
        self._current_state = "NORMAL"
        self._latency_ms = 0
        self._is_offline = False

    def set_offline(self, enabled: bool):
        self._is_offline = enabled
        bus.state_changed.emit("offline", enabled)
        bus.log_message.emit("INFO", f"Network state: {'OFFLINE' if enabled else 'ONLINE'}")

    def set_latency(self, ms: int):
        self._latency_ms = ms
        bus.state_changed.emit("latency", ms)
        bus.log_message.emit("INFO", f"Simulated latency: {ms}ms")

    def trigger_error(self, code: str):
        bus.state_changed.emit("error_triggered", code)
        bus.log_message.emit("ERROR", f"Simulated error: {code}")

engine = StateEngine()
