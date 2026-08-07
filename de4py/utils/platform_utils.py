# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import os
import sys

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
_BSD_SYSTEMS = ("freebsd", "openbsd", "netbsd", "dragonfly")
IS_BSD = sys.platform in _BSD_SYSTEMS
IS_UNIX = os.name == "posix"


def supports(feature: str) -> bool:
    if feature == "pyshell":
        return IS_WINDOWS
    return True
