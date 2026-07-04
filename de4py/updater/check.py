# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import requests
from PySide6.QtCore import QThread, Signal

from de4py.config.config import settings
from de4py.utils.version import is_newer, parse_version


class UpdateCheckResult:
    __slots__ = ('update_available', 'local', 'remote', 'changelog')

    def __init__(self, update_available: bool, local: str, remote: str, changelog: list):
        self.update_available = update_available
        self.local = local
        self.remote = remote
        self.changelog = changelog


class UpdateCheckWorker(QThread):
    result = Signal(object)
    error = Signal(str)

    def run(self):
        try:
            r_ver = requests.get(settings.version_url, timeout=8)
            r_ver.raise_for_status()
            remote_version = r_ver.text.strip()

            local_version = settings.version
            available = is_newer(remote_version, local_version)

            new_entries = []
            if available:
                r_cl = requests.get(settings.changelog_url, timeout=8)
                r_cl.raise_for_status()
                all_entries = r_cl.json()
                local_tuple = parse_version(local_version)
                for entry in all_entries:
                    if parse_version(entry['version']) > local_tuple:
                        new_entries.append(entry)

            self.result.emit(UpdateCheckResult(available, local_version, remote_version, new_entries))

        except requests.ConnectionError:
            self.error.emit("No internet connection.")
        except requests.Timeout:
            self.error.emit("Update server timed out.")
        except Exception as e:
            self.error.emit(f"Update check failed: {e}")
