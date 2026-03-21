# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

"""
De4py Changelog Worker - Fetches changelog from remote URL in background
One task only, emits result signal, no direct UI updates
"""
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException
from PySide6.QtCore import QThread, Signal

from de4py.config.config import settings


class ChangelogWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        from de4py.utils import sentry
        with sentry.span("fetch.changelog"):
            try:
                url = settings.changelog_url
                response = requests.get(url, timeout=10)
                self.finished.emit(response.text)
            except ConnectionError:
                self.error.emit("No internet connection available.")
            except Timeout:
                self.error.emit("The server took too long to respond.")
            except RequestException as e:
                self.error.emit(f"Failed to load changelog: {str(e)}")
            except Exception as e:
                self.error.emit(f"An unexpected error occurred: {str(e)}")
