# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import weakref
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QMainWindow
    from de4py.api.client import De4pyApiClient

class AppContext:
    _instance = None
    
    app: Optional['QApplication'] = None
    main_window: Optional['QMainWindow'] = None
    api_client: Optional['De4pyApiClient'] = None
    navigation_manager: Optional[object] = None
    state_manager: Optional[object] = None
    notification_manager: Optional[object] = None
    devtools_panel: Optional[object] = None
    
    dev_flags = {
        "highlight_mode": False,
        "inspect_mode": False,
        "freeze_ui": False,
        "api_fail": False,
        "api_delay": 0,
        "api_empty": False,
        "anim_speed": 1.0,
        "show_fps": False
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppContext, cls).__new__(cls)
        return cls._instance

context = AppContext()
