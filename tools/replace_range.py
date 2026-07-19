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
    dry_run: bool = False,
) -> dict:
    """
    Replace a contiguous line range with new content.

    No diff matching — the specified lines are replaced directly.
    All bytes outside the range are preserved exactly.

    IMPORTANT: line numbers shift after every write.  After a prior
    edit, always re-read (stat_file + read_range) to confirm current
    line numbers BEFORE calling replace_range again.  When in doubt,
    call with dry_run=True first to preview what would be touched.

    Args:
        path: Path to the .pwn/.inc file.
        startLine: 1-indexed, inclusive start.
        endLine: 1-indexed, inclusive end.
        new_content: The replacement text (may contain line breaks).
        expected_sha256: SHA-256 from stat_file or read_pawn_file.
        dry_run: If True, compute and return a preview WITHOUT writing
            anything to disk.  The response includes the exact lines
            that would be removed and preserved on either side.

    Returns:
        On success: { success, sha256, sizeBytes, encoding, lineEnding,
                       linesBeforeContext, linesAfterContext }
        On dry_run: { success, dryRun: true,
                       preview: { linesBefore, linesToBeReplaced,
                                  linesAfter, newContentPreview } }
    """
    logger.info(
        f"[replace_range] {path} L{startLine}-{endLine}"
        f"{' (dry_run)' if dry_run else ''}"
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

    # ── Compute line-based slices (1-indexed → 0-indexed conversion) ─
    # startLine is 1-indexed, so the first line to REPLACE is at
    # 0-indexed position (startLine - 1).
    #
    # Lines BEFORE the range:   lines[0 : startLine - 1]
    #   - Goes from index 0 up to (but NOT including) startLine - 1.
    #   - This keeps lines 1..(startLine-1) intact (1-indexed).
    #   - Example: startLine=2 → slice [0:1] keeps only line 1.
    #
    # Replaced lines:           lines[startLine - 1 : actual_end]
    #   - startLine=2, endLine=3 → indices [1:3] = lines 2,3.
    #
    # Lines AFTER the range:    lines[actual_end : ]
    #   - actual_end is 1-indexed end converted to 0-indexed exclusive.
    #   - Example: endLine=3 (actual_end=3) → slice [3:] = lines 4+.
    #
    lines_before = lines[:startLine - 1]
    lines_to_replace = lines[startLine - 1:actual_end]
    lines_after = lines[actual_end:]

    # ── Compute byte offsets ─────────────────────────────────────────
    # Use byte-level slicing for exact fidelity (handles CRLF 2-byte
    # separators precisely).  The line_start_bytes array gives the
    # byte position where each line starts in the original data.
    byte_pos = 0
    line_start_bytes: list[int] = []
    for line in lines:
        line_start_bytes.append(byte_pos)
        byte_pos += len(line.encode("cp1252")) + len(sep)

    # start_byte: byte position of line startLine (1-indexed).
    # startLine=1 → line_start_bytes[0]; startLine=5 → line_start_bytes[4].
    start_byte = line_start_bytes[startLine - 1]

    # end_byte: byte position of the first line AFTER the replaced range
    # (or EOF if replacing through the end).
    # actual_end is the 1-indexed end converted to 0-indexed "first-after"
    # index.  Example: endLine=3, actual_end=3 → line_start_bytes[3] gives
    # the byte where line 4 starts.
    if actual_end < total_lines:
        end_byte = line_start_bytes[actual_end]
    else:
        # Replacing through EOF — everything from start_byte onward.
        end_byte = len(data)

    # ── Normalize new_content line endings ───────────────────────────
    normalized = preserve_line_endings(new_content, line_ending)
    # Ensure the replacement block ends with a trailing newline if the
    # original file had one, using the shared helper for consistency
    # with write_pawn_file / apply_string_patch.
    normalized = ensure_trailing_newline(
        normalized, text, line_ending
    )

    # ── Build preview (computed before encoding, using line info) ────
    # linesBefore: last 3 lines of content immediately BEFORE the range.
    # linesToBeReplaced: the exact lines being removed, numbered.
    # linesAfter: first 3 lines of content immediately AFTER the range.
    preview_lines_before = (
        lines_before[-3:] if len(lines_before) >= 3 else lines_before[:]
    )
    preview_lines_replaced = [
        {"lineNumber": startLine + i, "content": line}
        for i, line in enumerate(lines_to_replace)
    ]
    preview_lines_after = (
        lines_after[:3] if len(lines_after) >= 3 else lines_after[:]
    )

    preview = {
        "linesBefore": preview_lines_before,
        "linesToBeReplaced": preview_lines_replaced,
        "linesAfter": preview_lines_after,
        "newContentPreview": normalized,
    }

    # ── Dry-run: return preview WITHOUT writing ──────────────────────
    if dry_run:
        logger.info(
            f"[replace_range] dry_run OK: would replace L{startLine}-{endLine}"
        )
        return success(
            dryRun=True,
            preview=preview,
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
    # data[:start_byte] = all bytes before line startLine (lines 1..startLine-1)
    # new_bytes          = encoded replacement content
    # data[end_byte:]    = all bytes from the line after endLine onward
    result = data[:start_byte] + new_bytes + data[end_byte:]

    # ── Context lines for the response (from ORIGINAL file) ──────────
    # linesBeforeContext: 1-2 lines immediately outside the range, BEFORE.
    ctx_before = lines_before[-2:] if len(lines_before) >= 2 else lines_before[:]
    # linesAfterContext: 1-2 lines immediately outside the range, AFTER.
    ctx_after = lines_after[:2] if len(lines_after) >= 2 else lines_after[:]

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
        linesBeforeContext=ctx_before,
        linesAfterContext=ctx_after,
        preview=preview,
    )
