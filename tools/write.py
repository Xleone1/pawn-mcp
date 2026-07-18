"""
write_pawn_file MCP tool.

Writes content to a Pawn source file with Windows-1252 encoding.
Uses an atomic write (temp file + rename) so the on-disk content
is never left in a partially-written state after a crash.

Performs SHA256 verification before writing to detect external
modifications (best-effort advisory lock — a concurrent writer
between the check and the write is still possible).
"""

import hashlib
import logging

from encoding import (
    encode_cp1252,
    preserve_line_endings,
    detect_line_endings,
    ensure_trailing_newline,
    atomic_write,
    read_and_verify_sha256,
    validate_line_ending_consistency,
    EncodingError,
)

logger = logging.getLogger(__name__)


def write_pawn_file(path: str, content: str, expected_sha256: str) -> dict:
    """
    Write content to a Pawn source file using Windows-1252 encoding.

    Args:
        path: Path to the .pwn/.inc file.
        content: The new file content (already decoded as CP1252 string).
        expected_sha256: SHA-256 hash of the original file before editing.
                        Used as a safety check to detect external modifications.

    Returns:
        A dictionary with:
        - success: True/False
        - sha256: SHA-256 of the newly written file (on success)
        - sizeBytes, encoding, lineEnding
        - Or error/message/encodingIssues on failure
    """
    logger.info(f"[write_pawn_file] Writing: {path}")

    # 1. Read current file and verify SHA256 (shared utility)
    try:
        current_data = read_and_verify_sha256(path, expected_sha256)
    except FileNotFoundError:
        return {
            'success': False,
            'error': True,
            'message': f'File not found: {path}',
        }
    except ValueError as e:
        return {
            'success': False,
            'error': True,
            'message': str(e),
        }

    # 2. Detect line endings from current file
    line_ending = detect_line_endings(current_data)

    # 3. Normalize line endings and preserve trailing newline
    normalized = preserve_line_endings(content, line_ending)
    original_text = current_data.decode('cp1252')
    normalized = ensure_trailing_newline(normalized, original_text, line_ending)

    # 4. Encode to CP1252
    try:
        raw = encode_cp1252(normalized)
    except EncodingError as e:
        return {
            'success': False,
            'error': True,
            'message': str(e),
            'encodingIssues': [
                {
                    'character': issue.character,
                    'codepoint': issue.codepoint,
                    'line': issue.line,
                    'column': issue.column,
                    'description': issue.description,
                }
                for issue in e.issues
            ],
        }

    # 4a. Defense-in-depth: line-ending consistency check
    le_issues = validate_line_ending_consistency(raw, line_ending)
    if le_issues:
        logger.error(
            f"[write_pawn_file] LINE_ENDING_INCONSISTENT: {len(le_issues)} issue(s)"
        )
        return {
            'success': False,
            'error': True,
            'message': (
                f"Line-ending mismatch detected — {len(le_issues)} issue(s). "
                f"File has been left unchanged. Details: {'; '.join(le_issues[:5])}"
            ),
            'issues': le_issues,
        }

    # 5. Atomic write (safe against crashes and partial writes)
    try:
        atomic_write(path, raw)
    except PermissionError:
        return {
            'success': False,
            'error': True,
            'message': f'Permission denied writing to: {path}',
        }
    except Exception as e:
        return {
            'success': False,
            'error': True,
            'message': f'Failed to write file: {e}',
        }

    new_sha256 = hashlib.sha256(raw).hexdigest()
    logger.info(f"[write_pawn_file] OK: {len(raw)} bytes, sha256={new_sha256[:16]}...")

    return {
        'success': True,
        'sha256': new_sha256,
        'sizeBytes': len(raw),
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
    }
