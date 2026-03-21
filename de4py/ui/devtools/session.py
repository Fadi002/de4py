# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import time
from PySide6.QtCore import QObject, QEvent
from .event_bus import bus

class SessionRecorder(QObject):
    def __init__(self):
        super().__init__()
        self._is_recording = False
        self._events = []
        self._start_time = 0

    def start_recording(self):
        self._is_recording = True
        self._events = []
        self._start_time = time.time()
        bus.log_message.emit("INFO", "Session recording started.")

    def stop_recording(self):
        self._is_recording = False
        bus.log_message.emit("INFO", f"Session recording stopped. Captured {len(self._events)} events.")
        return self._events

    def log_event(self, event_type, target, details=None):
        if not self._is_recording:
            return
            
        timestamp = time.time() - self._start_time
        entry = {
            "time": timestamp,
            "type": event_type,
            "target": str(target),
            "details": details or {}
        }
        self._events.append(entry)
        bus.log_message.emit("DEBUG", f"Recorded event: {event_type} on {target}")

recorder = SessionRecorder()
