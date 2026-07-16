"""
verify_encoding MCP tool.

Verifies that a Pawn source file is properly encoded as Windows-1252
with no corruption, UTF-8 BOM, or replacement characters.
"""

import hashlib
import logging

from encoding import detect_line_endings

logger = logging.getLogger(__name__)


def verify_encoding(path: str) -> dict:
    """
    Verify that a file is valid Windows-1252.

    Checks:
    - File is readable
    - No UTF-8 BOM present
    - All bytes decode cleanly as CP1252
    - File successfully round-trips through CP1252 (decode -> encode)
    - No replacement characters (U+FFFD)

    Args:
        path: Path to the file to verify.

    Returns:
        A dictionary with:
        - success: True/False
        - valid: True/False (same as success — kept for backward compat)
        - encoding, path, lineEnding, sha256, sizeBytes, issues[]
        - Or error/message on failure
    """
    logger.info(f"[verify_encoding] Verifying: {path}")

    # Read raw bytes
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except FileNotFoundError:
        return {
            'success': False,
            'valid': False,
            'error': True,
            'message': f'File not found: {path}',
        }
    except PermissionError:
        return {
            'success': False,
            'valid': False,
            'error': True,
            'message': f'Permission denied: {path}',
        }

    sha256 = hashlib.sha256(data).hexdigest()
    line_ending = detect_line_endings(data)

    diagnostics = {
        'success': True,
        'valid': True,
        'path': path,
        'encoding': 'windows-1252',
        'lineEnding': line_ending,
        'sha256': sha256,
        'sizeBytes': len(data),
        'issues': [],
    }

    # Check 1: UTF-8 BOM
    if data[:3] == b'\xef\xbb\xbf':
        diagnostics['valid'] = diagnostics['success'] = False
        diagnostics['issues'].append({
            'severity': 'error',
            'type': 'utf8_bom',
            'message': 'File contains UTF-8 BOM (EF BB BF). Pawn files must be pure CP1252 without BOM.',
        })

    # Check 2: Decode as CP1252
    try:
        decoded = data.decode('cp1252')
    except UnicodeDecodeError as e:
        diagnostics['valid'] = diagnostics['success'] = False
        diagnostics['issues'].append({
            'severity': 'error',
            'type': 'decode_error',
            'message': f'Failed to decode as Windows-1252: {e.reason}',
            'position': e.start,
        })
        return diagnostics

    # Check 3: Replacement characters (U+FFFD)
    replacement_positions = []
    for i, char in enumerate(decoded):
        if char == '\ufffd':
            # Find line and column
            line = decoded[:i].count('\n') + 1
            last_newline = decoded[:i].rfind('\n')
            col = i - last_newline if last_newline != -1 else i + 1
            replacement_positions.append({
                'line': line,
                'column': col,
                'byteOffset': i,
            })

    if replacement_positions:
        diagnostics['valid'] = diagnostics['success'] = False
        for pos in replacement_positions:
            diagnostics['issues'].append({
                'severity': 'error',
                'type': 'replacement_character',
                'message': (
                    f'Replacement character (U+FFFD) found at '
                    f'line {pos["line"]}, column {pos["column"]} '
                    f'(byte offset {pos["byteOffset"]})'
                ),
                'line': pos['line'],
                'column': pos['column'],
                'byteOffset': pos['byteOffset'],
            })

    # Check 4: Round-trip
    reencoded = decoded.encode('cp1252')
    if reencoded != data:
        diagnostics['valid'] = diagnostics['success'] = False
        # Find first differing byte
        diff_pos = 0
        for i, (a, b) in enumerate(zip(data, reencoded)):
            if a != b:
                diff_pos = i
                break
        else:
            diff_pos = min(len(data), len(reencoded))

        diagnostics['issues'].append({
            'severity': 'error',
            'type': 'roundtrip_failure',
            'message': (
                f'Round-trip failure: CP1252 decode → encode produced different bytes. '
                f'First difference at byte offset {diff_pos}'
            ),
            'byteOffset': diff_pos,
        })

    if diagnostics['valid']:
        logger.info(f"[verify_encoding] OK: {path} is valid CP1252")
    else:
        logger.warning(f"[verify_encoding] FAIL: {path} has {len(diagnostics['issues'])} issue(s)")

    return diagnostics
