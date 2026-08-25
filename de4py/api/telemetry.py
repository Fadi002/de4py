# de4py
# Copyright (c) 2026 Fadi002
#
# This file is part of the de4py project.
#
# Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
#
# See the LICENSE file for details.

import hashlib
import logging
import platform
import sys
import threading
from typing import Optional, Dict, Any

from de4py.api.client import De4pyApiClient, ApiError
from de4py.api.constants import (
    ENDPOINT_TELEMETRY_ERROR,
    TELEMETRY_SOURCES,
    TELEMETRY_SEVERITIES,
)
from de4py.config.config import settings

logger = logging.getLogger(__name__)


def _get_platform() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system


def _get_python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _get_architecture() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("aarch64", "arm64"):
        return "arm64"
    if machine.startswith("arm"):
        return "arm"
    return machine or "unknown"


def _machine_id() -> str:
    """Stable per-machine fingerprint, hashed so raw MAC is never sent."""
    import uuid
    raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class TelemetryClient:
    """Fail-safe: reporting failures are swallowed and never propagate to callers."""

    def __init__(self):
        self._client = De4pyApiClient()
        self._platform = _get_platform()
        self._python_version = _get_python_version()
        self._app_version = settings.version.lstrip("Vv")
    
    def report_error(
        self,
        source: str,
        source_name: str,
        severity: str,
        error_type: str,
        error_message: str,
        traceback_str: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not settings.telemetry:
            return False

        if source not in TELEMETRY_SOURCES:
            source = "core"
        if severity not in TELEMETRY_SEVERITIES:
            severity = "error"

        payload = {
            "source": source,
            "source_name": source_name,
            "severity": severity,
            "app_version": self._app_version,
            "platform": self._platform,
            "python": self._python_version,
            "context": context or {},
            "error": {
                "type": error_type,
                "message": error_message,
                "traceback": traceback_str,
            },
        }
        
        try:
            response = self._client.post(ENDPOINT_TELEMETRY_ERROR, json=payload)
            logger.debug(f"Telemetry report sent: {response}")
            return response.get("status") == "received"
        except ApiError as e:
            logger.warning(f"Telemetry report failed (API error): {e}")
            return False
        except Exception as e:
            logger.warning(f"Telemetry report failed (unexpected error): {e}")
            return False
    
    def close(self):
        self._client.close()


_default_client: Optional[TelemetryClient] = None


def report_error(
    source: str,
    source_name: str,
    severity: str,
    error_type: str,
    error_message: str,
    traceback_str: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    global _default_client

    if _default_client is None:
        _default_client = TelemetryClient()
    
    return _default_client.report_error(
        source=source,
        source_name=source_name,
        severity=severity,
        error_type=error_type,
        error_message=error_message,
        traceback_str=traceback_str,
        context=context,
    )


def send_ping() -> bool:
    if not settings.telemetry:
        return False

    api_key = settings.telemetry_api_key
    url = settings.telemetry_ping_url
    if not api_key or "xxxxx" in api_key or not url:
        logger.debug("Telemetry ping skipped: placeholder/incomplete credentials")
        return False

    try:
        import requests
        response = requests.post(
            url,
            json={
                "api_key": api_key,
                "instance_id": _machine_id(),
                "version": settings.version.lstrip("Vv"),
                "platform": _get_platform(),
                "architecture": _get_architecture(),
            },
            timeout=5,
        )
        ok = response.status_code == 200
        logger.debug(f"Telemetry ping {'sent' if ok else 'failed'}: {response.status_code}")
        return ok
    except Exception as e:
        logger.debug(f"Telemetry ping failed: {e}")
        return False


def start_ping_async() -> None:
    threading.Thread(target=send_ping, daemon=True).start()
