"""
Structured error codes and response helpers.

Every tool MUST return responses using the helpers defined here so
that every response — success or failure — shares the same top-level
shape:  { "success": true|false, ... }
"""

from typing import Any

# ── Error codes ──────────────────────────────────────────────────────

FILE_NOT_FOUND      = "FILE_NOT_FOUND"
FILE_TOO_LARGE      = "FILE_TOO_LARGE"
PERMISSION_DENIED   = "PERMISSION_DENIED"
SHA256_MISMATCH     = "SHA256_MISMATCH"
ENCODING_ERROR      = "ENCODING_ERROR"
SYMBOL_NOT_FOUND    = "SYMBOL_NOT_FOUND"
AMBIGUOUS_SYMBOL    = "AMBIGUOUS_SYMBOL"
INVALID_RANGE       = "INVALID_RANGE"
PATCH_FAILED        = "PATCH_FAILED"
INVALID_REGEX       = "INVALID_REGEX"
INTERNAL_ERROR      = "INTERNAL_ERROR"


def success(**kwargs: Any) -> dict:
    """Build a success response dict."""
    return {"success": True, **kwargs}


def error(code: str, message: str, **kwargs: Any) -> dict:
    """Build a structured error response dict."""
    return {"success": False, "errorCode": code, "message": message, **kwargs}
