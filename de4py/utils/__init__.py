# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

from .tui import setup_logging, clear_console, fade_type, __BANNER__
from .pathgen import gen_path

# Legacy compatibility — UpdateManager is now in de4py.update_manager
def check_update():
    """Legacy wrapper. Use de4py.update_manager.UpdateManager instead."""
    from de4py.update_manager.updater import UpdateManager
    from de4py.config.config import settings
    mgr = UpdateManager(
        current_version=settings.version,
        channel=getattr(settings, 'update_channel', 'stable'),
        auto_update=getattr(settings, 'auto_update', True),
    )
    release = mgr.check()
    return release is None  # True = up to date (matches old behavior)