"""
Windows-1252 (CP1252) encoding utilities for Pawn/Open.MP source files.

All Pawn source files (.pwn, .inc) must be read as Windows-1252,
written as Windows-1252, and must preserve existing line endings.
"""

import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EncodingIssue:
    """Represents a single encoding problem found during validation."""
    character: str
    codepoint: str          # e.g. "U+2014"
    line: int
    column: int
    description: str


@dataclass
class EncodingResult:
    """Result of encoding validation."""
    valid: bool
    encoding: str = "windows-1252"
    has_bom: bool = False
    line_ending: str = ""
    sha256: str = ""
    issues: list[EncodingIssue] = field(default_factory=list)
    size_bytes: int = 0


class EncodingError(Exception):
    """Raised when encoding to Windows-1252 fails."""

    def __init__(self, message: str, issues: Optional[list[EncodingIssue]] = None):
        super().__init__(message)
        self.issues = issues or []


def detect_line_endings(data: bytes) -> str:
    """
    Detect the line ending style used in the file.

    Returns one of: 'CRLF', 'LF', 'CR'
    Defaults to 'LF' if no line endings are found.
    """
    if b'\r\n' in data:
        return 'CRLF'
    if b'\r' in data:
        return 'CR'
    return 'LF'


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def decode_cp1252(data: bytes) -> str:
    """
    Decode raw bytes using Windows-1252.

    Uses strict mode — raises UnicodeDecodeError on invalid bytes.
    """
    return data.decode('cp1252')


def _compute_line_column(text: str, position: int) -> tuple[int, int]:
    """
    Compute a human-readable (1-based line, 1-based column) for a
    character at *position* inside *text*.

    Correctly handles both LF and CRLF line endings: in CRLF text the
    trailing ``\\r`` that precedes a ``\\n`` is considered part of the
    *previous* line (matching visual editor behaviour), so column
    numbers are not inflated.
    """
    prefix = text[:position]
    line = prefix.count('\n') + 1
    last_nl = prefix.rfind('\n')
    if last_nl == -1:
        col = position + 1
    else:
        col = position - last_nl
    return line, col


def _find_cp1252_encoding_issues(text: str) -> list[EncodingIssue]:
    """Find every character in *text* that cannot be encoded to CP1252."""
    issues: list[EncodingIssue] = []
    for i, char in enumerate(text):
        try:
            char.encode('cp1252')
        except UnicodeEncodeError:
            codepoint = f"U+{ord(char):04X}"
            line, col = _compute_line_column(text, i)
            issues.append(EncodingIssue(
                character=char,
                codepoint=codepoint,
                line=line,
                column=col,
                description=(
                    f"Cannot encode character {codepoint} "
                    f"({char!r}) at line {line}, column {col}"
                ),
            ))
    return issues


def encode_cp1252(text: str) -> bytes:
    """
    Encode text to Windows-1252 bytes.

    Raises EncodingError if any character cannot be represented in CP1252.
    Never uses replacement characters.

    The fast path (valid text) does a single encode; the slow path
    iterates only when an error is detected.
    """
    try:
        return text.encode('cp1252')
    except UnicodeEncodeError:
        # Build detailed per-character diagnostics
        issues = _find_cp1252_encoding_issues(text)
        details = "\n".join(issue.description for issue in issues)
        raise EncodingError(
            f"Cannot encode {len(issues)} character(s) to Windows-1252:\n{details}",
            issues=issues,
        )


def validate_line_ending_consistency(data: bytes, expected_ending: str) -> list[str]:
    """
    Verify that all line endings in *data* are consistent with
    *expected_ending*.  Returns a list of human-readable issue
    descriptions (empty = clean).

    Used as a defense-in-depth post-write sanity check: SHA-256
    validates byte integrity but cannot detect a file that mixes
    e.g. bare ``\\n`` inside an otherwise-CRLF file.  Such mixed
    files compile correctly as standalone units but break pawncc
    when used via ``#include`` from other compilation units.

    Args:
        data: Raw bytes of the file to check.
        expected_ending: One of ``'CRLF'``, ``'LF'``, ``'CR'``.

    Returns:
        A (possibly empty) list of issue description strings.
    """
    issues: list[str] = []
    if expected_ending == 'CRLF':
        # Every LF (0x0A) must be preceded by CR (0x0D)
        for i, byte in enumerate(data):
            if byte == 0x0A and (i == 0 or data[i - 1] != 0x0D):
                issues.append(
                    f"Bare LF (\\\\n without preceding \\\\r) at byte offset {i} "
                    f"in file expected to use CRLF line endings"
                )
    elif expected_ending == 'LF':
        # No CR (0x0D) allowed at all
        for i, byte in enumerate(data):
            if byte == 0x0D:
                issues.append(
                    f"CR (\\\\r) at byte offset {i} "
                    f"in file expected to use LF line endings"
                )
    elif expected_ending == 'CR':
        # No LF (0x0A) after any CR (0x0D)
        for i, byte in enumerate(data):
            if byte == 0x0D and i + 1 < len(data) and data[i + 1] == 0x0A:
                issues.append(
                    f"CRLF at byte offset {i} "
                    f"in file expected to use CR line endings"
                )
    return issues


def preserve_line_endings(text: str, target_ending: str) -> str:
    """
    Normalize all line endings in text to the target style.

    Args:
        text: The text to normalize.
        target_ending: One of 'CRLF', 'LF', 'CR'.
    """
    # First normalize everything to LF
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')

    if target_ending == 'CRLF':
        return normalized.replace('\n', '\r\n')
    elif target_ending == 'CR':
        return normalized.replace('\n', '\r')
    else:
        return normalized


