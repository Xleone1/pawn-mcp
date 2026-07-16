"""
read_pawn_file MCP tool.

Reads a Pawn source file (.pwn, .inc) with Windows-1252 encoding,
returning content with metadata including SHA256 and line ending info.
"""

import hashlib
import logging

from encoding import detect_line_endings

logger = logging.getLogger(__name__)


def read_pawn_file(path: str) -> dict:
    """
    Read a Pawn source file safely.

    Args:
        path: Absolute or relative path to the .pwn/.inc file.

    Returns:
        A dictionary with:
        - success: True
        - content: The file content decoded as CP1252
        - encoding: Always 'windows-1252'
        - lineEnding: 'CRLF', 'LF', or 'CR'
        - sha256: SHA-256 hash of original bytes
        - sizeBytes: Total file size in bytes

        On error:
        - success: False
        - error: True
        - message: Human-readable error description
    """
    logger.info(f"[read_pawn_file] Reading: {path}")

    try:
        with open(path, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return {
            'success': False,
            'error': True,
            'message': f'File not found: {path}',
        }
    except PermissionError:
        return {
            'success': False,
            'error': True,
            'message': f'Permission denied: {path}',
        }
    except Exception as e:
        return {
            'success': False,
            'error': True,
            'message': f'Failed to read file: {e}',
        }

    sha256 = hashlib.sha256(data).hexdigest()

    # Detect line endings via shared utility
    line_ending = detect_line_endings(data)

    # Decode CP1252
    try:
        content = data.decode('cp1252')
    except UnicodeDecodeError as e:
        return {
            'success': False,
            'error': True,
            'message': f'Failed to decode file as Windows-1252: {e}',
        }

    logger.info(f"[read_pawn_file] OK: {len(data)} bytes, {line_ending}, sha256={sha256[:16]}...")

    return {
        'success': True,
        'content': content,
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
        'sha256': sha256,
        'sizeBytes': len(data),
    }
