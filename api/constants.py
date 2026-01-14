"""
De4py API Constants
Defines all API endpoints, rate limits, and error codes.
"""

# =============================================================================
# API Endpoints
# =============================================================================

# Telemetry
ENDPOINT_TELEMETRY_ERROR = "/api/telemetry/error"

# PyLingual Integration
ENDPOINT_PYLINGUAL_UPLOAD = "/api/integrations/pylingual/upload"
ENDPOINT_PYLINGUAL_PROGRESS = "/api/integrations/pylingual/progress/{identifier}"
ENDPOINT_PYLINGUAL_RESULT = "/api/integrations/pylingual/result/{identifier}"


# =============================================================================
# Rate Limits (requests per minute per IP)
# =============================================================================

RATE_LIMIT_TELEMETRY = 20
RATE_LIMIT_PYLINGUAL_UPLOAD = 3
RATE_LIMIT_PYLINGUAL_PROGRESS = 60
RATE_LIMIT_PYLINGUAL_RESULT = 60


# =============================================================================
# File Constraints
# =============================================================================

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


# =============================================================================
# PyLingual Task Stages
# =============================================================================

STAGE_WAITING = "waiting_for_decompiler"
STAGE_DECOMPILING = "decompiling"
STAGE_DONE = "done"
STAGE_ERROR = "error"


# =============================================================================
# Error Codes and Descriptions
# =============================================================================

ERROR_CODES = {
    413: {
        "name": "Payload Too Large",
        "meaning": "File exceeds 10MB limit",
        "action": "Check file size before upload",
    },
    429: {
        "name": "Too Many Requests",
        "meaning": "Rate limit hit for your IP",
        "action": "Wait 60s or use exponential backoff",
    },
    500: {
        "name": "Server Error",
        "meaning": "Unexpected backend crash",
        "action": "Contact maintainer; check server logs",
    },
    502: {
        "name": "Bad Gateway",
        "meaning": "PyLingual API error/timeout",
        "action": "Report via Telemetry, retry later",
    },
}


# =============================================================================
# Telemetry Sources and Severities
# =============================================================================

TELEMETRY_SOURCES = ["core", "ui", "cli", "integration", "plugin"]
TELEMETRY_SEVERITIES = ["info", "warning", "error", "critical"]
TELEMETRY_PLATFORMS = ["windows", "linux", "macos"]
