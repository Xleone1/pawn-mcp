"""
pawn-mcp centralized configuration.

All tunable thresholds are read from environment variables with
sensible defaults.  Never hard-code a limit in a tool module.
"""

import os

# ── Read thresholds ─────────────────────────────────────────────────

_MAX_READ_SIZE_KB = int(os.environ.get("PAWN_MCP_MAX_READ_SIZE_KB", "500"))

# Make max search results configurable (used by upcoming tools)
_MAX_SEARCH_RESULTS = int(os.environ.get("PAWN_MCP_MAX_SEARCH_RESULTS", "50"))


def max_read_size_bytes() -> int:
    """Maximum file size (in bytes) that read_pawn_file will accept."""
    return _MAX_READ_SIZE_KB * 1024


def max_search_results() -> int:
    """Default cap on the number of results returned by search tools."""
    return _MAX_SEARCH_RESULTS


# Small helpers for composing human-readable messages

def _fmt_size(size_bytes: int) -> str:
    """Return a human-friendly size string (e.g. '2.3 MB')."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def large_file_message(size_bytes: int) -> str:
    """Standard message returned when a file exceeds the read threshold."""
    return (
        f"File is {_fmt_size(size_bytes)} (exceeds {_fmt_size(max_read_size_bytes())} limit). "
        "Use stat_file for metadata, list_symbols for structure, "
        "read_symbol for specific symbols, or read_range for line windows."
    )
