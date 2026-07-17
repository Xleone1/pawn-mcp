"""
stat_file MCP tool.

Returns file metadata (SHA-256, size, line count, encoding, line endings)
— NEVER the file content.  Designed for large files where read_pawn_file
would be refused.
"""

import hashlib
import logging
import os

from encoding import detect_line_endings
from tools.errors import success, error, FILE_NOT_FOUND, INTERNAL_ERROR

logger = logging.getLogger(__name__)

# Chunk size for streaming reads: 64 KiB balances speed with memory
_STAT_CHUNK_SIZE = 64 * 1024


def stat_file(path: str) -> dict:
    """
    Return file metadata without returning any content.

    Args:
        path: Absolute or relative path to a .pwn/.inc file.

    Returns:
        { success, sha256, sizeBytes, lineCount, encoding, lineEnding }
    """
    logger.info(f"[stat_file] Stat: {path}")

    # ── Open and stream-read for SHA256 + line count ─────────────────
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied: {path}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to open file: {e}")

    try:
        sha = hashlib.sha256()
        line_ending_detected: str | None = None
        line_count = 0
        size_bytes = 0
        # We need the first ~few KB to reliably detect line endings,
        # but streaming is fine — detect_line_endings works on any slice.
        first_chunk: bytes | None = None

        while True:
            chunk = f.read(_STAT_CHUNK_SIZE)
            if not chunk:
                break
            sha.update(chunk)
            size_bytes += len(chunk)

            # Count LF characters (fast, works for all line-ending styles)
            line_count += chunk.count(b"\n")

            # Detect line endings from the first chunk that has them
            if line_ending_detected is None:
                if first_chunk is None:
                    first_chunk = chunk
                else:
                    # Concatenate just enough for detection
                    probe = first_chunk + chunk
                    if len(probe) > 16384:
                        probe = probe[:16384]
                    le = detect_line_endings(probe)
                    if le != "LF" or b"\r" in probe or b"\n" in probe:
                        # If we see actual CR or LF we take the result;
                        # for pure-LF files the default is LF anyway.
                        if b"\r" in probe or b"\n" in probe:
                            line_ending_detected = le
                    # Keep first_chunk for next iteration if still None
                    if line_ending_detected is None:
                        first_chunk = probe
    finally:
        f.close()

    # Final line-ending detection pass
    if first_chunk is not None and line_ending_detected is None:
        line_ending_detected = detect_line_endings(first_chunk)
    if line_ending_detected is None:
        line_ending_detected = "LF"

    # Files that don't end with newline still count as having one line
    # (the last line has no trailing newline; we counted all \n bytes
    # above, so add one for the final non-newline-terminated line).
    if size_bytes > 0:
        # If the file doesn't end with a newline, bump count.
        # We can't seek back, so we'll just assume most Pawn files end
        # with newline. For perfection we'd re-read the last byte, but
        # dropping that complexity — the count is informative anyway.
        pass
    # Actually: re-open briefly to check the last byte.
    try:
        with open(path, "rb") as tail_f:
            tail_f.seek(max(0, size_bytes - 1))
            last_byte = tail_f.read(1)
        if last_byte and last_byte != b"\n":
            line_count += 1
    except OSError:
        # Best effort — line count already approximate
        pass

    sha256_hex = sha.hexdigest()

    logger.info(
        f"[stat_file] OK: {size_bytes} bytes, {line_count} lines, "
        f"{line_ending_detected}, sha256={sha256_hex[:16]}..."
    )

    return success(
        sha256=sha256_hex,
        sizeBytes=size_bytes,
        lineCount=line_count,
        encoding="windows-1252",
        lineEnding=line_ending_detected,
    )
