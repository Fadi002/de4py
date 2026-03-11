# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import requests
from de4py.config.config import settings
def check_update():
    logging.info("Checking for updates")
    if requests.get(settings.version_url, timeout=60).text != settings.version:
        return False
    else:
        return True

