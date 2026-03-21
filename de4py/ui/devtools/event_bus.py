# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from PySide6.QtCore import QObject, Signal

class DevEventBus(QObject):
    toggle_panel = Signal()
    toggle_highlight = Signal(bool)
    toggle_inspect = Signal(bool)
    
    api_mode_changed = Signal(str)
    api_delay_changed = Signal(int)
    anim_speed_changed = Signal(float)
    
    log = Signal(str, str)
    
    trigger_ui_stress = Signal()
    trigger_network_blackout = Signal()
    
    inspect_widget = Signal(object)

bus = DevEventBus()
