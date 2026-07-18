"""
replace_range MCP tool.

Replace a line range directly without diff matching.
Preserves CP1252 encoding, line endings, and all bytes outside the range.
"""

import hashlib
import logging

from encoding import (
    detect_line_endings,
    preserve_line_endings,
    ensure_trailing_newline,
    encode_cp1252,
    atomic_write,
    read_and_verify_sha256,
    validate_line_ending_consistency,
    EncodingError,
)
from tools.errors import (
    success, error,
    FILE_NOT_FOUND, INVALID_RANGE, SHA256_MISMATCH,
    LINE_ENDING_INCONSISTENT,
    INTERNAL_ERROR,
)

logger = logging.getLogger(__name__)


def replace_range(
    path: str,
    startLine: int,
    endLine: int,
    new_content: str,
    expected_sha256: str,
) -> dict:
    """
    Replace a contiguous line range with new content.

    No diff matching — the specified lines are replaced directly.
    All bytes outside the range are preserved exactly.

    Args:
        path: Path to the .pwn/.inc file.
        startLine: 1-indexed, inclusive start.
        endLine: 1-indexed, inclusive end.
        new_content: The replacement text (may contain line breaks).
        expected_sha256: SHA-256 from stat_file or read_pawn_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    logger.info(
        f"[replace_range] {path} L{startLine}-{endLine}"
    )

    # ── Validate range ───────────────────────────────────────────────
    if startLine < 1 or endLine < 1:
        return error(
            INVALID_RANGE,
            f"Line numbers must be >= 1 (got startLine={startLine}, endLine={endLine})",
        )
    if startLine > endLine:
        return error(
            INVALID_RANGE,
            f"startLine ({startLine}) must be <= endLine ({endLine})",
        )

    # ── Read and verify SHA-256 ──────────────────────────────────────
    try:
        data = read_and_verify_sha256(path, expected_sha256)
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except ValueError as e:
        return error(SHA256_MISMATCH, str(e))
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied: {path}")

    # ── Detect line endings ──────────────────────────────────────────
    line_ending = detect_line_endings(data)
    if line_ending == "CRLF":
        sep = b"\r\n"
        sep_str = "\r\n"
    elif line_ending == "CR":
        sep = b"\r"
        sep_str = "\r"
    else:
        sep = b"\n"
        sep_str = "\n"

    # ── Decode and split ─────────────────────────────────────────────
    text = data.decode("cp1252")
    lines = text.split(sep_str)
    original_ends_with_newline = text.endswith(sep_str)
    if original_ends_with_newline and lines and lines[-1] == "":
        lines.pop()

    total_lines = len(lines)

    if total_lines == 0:
        return error(INVALID_RANGE, "File is empty")

    if startLine > total_lines:
        return error(
            INVALID_RANGE,
            f"startLine ({startLine}) exceeds file line count ({total_lines})",
        )

    actual_end = min(endLine, total_lines)

    # ── Compute byte offsets ─────────────────────────────────────────
    # Find byte position of startLine and end of endLine
    byte_pos = 0
    line_start_bytes: list[int] = []
    for line in lines:
        line_start_bytes.append(byte_pos)
        byte_pos += len(line.encode("cp1252")) + len(sep)

    # Byte range to replace
    start_byte = line_start_bytes[startLine - 1]
    if actual_end < total_lines:
        end_byte = line_start_bytes[actual_end]
    else:
        # Replacing through EOF
        end_byte = len(data)

    # ── Normalize new_content line endings ───────────────────────────
    normalized = preserve_line_endings(new_content, line_ending)
    # Ensure the replacement block ends with a trailing newline if the
    # original file had one, using the shared helper for consistency
    # with write_pawn_file / apply_string_patch.
    normalized = ensure_trailing_newline(
        normalized, text, line_ending
    )

    # ── Encode new content ───────────────────────────────────────────
    try:
        new_bytes = encode_cp1252(normalized)
    except EncodingError as e:
        return error(
            "ENCODING_ERROR",
            str(e),
            encodingIssues=[
                {
                    "character": issue.character,
                    "codepoint": issue.codepoint,
                    "line": issue.line,
                    "column": issue.column,
                    "description": issue.description,
                }
                for issue in e.issues
            ],
        )

    # ── Build new file bytes ─────────────────────────────────────────
    result = data[:start_byte] + new_bytes + data[end_byte:]

    # ── Defense-in-depth: line-ending consistency check ──────────────
    # SHA-256 validates byte integrity but cannot detect mixed line
    # endings (e.g. bare \n inside a CRLF file), which silently
    # corrupt pawncc cross-unit compilation.
    le_issues = validate_line_ending_consistency(result, line_ending)
    if le_issues:
        logger.error(
            f"[replace_range] LINE_ENDING_INCONSISTENT: {len(le_issues)} issue(s)"
        )
        return error(
            LINE_ENDING_INCONSISTENT,
            f"Line-ending mismatch detected — {len(le_issues)} issue(s). "
            f"File has been left unchanged. Details: {'; '.join(le_issues[:5])}",
            issues=le_issues,
        )

    # ── Atomic write ─────────────────────────────────────────────────
    try:
        atomic_write(path, result)
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied writing to: {path}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to write file: {e}")

    new_sha256 = hashlib.sha256(result).hexdigest()
    logger.info(
        f"[replace_range] OK: {len(result)} bytes, sha256={new_sha256[:16]}..."
    )

    return success(
        sha256=new_sha256,
        sizeBytes=len(result),
        encoding="windows-1252",
        lineEnding=line_ending,
    )
