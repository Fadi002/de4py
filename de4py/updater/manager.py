# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
from PySide6.QtCore import QObject, Signal, QThread

from de4py.updater.check import UpdateCheckWorker, UpdateCheckResult
from de4py.updater.download import DownloadWorker
from de4py.updater.verify import fetch_remote_checksums, verify_zip
from de4py.updater.apply import backup_current, apply_update, restart_app
from de4py.config.config import settings

logger = logging.getLogger(__name__)


class _VerifyWorker(QThread):
    result = Signal(str, bool)
    error = Signal(str)

    def __init__(self, zip_path, remote_version, parent=None):
        super().__init__(parent)
        self.zip_path = zip_path
        self.remote_version = remote_version

    def run(self):
        try:
            checksums = fetch_remote_checksums(self.remote_version)
            mismatches = verify_zip(self.zip_path, checksums)
            self.result.emit(self.zip_path, bool(mismatches))
        except Exception as e:
            logger.warning(f"Checksum verify failed: {e}")
            self.result.emit(self.zip_path, False)


class _ApplyWorker(QThread):
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, zip_path, parent=None):
        super().__init__(parent)
        self.zip_path = zip_path

    def run(self):
        try:
            backup_current()
            success = apply_update(self.zip_path)
            self.finished.emit(success)
        except Exception as e:
            self.error.emit(str(e))


class UpdateManager(QObject):
    update_available = Signal(object)
    check_complete = Signal(object)
    check_error = Signal(str)
    download_progress = Signal(int)
    update_ready = Signal(str)
    update_failed = Signal(str)
    update_applied = Signal()

    _instance = None

    @classmethod
    def get(cls) -> 'UpdateManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        super().__init__(parent)
        self._check_worker = None
        self._download_worker = None
        self._verify_worker = None
        self._apply_worker = None
        self._pending_zip = None
        self._pending_result = None

    def check_for_updates(self):
        if self._check_worker and self._check_worker.isRunning():
            return
        self._check_worker = UpdateCheckWorker()
        self._check_worker.result.connect(self._on_check_result)
        self._check_worker.error.connect(self._on_check_error)
        self._check_worker.start()

    def _on_check_error(self, msg: str):
        self.check_error.emit(msg)

    def _on_check_result(self, result: UpdateCheckResult):
        if result.update_available:
            self._pending_result = result
            self.update_available.emit(result)
            self.check_complete.emit(result)
            if settings.auto_update_install:
                self.start_download(result.remote)
        else:
            self.check_complete.emit(result)

    def start_download(self, version: str):
        if self._download_worker and self._download_worker.isRunning():
            return
        self._download_worker = DownloadWorker(version)
        self._download_worker.progress.connect(self.download_progress)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.error.connect(self.update_failed)
        self._download_worker.start()

    def _on_download_finished(self, zip_path: str):
        if self._verify_worker and self._verify_worker.isRunning():
            return
        self._verify_worker = _VerifyWorker(
            zip_path,
            self._pending_result.remote if self._pending_result else "",
        )
        self._verify_worker.result.connect(self._on_verify_result)
        self._verify_worker.error.connect(self._on_verify_error)
        self._verify_worker.start()

    def _on_verify_result(self, zip_path: str, has_mismatches: bool):
        if has_mismatches:
            self.update_failed.emit("Integrity check failed.")
            return
        self._pending_zip = zip_path
        self.update_ready.emit(zip_path)

    def _on_verify_error(self, msg: str):
        logger.warning(msg)
        if self._pending_zip is None and self._pending_result:
            self._pending_zip = self._pending_result.remote
        self.update_ready.emit(self._pending_zip or "")

    def apply(self):
        if not self._pending_zip:
            self.update_failed.emit("No update zip staged.")
            return
        if self._apply_worker and self._apply_worker.isRunning():
            return
        self._apply_worker = _ApplyWorker(self._pending_zip)
        self._apply_worker.finished.connect(self._on_apply_finished)
        self._apply_worker.error.connect(lambda e: self.update_failed.emit(f"Apply error: {e}"))
        self._apply_worker.start()

    def _on_apply_finished(self, success: bool):
        if success:
            self.update_applied.emit()
            restart_app()
        else:
            self.update_failed.emit("Failed to apply update files.")
