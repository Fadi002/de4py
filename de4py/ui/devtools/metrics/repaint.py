# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import time
import weakref
from collections import defaultdict, deque

from PySide6.QtCore import QObject

_WINDOW_SECONDS = 5.0
_MAX_EVENTS = 10000

class RepaintTracker(QObject):
    def __init__(self):
        super().__init__()
        self._events = deque()
        self._refs = {}

    def track(self, widget):
        try:
            widget.metaObject()
        except RuntimeError:
            return
        now = time.monotonic()
        self._events.append((id(widget), now))
        self._refs[id(widget)] = weakref.ref(widget)
        if len(self._events) > _MAX_EVENTS:
            self._events = deque(list(self._events)[-_MAX_EVENTS:])

    def top(self, n):
        now = time.monotonic()
        while self._events and now - self._events[0][1] > _WINDOW_SECONDS:
            self._events.popleft()

        counts = defaultdict(int)
        for wid, _t in self._events:
            counts[wid] += 1

        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]
        result = []
        for wid, count in ranked:
            ref = self._refs.get(wid)
            widget = ref() if ref else None
            if widget is None:
                continue
            try:
                widget.metaObject()
            except RuntimeError:
                continue
            result.append((widget, count))
        return result

repaint_tracker = RepaintTracker()
