import logging
import platform
import sys
import traceback
from typing import Optional, Dict, Any

from api.client import De4pyApiClient, ApiError
from api.constants import (
    ENDPOINT_TELEMETRY_ERROR,
    TELEMETRY_SOURCES,
    TELEMETRY_SEVERITIES,
)
from config.config import __VERSION__

logger = logging.getLogger(__name__)


def _get_platform() -> str:
    """Detect the current platform."""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system


def _get_python_version() -> str:
    """Get Python version string (e.g., '3.11')."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


class TelemetryClient:
    """
    Client for reporting errors to the de4py telemetry system.
    
    This client is designed to be fail-safe - errors during telemetry
    reporting should never crash the application.
    
    Usage:
        client = TelemetryClient()
        client.report_error(
            source="core",
            source_name="deobfuscator",
            severity="error",
            error_type="ValueError",
            error_message="Invalid input format",
            traceback_str="...",
            context={"action": "parse_file", "file_hash": "abc123"}
        )
    """
    
    def __init__(self):
        """Initialize the telemetry client."""
        self._client = De4pyApiClient()
        self._platform = _get_platform()
        self._python_version = _get_python_version()
        self._app_version = __VERSION__.lstrip("Vv")
    
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
        """
        Report an error to the telemetry system.
        
        Args:
            source: Error source category ("core", "ui", "cli", "integration", "plugin")
            source_name: Specific component name (e.g., "pylingual", "deobfuscator")
            severity: Error severity ("info", "warning", "error", "critical")
            error_type: Exception type name (e.g., "ValueError", "ConnectionError")
            error_message: Human-readable error message
            traceback_str: Optional full traceback string
            context: Optional additional context (action, file_hash, extra data)
            
        Returns:
            True if report was sent successfully, False otherwise
        """
        # Validate inputs
        if source not in TELEMETRY_SOURCES:
            source = "core"
        if severity not in TELEMETRY_SEVERITIES:
            severity = "error"
        
        # Build payload
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
        """Close the telemetry client."""
        self._client.close()


# =============================================================================
# Convenience Function
# =============================================================================

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
    """
    Convenience function to report an error using a shared client instance.
    
    This is the recommended way to report errors from anywhere in the application.
    
    Args:
        source: Error source ("core", "ui", "cli", "integration", "plugin")
        source_name: Component name (e.g., "pylingual")
        severity: Severity level ("info", "warning", "error", "critical")
        error_type: Exception type (e.g., "ValueError")
        error_message: Error description
        traceback_str: Optional traceback
        context: Optional additional context
        
    Returns:
        True if sent successfully, False otherwise
        
    Example:
        from api import report_error
        
        try:
            do_something()
        except Exception as e:
            report_error(
                source="core",
                source_name="analyzer",
                severity="error",
                error_type=type(e).__name__,
                error_message=str(e),
                traceback_str=traceback.format_exc(),
            )
    """
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
