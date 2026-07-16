"""
apply_patch MCP tool.

Applies a unified diff to a Pawn source file while preserving
Windows-1252 encoding and line endings.

This is the preferred editing tool for Pawn/Open.MP projects.
"""

import hashlib
import logging

from encoding import encode_cp1252, preserve_line_endings, EncodingError
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
        - Or error information if the patch failed
    """
    logger.info(f"[apply_patch] Patching: {path}")

    # 1. Read and verify current file
    try:
        with open(path, 'rb') as f:
            current_data = f.read()
    except FileNotFoundError:
        return {
            'success': False,
            'error': True,
            'message': f'File not found: {path}',
        }

    current_sha256 = hashlib.sha256(current_data).hexdigest()

    if current_sha256 != expected_sha256:
        return {
            'success': False,
            'error': True,
            'message': (
                f'SHA256 mismatch: file has been modified externally.\n'
                f'  Expected: {expected_sha256}\n'
                f'  Actual:   {current_sha256}'
            ),
        }

    # 2. Detect line endings
    if b'\r\n' in current_data:
        line_ending = 'CRLF'
    elif b'\r' in current_data:
        line_ending = 'CR'
    else:
        line_ending = 'LF'

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

    # 5. Normalize line endings to match original
    normalized = preserve_line_endings(patched_text, line_ending)

    # Preserve trailing newline
    if original_text.endswith('\n') and not normalized.endswith('\n'):
        if line_ending == 'CRLF':
            normalized += '\r\n'
        elif line_ending == 'CR':
            normalized += '\r'
        else:
            normalized += '\n'

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

    # 7. Write the file
    try:
        with open(path, 'wb') as f:
            f.write(raw)
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
