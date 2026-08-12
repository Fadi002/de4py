# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional, Callable

from de4py.api.client import De4pyApiClient
from de4py.api.constants import (
    ENDPOINT_PYLINGUAL_UPLOAD,
    ENDPOINT_PYLINGUAL_PROGRESS,
    ENDPOINT_PYLINGUAL_RESULT,
    STAGE_DONE,
    STAGE_ERROR,
    MAX_FILE_SIZE_BYTES,
)
from de4py.config.config import settings as _settings

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    identifier: str
    cached: bool


@dataclass
class ProgressResult:
    success: bool
    stage: str
    percentage: float
    message: str


@dataclass
class DecompileResult:
    success: bool
    source_code: Optional[str] = None
    error: Optional[str] = None


class FileTooLargeError(Exception):
    
    def __init__(self, file_size: int, max_size: int = MAX_FILE_SIZE_BYTES):
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(
            f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds "
            f"maximum allowed size ({max_size / 1024 / 1024:.2f} MB)"
        )


class PyLingualClient:
    
    def __init__(self):
        self._client = De4pyApiClient()
        self.poll_interval = _settings.poll_interval
    
    def _validate_file(self, file_path: str) -> int:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise FileTooLargeError(file_size)
        
        return file_size
    
    def upload_file(self, file_path: str) -> UploadResult:
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
        endpoint = ENDPOINT_PYLINGUAL_PROGRESS.format(identifier=identifier)
        response = self._client.get(endpoint)
        
        raw_pct = response.get("percentage")
        if raw_pct is None:
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
        if progress_callback:
            progress_callback("uploading", 0.0, "Uploading file...")
        
        upload = self.upload_file(file_path)
        
        if upload.cached:
            logger.info("Result is cached, skipping polling")
            if progress_callback:
                progress_callback(STAGE_DONE, 100.0, "Retrieved from cache")
        else:
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
        
        return self.get_result(upload.identifier)
    
    def close(self):
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
