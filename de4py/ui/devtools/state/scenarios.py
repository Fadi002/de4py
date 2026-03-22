# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

SCENARIOS = {
    "EMPTY": {
        "description": "Simulate no data across all views",
        "params": {"items": 0, "offline": False}
    },
    "LARGE_DATASET": {
        "description": "Load 50,000+ items to test scrolling performance",
        "params": {"items": 50000, "offline": False}
    },
    "OFFLINE": {
        "description": "Cut all network connections",
        "params": {"offline": True}
    },
    "SLOW_NETWORK": {
        "description": "High latency simulation (2-5s)",
        "params": {"latency_range": (2000, 5000)}
    },
    "API_ERROR": {
        "description": "Random 5xx errors from all requests",
        "params": {"error_rate": 1.0}
    }
}
