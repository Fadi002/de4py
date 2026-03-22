# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
from PySide6.QtCore import QPropertyAnimation
from ...devtools.context import context

class DevAnimationController:
    _original_set_duration = QPropertyAnimation.setDuration

    @staticmethod
    def inject():
        def patched_set_duration(self, duration: int):
            multi = context.dev_flags.get("anim_speed", 1.0)
            if multi <= 0: multi = 1.0
            # Higher multi = Faster animation (Lower duration)
            scaled_duration = int(duration / multi)
            DevAnimationController._original_set_duration(self, scaled_duration)
            
        QPropertyAnimation.setDuration = patched_set_duration
        logging.info("[DevTools] Animation Duration Hook injected.")

    @staticmethod
    def restore():
        QPropertyAnimation.setDuration = DevAnimationController._original_set_duration
