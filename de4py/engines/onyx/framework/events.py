# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    category: str
    detail: str
    rule: str = ""
    confidence: float = 1.0


def render_explain(events) -> str:
    lines = []
    for event in events:
        head = f"[{event.category}]"
        if event.rule:
            head += f" ({event.rule})"
        if event.confidence < 1.0:
            head += f" conf={event.confidence:.2f}"
        lines.append(f"{head} {event.detail}")
    return "\n".join(lines)
