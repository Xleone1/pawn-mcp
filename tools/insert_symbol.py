"""
insert_symbol MCP tools.

insert_after_symbol — Insert content after a symbol's definition.
insert_before_symbol — Insert content before a symbol's definition.

Both use heuristics from _symbol_utils.  Preserves CP1252, line endings,
and all existing bytes.
"""

import hashlib
import logging

from encoding import (
    detect_line_endings,
    preserve_line_endings,
    encode_cp1252,
    atomic_write,
    read_and_verify_sha256,
    EncodingError,
)
from tools._symbol_utils import (
    find_all_matching,
    resolve_symbol_extent,
)
from tools.errors import (
    success, error,
    FILE_NOT_FOUND, SYMBOL_NOT_FOUND, AMBIGUOUS_SYMBOL,
    SHA256_MISMATCH, INTERNAL_ERROR,
)

logger = logging.getLogger(__name__)


# ── Shared helpers ───────────────────────────────────────────────────

def _find_insertion_point(
    data: bytes,
    lines: list[str],
    symbol: str,
    path: str,
    position: str,  # "after" or "before"
) -> dict | int:
    """Locate the insertion byte and return it, or an error dict."""
    candidates = find_all_matching(lines, symbol)

    if not candidates:
        return error(
            SYMBOL_NOT_FOUND,
            f"Symbol '{symbol}' not found in {path}",
            symbol=symbol,
        )

    if len(candidates) > 1:
        return error(
            AMBIGUOUS_SYMBOL,
            f"Multiple symbols named '{symbol}' found.",
            symbol=symbol,
            candidates=[
                {"line": ln, "kind": k} for ln, k, _ in candidates
            ],
        )

    cand_line, cand_kind, _cand_sig = candidates[0]
    start_line, end_line = resolve_symbol_extent(lines, cand_line, cand_kind)

    # Detect line separator from raw data
    if b"\r\n" in data:
        sep = b"\r\n"
    elif b"\r" in data:
        sep = b"\r"
    else:
        sep = b"\n"

    # Compute byte positions of line starts
    line_start_bytes: list[int] = []
    byte_pos = 0
    for line in lines:
        line_start_bytes.append(byte_pos)
        byte_pos += len(line.encode("cp1252")) + len(sep)

    total_lines = len(lines)

    if position == "after":
        target_line = end_line
        if target_line < total_lines:
            return line_start_bytes[target_line]
        else:
            return len(data)
    else:  # "before"
        return line_start_bytes[start_line - 1]


# ── Tools ────────────────────────────────────────────────────────────

def insert_after_symbol(
    path: str,
    symbol: str,
    content: str,
    expected_sha256: str,
) -> dict:
    """
    Insert content immediately after a symbol's definition.

    Useful for adding new callbacks, functions, or helpers.
    """
    logger.info(f"[insert_after_symbol] {path} after {symbol}")
    return _insert_at_position(path, symbol, content, expected_sha256, "after")


def insert_before_symbol(
    path: str,
    symbol: str,
    content: str,
    expected_sha256: str,
) -> dict:
    """
    Insert content immediately before a symbol's definition.
    """
    logger.info(f"[insert_before_symbol] {path} before {symbol}")
    return _insert_at_position(path, symbol, content, expected_sha256, "before")


def _insert_at_position(
    path: str,
    symbol: str,
    content: str,
    expected_sha256: str,
    position: str,
) -> dict:
    """Shared implementation for insert_after/before_symbol."""

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
        sep_str = "\r\n"
    elif line_ending == "CR":
        sep_str = "\r"
    else:
        sep_str = "\n"

    # ── Decode and split ─────────────────────────────────────────────
    text = data.decode("cp1252")
    lines = text.split(sep_str)
    if text.endswith(sep_str) and lines and lines[-1] == "":
        lines.pop()

    # ── Find insertion point ─────────────────────────────────────────
    result = _find_insertion_point(data, lines, symbol, path, position)
    if isinstance(result, dict):
        return result  # error dict
    insert_byte: int = result

    # ── Normalize content line endings ───────────────────────────────
    normalized = preserve_line_endings(sep_str + content, line_ending)

    # ── Encode ───────────────────────────────────────────────────────
    try:
        new_bytes = encode_cp1252(normalized)
    except EncodingError as e:
        return error("ENCODING_ERROR", str(e),
            encodingIssues=[{
                "character": i.character, "codepoint": i.codepoint,
                "line": i.line, "column": i.column, "description": i.description,
            } for i in e.issues])

    # ── Build and write ──────────────────────────────────────────────
    result_bytes = data[:insert_byte] + new_bytes + data[insert_byte:]
    try:
        atomic_write(path, result_bytes)
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied writing to: {path}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to write file: {e}")

    new_sha256 = hashlib.sha256(result_bytes).hexdigest()
    logger.info(f"[insert_{position}_symbol] OK: {len(result_bytes)} bytes")

    return success(
        sha256=new_sha256, sizeBytes=len(result_bytes),
        encoding="windows-1252", lineEnding=line_ending,
    )

