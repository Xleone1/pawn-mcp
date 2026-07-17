"""
read_pawn_file MCP tool.

Reads a Pawn source file (.pwn, .inc) with Windows-1252 encoding,
returning content with metadata including SHA256 and line ending info.

For files larger than PAWN_MCP_MAX_READ_SIZE_KB this tool REFUSES to
return content and instead instructs the client to use ranged /
symbol-based access.
"""

import hashlib
import logging
import os

from config import max_read_size_bytes, large_file_message
from encoding import detect_line_endings
from tools.errors import success, error, FILE_TOO_LARGE, FILE_NOT_FOUND, INTERNAL_ERROR

logger = logging.getLogger(__name__)


def read_pawn_file(path: str) -> dict:
    """
    Read a Pawn source file safely.

    Args:
        path: Absolute or relative path to the .pwn/.inc file.

    Returns:
        A success dictionary with content + metadata, or a structured error.
    """
    logger.info(f"[read_pawn_file] Reading: {path}")

    # ── Stat first to decide whether we accept the read ──────────────
    try:
        file_size = os.path.getsize(path)
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error(
            "PERMISSION_DENIED",
            f"Permission denied: {path}",
        )
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to stat file: {e}")

    # ── Reject large files ───────────────────────────────────────────
    max_size = max_read_size_bytes()
    if file_size > max_size:
        return error(
            FILE_TOO_LARGE,
            large_file_message(file_size),
            sizeBytes=file_size,
            maxAllowedBytes=max_size,
            suggestedTools=[
                "stat_file",
                "list_symbols",
                "read_symbol",
                "read_range",
            ],
        )

    # ── Read raw bytes ───────────────────────────────────────────────
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error(
            "PERMISSION_DENIED",
            f"Permission denied: {path}",
        )
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to read file: {e}")

    sha256 = hashlib.sha256(data).hexdigest()
    line_ending = detect_line_endings(data)

    try:
        content = data.decode("cp1252")
    except UnicodeDecodeError as e:
        return error(
            "ENCODING_ERROR",
            f"Failed to decode file as Windows-1252: {e}",
        )

    line_count = content.count("\n")
    if not content.endswith("\n") and content:
        line_count += 1

    logger.info(
        f"[read_pawn_file] OK: {len(data)} bytes, {line_ending}, "
        f"sha256={sha256[:16]}..."
    )

    return success(
        content=content,
        encoding="windows-1252",
        lineEnding=line_ending,
        sha256=sha256,
        sizeBytes=len(data),
        lineCount=line_count,
        hint=(
            "For targeted access, prefer list_symbols + read_symbol "
            "to minimize context usage."
        ),
    )

