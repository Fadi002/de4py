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


def check_update() -> bool:
    """Returns True if running the latest version. Raises on network error."""
    logging.info("Checking for updates")
    response = requests.get(settings.version_url, timeout=10)
    response.raise_for_status()
    return response.text.strip() == settings.version.strip()
