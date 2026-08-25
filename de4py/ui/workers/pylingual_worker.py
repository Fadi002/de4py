# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import traceback
from PySide6.QtCore import QThread, Signal

from de4py.api.pylingual import PyLingualClient, FileTooLargeError
from de4py.api.client import ApiError
from de4py.api import report_error

logger = logging.getLogger(__name__)


class PyLingualWorker(QThread):
    progress = Signal(str, float, str)
    finished = Signal(str)
    error = Signal(str)
    cached = Signal()

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._client = None
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _progress_callback(self, stage: str, percentage: float, message: str):
        if not self._is_cancelled:
            self.progress.emit(stage, percentage, message)

    def run(self):
        from de4py.utils import sentry
        with sentry.transaction("PyLingual Task", "worker.pylingual"):
            try:
                self._client = PyLingualClient()
                self._progress_callback("uploading", 0.0, "Uploading file to PyLingual...")

                try:
                    upload_result = self._client.upload_file(self._file_path)
                except FileTooLargeError as e:
                    self.error.emit(str(e))
                    self._report_telemetry(e, "upload")
                    return
                except FileNotFoundError:
                    self.error.emit(f"File not found: {self._file_path}")
                    return
                
                if self._is_cancelled:
                    return

                if upload_result.cached:
                    self.cached.emit()
                    self._progress_callback("cached", 100.0, "Result retrieved from cache")

                identifier = upload_result.identifier
                if not upload_result.cached:
                    MAX_POLL_RETRIES = 500
                    poll_count = 0
                    while not self._is_cancelled and poll_count < MAX_POLL_RETRIES:
                        poll_count += 1
                        progress = self._client.check_progress(identifier)

                        self._progress_callback(
                            progress.stage,
                            progress.percentage,
                            progress.message,
                        )

                        if progress.stage == "done":
                            break
                        
                        if progress.stage == "error" or not progress.success:
                            self.error.emit(progress.message or "Decompilation failed")
                            self._report_telemetry(
                                Exception(progress.message),
                                "decompile"
                            )
                            return

                        self.msleep(int(self._client.poll_interval * 1000))

                    if poll_count >= MAX_POLL_RETRIES and not self._is_cancelled:
                        self.error.emit("Decompilation timed out after maximum polling attempts")
                        self._report_telemetry(Exception("Polling timeout"), "poll_timeout")
                        return

                if self._is_cancelled:
                    return

                self._progress_callback("retrieving", 95.0, "Retrieving decompiled code...")
                result = self._client.get_result(identifier)

                if result.success and result.source_code:
                    self._progress_callback("done", 100.0, "Decompilation complete!")
                    self.finished.emit(result.source_code)
                else:
                    error_msg = result.error or "Failed to retrieve decompiled code"
                    self.error.emit(error_msg)
                    self._report_telemetry(Exception(error_msg), "result")

            except ApiError as e:
                error_msg = e.message
                if e.action:
                    error_msg += f" ({e.action})"
                self.error.emit(error_msg)
                self._report_telemetry(e, "api")

            except Exception as e:
                logger.exception("Unexpected error in PyLingual worker")
                self.error.emit(f"Unexpected error: {e}")
                self._report_telemetry(e, "unexpected")

            finally:
                if self._client:
                    self._client.close()

    def _report_telemetry(self, exception: Exception, action: str):
        try:
            report_error(
                source="integration",
                source_name="pylingual",
                severity="error",
                error_type=type(exception).__name__,
                error_message=str(exception),
                traceback_str=traceback.format_exc(),
                context={"action": action, "file": self._file_path},
            )
        except Exception:
            logger.debug("Failed to send telemetry report")
