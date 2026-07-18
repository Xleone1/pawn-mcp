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
from patching import apply_string_patch

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


def apply_string_patch_tool(
    path: str,
    old_string: str,
    new_string: str,
    expected_sha256: str,
    replace_all: bool = False,
) -> dict:
    """
    Replace old_string with new_string in a Pawn source file by exact text match.

    This is the **PREFERRED** editing tool over diff-based ``apply_patch``.
    Because ``read_symbol()`` returns the exact ``body`` text of a symbol,
    you can quote that text verbatim as ``old_string`` without needing to
    count lines or generate line-number diffs — the match is purely textual.

    Args:
        path: Path to the .pwn/.inc file.
        old_string: Exact text to find and replace. Must match verbatim,
            including whitespace and line endings.
        new_string: Replacement text.
        expected_sha256: SHA-256 hash of the original file before editing.
        replace_all: If True, replace all occurrences. If False (default),
            old_string must match exactly once.

    Returns:
        A dictionary with success status, new SHA-256, size, encoding, and
        lineEnding on success, or errorCode/message on failure.
    """
    logger.info(f"[apply_string_patch] Patching: {path}")

    # 1. Read and verify current file SHA256
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

    # 4. Apply the string patch
    try:
        patched_text = apply_string_patch(
            original_text, old_string, new_string, replace_all
        )
    except ValueError as e:
        return {
            'success': False,
            'error': True,
            'message': str(e),
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

    # 7. Atomic write
    try:
        atomic_write(path, raw)
    except Exception as e:
        return {
            'success': False,
            'error': True,
            'message': f'Failed to write file: {e}',
        }

    new_sha256 = hashlib.sha256(raw).hexdigest()
    logger.info(
        f"[apply_string_patch] OK: {len(raw)} bytes, sha256={new_sha256[:16]}..."
    )

    return {
        'success': True,
        'sha256': new_sha256,
        'sizeBytes': len(raw),
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
    }