def has_utf8_bom(data: bytes) -> bool:
    """Check if data starts with UTF-8 BOM (0xEF 0xBB 0xBF)."""
    return data[:3] == b'\xef\xbb\xbf'


# CP1252 valid single-byte ranges:
def ensure_trailing_newline(text: str, original_text: str, line_ending: str) -> str:
    """
    If *original_text* ended with a newline but *text* does not,
    append the appropriate line-ending sequence.

    This is a single, testable function that replaces the duplicated
    fragile logic previously scattered across write and patch tools.
    """
    # Check if the original had a trailing newline of any kind
    original_has_newline = original_text.endswith('\n') or original_text.endswith('\r')
    if not original_has_newline:
        return text
    if text.endswith('\n') or text.endswith('\r'):
        return text

    if line_ending == 'CRLF':
        return text + '\r\n'
    elif line_ending == 'CR':
        return text + '\r'
    else:
        return text + '\n'


def read_and_verify_sha256(path: str, expected_sha256: str) -> bytes:
    """
    Read a file as raw bytes, verify its SHA-256 matches *expected_sha256*.

    Returns the raw bytes on success.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if the SHA-256 does not match (externally modified).
    """
    with open(path, 'rb') as f:
        data = f.read()

    current_sha256 = hashlib.sha256(data).hexdigest()
    if current_sha256 != expected_sha256:
        raise ValueError(
            f'SHA256 mismatch: file has been modified externally.\n'
            f'  Expected: {expected_sha256}\n'
            f'  Actual:   {current_sha256}'
        )
    return data


def atomic_write(path: str, raw: bytes) -> None:
    """
    Write *raw* bytes atomically to *path*.

    Writes to a temporary file in the same directory, fsyncs, then
    atomically renames onto the target path.  This prevents:
    - partial writes (crash mid-write → original stays intact).
    - TOCTOU races where another process sees a half-written file.

    Raises OSError on I/O failure.
    """
    dirname = os.path.dirname(path) or '.'
    fd, tmpname = tempfile.mkstemp(dir=dirname, suffix='.tmp')
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmpname, path)
# 0x00-0x7F: ASCII
# 0xA0-0xFF: Latin-1 Supplement (valid CP1252)
# 0x80-0x9F: CP1252-specific characters (not all are assigned, but all bytes are valid in CP1252)
# All bytes 0x00-0xFF are valid CP1252 characters.
# The only way a byte can be invalid is if it's undecodable by the codec.

def validate_cp1252(data: bytes) -> EncodingResult:
    """
    Validate that a file is proper Windows-1252.

    Checks:
    - No UTF-8 BOM
    - All bytes decode cleanly as CP1252
    - Round-trip: decode -> encode produces identical bytes
    """
    sha256 = compute_sha256(data)
    line_ending = detect_line_endings(data)
    result = EncodingResult(
        valid=True,
        encoding="windows-1252",
        line_ending=line_ending,
        sha256=sha256,
        size_bytes=len(data),
    )

    # Check BOM
    if has_utf8_bom(data):
        result.has_bom = True
        result.valid = False
        result.issues.append(EncodingIssue(
            character="",
            codepoint="BOM",
            line=1,
            column=1,
            description="File contains UTF-8 BOM (EF BB BF) — must be pure CP1252"
        ))

    # Test decode
    try:
        decoded = data.decode('cp1252')
    except UnicodeDecodeError as e:
        result.valid = False
        result.issues.append(EncodingIssue(
            character="",
            codepoint=f"Byte 0x{data[e.start:e.end].hex().upper() if e.start is not None else '??'}",
            line=1,
            column=e.start + 1 if e.start is not None else 1,
            description=f"CP1252 decode error: {e.reason}"
        ))
        return result

    # Round-trip test
    reencoded = decoded.encode('cp1252')
    if reencoded != data:
        result.valid = False
        # Find first differing byte
        diff_pos = 0
        for i, (a, b) in enumerate(zip(data, reencoded)):
            if a != b:
                diff_pos = i
                break
        else:
            diff_pos = min(len(data), len(reencoded))

        result.issues.append(EncodingIssue(
            character="",
            codepoint="",
            line=1,
            column=diff_pos + 1,
            description=f"Round-trip failure at byte offset {diff_pos}: CP1252 decode→encode produced different bytes"
        ))

    return result


def read_pawn_file_raw(path: str) -> tuple[bytes, str, str, str]:
    """
    Read a Pawn source file, return raw bytes with metadata.

    Returns:
        (raw_bytes, sha256, line_ending, encoding)
    """
    with open(path, 'rb') as f:
        data = f.read()

    sha256 = compute_sha256(data)
    line_ending = detect_line_endings(data)

    return data, sha256, line_ending, 'windows-1252'


def write_pawn_file_raw(path: str, text: str, line_ending: str) -> bytes:
    """
    Encode text to CP1252 bytes and write to file.

    Preserves line endings.
    Returns the raw bytes written.
    """
    normalized = preserve_line_endings(text, line_ending)

    # Ensure trailing newline is preserved
    if text.endswith('\n') and not normalized.endswith('\n'):
        if line_ending == 'CRLF':
            normalized += '\r\n'
        elif line_ending == 'CR':
            normalized += '\r'
        else:
            normalized += '\n'

    raw = encode_cp1252(normalized)

    with open(path, 'wb') as f:
        f.write(raw)

    return raw
