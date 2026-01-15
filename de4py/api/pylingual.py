import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Tuple, Callable

from de4py.api.client import De4pyApiClient, ApiError
from de4py.api.constants import (
    ENDPOINT_PYLINGUAL_UPLOAD,
    ENDPOINT_PYLINGUAL_PROGRESS,
    ENDPOINT_PYLINGUAL_RESULT,
    STAGE_DONE,
    STAGE_ERROR,
    MAX_FILE_SIZE_BYTES,
)
from de4py.config.config import __POLL_INTERVAL__

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result of a PyLingual upload operation."""
    identifier: str
    cached: bool


@dataclass
class ProgressResult:
    """Result of a PyLingual progress check."""
    success: bool
    stage: str
    percentage: float
    message: str


@dataclass
class DecompileResult:
    """Result of a PyLingual decompilation."""
    success: bool
    source_code: Optional[str] = None
    error: Optional[str] = None


class FileTooLargeError(Exception):
    """Raised when a file exceeds the maximum upload size."""
    
    def __init__(self, file_size: int, max_size: int = MAX_FILE_SIZE_BYTES):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(
            f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds "
            f"maximum allowed size ({max_size / 1024 / 1024:.2f} MB)"
        )


class PyLingualClient:
    """
    Client for decompiling .pyc files using the PyLingual service.
    
    The decompilation workflow is:
    1. Upload the .pyc file
    2. Poll for progress until stage is "done" or "error"
    3. Retrieve the decompiled source code
    
    Usage:
        client = PyLingualClient()
        
        # Upload file
        upload = client.upload_file("path/to/file.pyc")
        print(f"Task ID: {upload.identifier}, Cached: {upload.cached}")
        
        # Poll for completion
        while True:
            progress = client.check_progress(upload.identifier)
            print(f"Stage: {progress.stage}, Progress: {progress.percentage}%")
            if progress.stage == "done":
                break
            time.sleep(2)
        
        # Get result
        result = client.get_result(upload.identifier)
        if result.success:
            print(result.source_code)
        else:
            print(f"Error: {result.error}")
    """
    
    def __init__(self):
        """Initialize the PyLingual client."""
        self._client = De4pyApiClient()
        self.poll_interval = __POLL_INTERVAL__
    
    def _validate_file(self, file_path: str) -> int:
        """
        Validate file exists and is within size limits.
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            FileTooLargeError: If file exceeds size limit
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(file_size)
        
        return file_size
    
    def upload_file(self, file_path: str) -> UploadResult:
        """
        Upload a .pyc file for decompilation.
        
        The server may return a cached result if the file has been
        processed before (within the 24-hour cache window).
        
        Args:
            file_path: Path to the .pyc file
            
        Returns:
            UploadResult with task identifier and cache status
            
        Raises:
            FileNotFoundError: If file doesn't exist
            FileTooLargeError: If file exceeds 10MB
            ApiError: For API-related errors
        """
        self._validate_file(file_path)
        
        filename = os.path.basename(file_path)
        logger.info(f"Uploading file: {filename}")
        
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "application/octet-stream")}
            response = self._client.post(ENDPOINT_PYLINGUAL_UPLOAD, files=files)
        
        result = UploadResult(
            identifier=response["identifier"],
            cached=response.get("cached", False),
        )
        
        logger.info(f"Upload complete: id={result.identifier}, cached={result.cached}")
        return result
    
    def check_progress(self, identifier: str) -> ProgressResult:
        """
        Check the progress of a decompilation task.
        
        Args:
            identifier: Task identifier from upload
            
        Returns:
            ProgressResult with current stage, percentage, and status message
            
        Raises:
            ApiError: For API-related errors
        """
        endpoint = ENDPOINT_PYLINGUAL_PROGRESS.format(identifier=identifier)
        response = self._client.get(endpoint)
        
        raw_pct = response.get("percentage")
        if raw_pct is None:
            # Check other possible keys
            raw_pct = response.get("progress", response.get("percent", 0.0))
        
        try:
            # Clean up string values if any (e.g. "45%")
            if isinstance(raw_pct, str):
                raw_pct = raw_pct.replace("%", "").strip()
            percentage = float(raw_pct)
        except (ValueError, TypeError):
            percentage = 0.0
            
        return ProgressResult(
            success=response.get("success", True),
            stage=response.get("stage", "unknown"),
            percentage=percentage,
            message=response.get("message", ""),
        )
    
    def get_result(self, identifier: str) -> DecompileResult:
        """
        Retrieve the decompiled source code.
        
        Should only be called after check_progress returns stage="done".
        
        Args:
            identifier: Task identifier from upload
            
        Returns:
            DecompileResult with source code or error message
            
        Raises:
            ApiError: For API-related errors
        """
        endpoint = ENDPOINT_PYLINGUAL_RESULT.format(identifier=identifier)
        response = self._client.get(endpoint)
        
        return DecompileResult(
            success=response.get("success", False),
            source_code=response.get("source_code"),
            error=response.get("error"),
        )
    
    def decompile(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[str, float, str], None]] = None,
    ) -> DecompileResult:
        """
        Convenience method to perform the full decompilation workflow.
        
        This method handles upload, polling, and result retrieval in one call.
        
        Args:
            file_path: Path to the .pyc file
            progress_callback: Optional callback(stage, percentage, message)
                               called during polling
            
        Returns:
            DecompileResult with source code or error
            
        Raises:
            FileNotFoundError: If file doesn't exist
            FileTooLargeError: If file exceeds 10MB
            ApiError: For API-related errors
        """
        # Step 1: Upload
        if progress_callback:
            progress_callback("uploading", 0.0, "Uploading file...")
        
        upload = self.upload_file(file_path)
        
        if upload.cached:
            logger.info("Result is cached, skipping polling")
            if progress_callback:
                progress_callback(STAGE_DONE, 100.0, "Retrieved from cache")
        else:
            # Step 2: Poll for completion
            while True:
                progress = self.check_progress(upload.identifier)
                
                if progress_callback:
                    progress_callback(
                        progress.stage,
                        progress.percentage,
                        progress.message,
                    )
                
                if progress.stage == STAGE_DONE:
                    break
                
                if progress.stage == STAGE_ERROR or not progress.success:
                    return DecompileResult(
                        success=False,
                        error=progress.message or "Decompilation failed",
                    )
                
                time.sleep(self.poll_interval)
        
        # Step 3: Get result
        return self.get_result(upload.identifier)
    
    def close(self):
        """Close the PyLingual client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
