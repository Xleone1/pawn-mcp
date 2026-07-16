"""
apply_patch MCP tool.

Applies a unified diff to a Pawn source file while preserving
Windows-1252 encoding and line endings.

This is the preferred editing tool for Pawn/Open.MP projects.

Uses an atomic write (temp file + rename) so the on-disk content
is never left in a partially-written state after a crash.
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
    EncodingError,
)
from patching import apply_unified_diff

logger = logging.getLogger(__name__)


def apply_patch(path: str, unified_diff: str, expected_sha256: str) -> dict:
    """
    Apply a unified diff to a Pawn source file.

    Args:
        path: Path to the .pwn/.inc file.
        unified_diff: A unified diff to apply.
        expected_sha256: SHA-256 hash of the original file before patching.

    Returns:
        A dictionary with:
        - success: True/False
        - sha256: SHA-256 of the patched file (on success)
        - Or error/message/encodingIssues on failure
    """
    logger.info(f"[apply_patch] Patching: {path}")

    # 1. Read and verify current file SHA256 (shared utility)
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

    # 2. Detect line endings
    line_ending = detect_line_endings(current_data)

    # 3. Decode as CP1252
    original_text = current_data.decode('cp1252')

    # 4. Apply the unified diff
    try:
        patched_text = apply_unified_diff(original_text, unified_diff)
    except ValueError as e:
        return {
            'success': False,
            'error': True,
            'message': f'Patch application failed: {e}',
        }

    # 5. Normalize line endings and preserve trailing newline
    normalized = preserve_line_endings(patched_text, line_ending)
    normalized = ensure_trailing_newline(normalized, original_text, line_ending)

    # 6. Encode back to CP1252
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

    # 7. Atomic write (safe against crashes and partial writes)
    try:
        atomic_write(path, raw)
    except Exception as e:
        return {
            'success': False,
            'error': True,
            'message': f'Failed to write file: {e}',
        }

    new_sha256 = hashlib.sha256(raw).hexdigest()
    logger.info(f"[apply_patch] OK: {len(raw)} bytes, sha256={new_sha256[:16]}...")

    return {
        'success': True,
        'sha256': new_sha256,
        'sizeBytes': len(raw),
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
    }
