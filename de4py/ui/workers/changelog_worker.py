"""
De4py Changelog Worker - Fetches changelog from remote URL in background
One task only, emits result signal, no direct UI updates
"""
import requests
from PySide6.QtCore import QThread, Signal

from de4py.config.config import settings


class ChangelogWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        try:
            url = settings.changelog_url
            response = requests.get(url, timeout=10)
            self.finished.emit(response.text)
        except Exception as e:
            self.error.emit(f"Failed to load changelog: {str(e)}")
