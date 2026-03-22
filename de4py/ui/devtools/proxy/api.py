# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import time
import logging
from typing import Dict, Any, Optional
from de4py.api.client import De4pyApiClient
from de4py.ui.devtools.context import context

class DevApiProxy(De4pyApiClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ..event_bus import bus
        bus.log.emit("DEBUG", f"DevApiProxy initialized for {self.base_url}")

    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        return self._inject_behavior("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Dict[str, Any] = None, 
             data: Dict[str, Any] = None, files: Dict[str, Any] = None) -> Dict[str, Any]:
        return self._inject_behavior("POST", endpoint, json=json, data=data, files=files)

    def _inject_behavior(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        delay = context.dev_flags.get("api_delay", 0)
        if delay > 0:
            from ..event_bus import bus
            bus.log.emit("DEBUG", f"LATENCY ({delay}ms): {method} {endpoint}")
            time.sleep(delay / 1000.0)

        if context.dev_flags.get("api_fail"):
            from ..event_bus import bus
            bus.log.emit("ERROR", f"FORCED FAIL: {method} {endpoint}")
            raise Exception(f"DevTools: Forced API failure on {endpoint}")
        if context.dev_flags.get("api_empty"):
            from ..event_bus import bus
            bus.log.emit("WARNING", f"FORCED EMPTY: {method} {endpoint}")
            return {}
        from ..event_bus import bus
        bus.log.emit("INFO", f"API CALL: {method} {endpoint}")
        
        real_method = getattr(super(), method.lower())
        return real_method(endpoint, **kwargs)
