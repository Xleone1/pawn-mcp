"""
read_range MCP tool.

Read a specific line range from a Pawn source file.
Line-based only — no byte offsets.  1-indexed, inclusive.
"""

import logging
import os

from encoding import detect_line_endings
from tools.errors import success, error, FILE_NOT_FOUND, INVALID_RANGE, INTERNAL_ERROR

logger = logging.getLogger(__name__)


def read_range(path: str, startLine: int, endLine: int) -> dict:
    """
    Read a contiguous range of lines from a Pawn file.

    Args:
        path: Path to the .pwn/.inc file.
        startLine: 1-indexed, inclusive starting line.
        endLine: 1-indexed, inclusive ending line.

    Returns:
        { success, content, startLine, endLine, encoding, lineEnding, sha256? }
    """
    logger.info(f"[read_range] Range: {path} L{startLine}-{endLine}")

    # ── Validate range ───────────────────────────────────────────────
    if startLine < 1 or endLine < 1:
        return error(
            INVALID_RANGE,
            f"Line numbers must be >= 1 (got startLine={startLine}, endLine={endLine})",
            startLine=startLine,
            endLine=endLine,
        )
    if startLine > endLine:
        return error(
            INVALID_RANGE,
            f"startLine ({startLine}) must be <= endLine ({endLine})",
            startLine=startLine,
            endLine=endLine,
        )

    # ── Read raw bytes ───────────────────────────────────────────────
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied: {path}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to read file: {e}")

    # ── Detect line endings (for proper splitting) ───────────────────
    line_ending = detect_line_endings(data)
    if line_ending == "CRLF":
        sep = b"\r\n"
    elif line_ending == "CR":
        sep = b"\r"
    else:
        sep = b"\n"

    # ── Split into raw lines ─────────────────────────────────────────
    # We split on the detected separator; Pawn files use consistent
    # line endings so this is safe.
    raw_lines = data.split(sep)

    total_lines = len(raw_lines)

    # Handle files ending with newline (split produces empty trailing element)
    if data.endswith(sep) and raw_lines and raw_lines[-1] == b"":
        raw_lines.pop()
        total_lines = len(raw_lines)

    if total_lines == 0:
        return error(
            INVALID_RANGE,
            f"File is empty (0 lines)",
            startLine=startLine,
            endLine=endLine,
        )

    # ── Clamp / validate against actual line count ───────────────────
    if startLine > total_lines:
        return error(
            INVALID_RANGE,
            f"startLine ({startLine}) exceeds file line count ({total_lines})",
            startLine=startLine,
            endLine=endLine,
            totalLines=total_lines,
        )

    actual_end = min(endLine, total_lines)

    # ── Extract lines ────────────────────────────────────────────────
    selected = raw_lines[startLine - 1 : actual_end]

    # Decode each line individually as CP1252
    try:
        decoded_lines = [line.decode("cp1252") for line in selected]
    except UnicodeDecodeError as e:
        return error(
            "ENCODING_ERROR",
            f"Failed to decode line range as Windows-1252: {e}",
        )

    # Re-join with the detected line ending (as characters)
    # decode the separator for joining
    sep_str = sep.decode("cp1252")
    content = sep_str.join(decoded_lines)
    # If the original ended with a newline and we're including the last line,
    # add trailing newline
    if actual_end == total_lines and data.endswith(sep):
        content += sep_str

    logger.info(
        f"[read_range] OK: {path} L{startLine}-{actual_end} "
        f"({len(selected)} lines)"
    )

    return success(
        content=content,
        startLine=startLine,
        endLine=actual_end,
        totalLines=total_lines,
        encoding="windows-1252",
        lineEnding=line_ending,
    )
