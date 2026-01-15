import logging
import traceback
from PySide6.QtCore import QThread, Signal

from de4py.api.pylingual import PyLingualClient, FileTooLargeError, DecompileResult
from de4py.api.client import ApiError
from de4py.api import report_error

logger = logging.getLogger(__name__)


class PyLingualWorker(QThread):
    """
    Background worker for PyLingual decompilation.
    
    Signals:
        progress(stage, percentage, message): Emitted during decompilation progress
        finished(source_code): Emitted when decompilation completes successfully
        error(message): Emitted when an error occurs
        cached(): Emitted when result was retrieved from cache
    
    Usage:
        worker = PyLingualWorker("/path/to/file.pyc")
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()
    """
    
    # Signals
    progress = Signal(str, float, str)  # stage, percentage, message
    finished = Signal(str)              # source_code
    error = Signal(str)                 # error_message
    cached = Signal()                   # result was cached
    
    def __init__(self, file_path: str, parent=None):
        """
        Initialize the PyLingual worker.
        
        Args:
            file_path: Path to the .pyc file to decompile
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._file_path = file_path
        self._client = None
        self._is_cancelled = False
    
    def cancel(self):
        """Request cancellation of the worker."""
        self._is_cancelled = True
    
    def _progress_callback(self, stage: str, percentage: float, message: str):
        """Internal callback to emit progress signal."""
        if not self._is_cancelled:
            self.progress.emit(stage, percentage, message)
    
    def run(self):
        """Execute the decompilation workflow in background thread."""
        try:
            self._client = PyLingualClient()
            
            # Step 1: Upload file
            self._progress_callback("uploading", 0.0, "Uploading file to PyLingual...")
            
            try:
                upload_result = self._client.upload_file(self._file_path)
            except FileTooLargeError as e:
                self.error.emit(str(e))
                self._report_telemetry(e, "upload")
                return
            except FileNotFoundError as e:
                self.error.emit(f"File not found: {self._file_path}")
                return
            
            if self._is_cancelled:
                return
            
            # Check if cached
            if upload_result.cached:
                self.cached.emit()
                self._progress_callback("cached", 100.0, "Result retrieved from cache")
            
            identifier = upload_result.identifier
            
            # Step 2: Poll for progress (skip if cached result)
            if not upload_result.cached:
                while not self._is_cancelled:
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
                    
                    # Wait before next poll
                    self.msleep(int(self._client.poll_interval * 1000))
            
            if self._is_cancelled:
                return
            
            # Step 3: Get result
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
            error_msg = f"{e.message}"
            if e.action:
                error_msg += f" ({e.action})"
            self.error.emit(error_msg)
            self._report_telemetry(e, "api")
        
        except Exception as e:
            logger.exception("Unexpected error in PyLingual worker")
            self.error.emit(f"Unexpected error: {str(e)}")
            self._report_telemetry(e, "unexpected")
        
        finally:
            if self._client:
                self._client.close()
    
    def _report_telemetry(self, exception: Exception, action: str):
        """Report error to telemetry system."""
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
            # Telemetry failure should never crash the worker
            logger.debug("Failed to send telemetry report")
