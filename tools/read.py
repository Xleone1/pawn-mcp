"""
read_pawn_file MCP tool.

Reads a Pawn source file (.pwn, .inc) with Windows-1252 encoding,
returning content with metadata including SHA256 and line ending info.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def read_pawn_file(path: str) -> dict:
    """
    Read a Pawn source file safely.

    Args:
        path: Absolute or relative path to the .pwn/.inc file.

    Returns:
        A dictionary with:
        - content: The file content decoded as CP1252
        - encoding: Always 'windows-1252'
        - lineEnding: 'CRLF', 'LF', or 'CR'
        - sha256: SHA-256 hash of original bytes
        - sizeBytes: Total file size in bytes
    """
    logger.info(f"[read_pawn_file] Reading: {path}")

    try:
        with open(path, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return {
            'error': True,
            'message': f'File not found: {path}',
        }
    except PermissionError:
        return {
            'error': True,
            'message': f'Permission denied: {path}',
        }
    except Exception as e:
        return {
            'error': True,
            'message': f'Failed to read file: {e}',
        }

    sha256 = hashlib.sha256(data).hexdigest()

    # Detect line endings
    if b'\r\n' in data:
        line_ending = 'CRLF'
    elif b'\r' in data:
        line_ending = 'CR'
    else:
        line_ending = 'LF'

    # Decode CP1252
    try:
        content = data.decode('cp1252')
    except UnicodeDecodeError as e:
        return {
            'error': True,
            'message': f'Failed to decode file as Windows-1252: {e}',
        }

    logger.info(f"[read_pawn_file] OK: {len(data)} bytes, {line_ending}, sha256={sha256[:16]}...")

    return {
        'content': content,
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
        'sha256': sha256,
        'sizeBytes': len(data),
    }
