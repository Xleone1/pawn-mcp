"""
replace_symbol MCP tool.

Replace a symbol's body directly — no diff matching.
Uses the same heuristic symbol detection as read_symbol.
Preserves CP1252, line endings, and all bytes outside the symbol.
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


def replace_symbol(
    path: str,
    symbol: str,
    new_content: str,
    expected_sha256: str,
) -> dict:
    """
    Replace a symbol's definition body with new content.

    Locates the symbol using heuristic pattern matching, determines
    its line extent (brace-matched for functions/enums, continuation-
    aware for macros), and replaces only that region.

    No diff matching — the replacement is applied directly.

    Args:
        path: Path to the .pwn/.inc file.
        symbol: The symbol name to replace.
        new_content: The new definition (may include line breaks).
        expected_sha256: SHA-256 from stat_file or read_pawn_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    logger.info(f"[replace_symbol] {path} :: {symbol}")

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

    # ── Find symbol ──────────────────────────────────────────────────
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

    # ── Resolve symbol extent ────────────────────────────────────────
    start_line, end_line = resolve_symbol_extent(lines, cand_line, cand_kind)

    # ── Compute byte offsets ─────────────────────────────────────────
    byte_pos = 0
    line_start_bytes: list[int] = []
    for line in lines:
        line_start_bytes.append(byte_pos)
        byte_pos += len(line.encode("cp1252")) + len(sep)

    total_lines = len(lines)
    start_byte = line_start_bytes[start_line - 1]
    if end_line < total_lines:
        end_byte = line_start_bytes[end_line]
    else:
        end_byte = len(data)

    # ── Normalize new_content line endings ───────────────────────────
    normalized = preserve_line_endings(new_content, line_ending)

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

    # ── Atomic write ─────────────────────────────────────────────────
    try:
        atomic_write(path, result)
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied writing to: {path}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to write file: {e}")

    new_sha256 = hashlib.sha256(result).hexdigest()
    logger.info(
        f"[replace_symbol] OK: {symbol} L{start_line}-{end_line}, "
        f"{len(result)} bytes, sha256={new_sha256[:16]}..."
    )

    return success(
        sha256=new_sha256,
        sizeBytes=len(result),
        encoding="windows-1252",
        lineEnding=line_ending,
    )
