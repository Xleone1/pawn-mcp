"""
write_pawn_file MCP tool.

Writes content to a Pawn source file with Windows-1252 encoding.
Performs SHA256 verification before writing to prevent overwriting
externally modified files.
"""

import hashlib
import logging

from encoding import encode_cp1252, preserve_line_endings, EncodingError

logger = logging.getLogger(__name__)


def write_pawn_file(path: str, content: str, expected_sha256: str) -> dict:
    """
    Write content to a Pawn source file using Windows-1252 encoding.

    Args:
        path: Path to the .pwn/.inc file.
        content: The new file content (already decoded as CP1252 string).
        expected_sha256: SHA-256 hash of the original file before editing.
                        Used as a safety check to prevent overwriting
                        externally modified files.

    Returns:
        A dictionary with:
        - success: True/False
        - sha256: SHA-256 of the newly written file
        - Or error information if the operation failed
    """
    logger.info(f"[write_pawn_file] Writing: {path}")

    # 1. Read the current file and verify SHA256
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

    # 2. Detect line endings from current file
    if b'\r\n' in current_data:
        line_ending = 'CRLF'
    elif b'\r' in current_data:
        line_ending = 'CR'
    else:
        line_ending = 'LF'

    # 3. Normalize line endings and encode to CP1252
    normalized = preserve_line_endings(content, line_ending)

    # Preserve trailing newline if original had one
    original_text = current_data.decode('cp1252')
    if original_text.endswith('\n') and not normalized.endswith('\n'):
        if line_ending == 'CRLF':
            normalized += '\r\n'
        elif line_ending == 'CR':
            normalized += '\r'
        else:
            normalized += '\n'

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

    # 4. Write the file
    try:
        with open(path, 'wb') as f:
            f.write(raw)
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
