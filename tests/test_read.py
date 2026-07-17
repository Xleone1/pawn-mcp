"""
Tests for read_pawn_file tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read import read_pawn_file


class TestReadPawnFile:
    """Tests for the read_pawn_file MCP tool."""

    def test_read_cp1252_file(self, temp_pawn_file):
        """Reading a CP1252 file should return content with metadata."""
        result = read_pawn_file(temp_pawn_file)

        assert 'error' not in result
        assert 'content' in result
        assert result['encoding'] == 'windows-1252'
        assert result['lineEnding'] in ('CRLF', 'LF', 'CR')
        assert len(result['sha256']) == 64
        assert result['sizeBytes'] > 0

    def test_read_returns_spanish_chars(self, temp_pawn_file):
        """Spanish characters must appear correctly in returned content."""
        result = read_pawn_file(temp_pawn_file)
        content = result['content']

        # All Spanish words should be present
        assert 'Contraseña' in content
        assert 'Último' in content
        assert 'Información' in content
        assert 'Vehículo' in content
        assert 'Niño' in content
        assert 'Acción' in content
        assert '¿' in content
        assert '¡' in content

    def test_read_detects_crlf(self, temp_pawn_file):
        """CRLF files should be detected."""
        result = read_pawn_file(temp_pawn_file)
        assert result['lineEnding'] == 'CRLF'

    def test_read_sha256_length(self, temp_pawn_file):
        """SHA256 should be 64 hex characters."""
        result = read_pawn_file(temp_pawn_file)
        sha = result['sha256']
        assert len(sha) == 64
        assert all(c in '0123456789abcdef' for c in sha)

    def test_read_missing_file(self):
        """Non-existent file should return error."""
        result = read_pawn_file('/nonexistent/file.pwn')
        assert result['success'] is False
        assert result['errorCode'] == 'FILE_NOT_FOUND'

    def test_read_consistent_sha256(self, temp_pawn_file):
        """Reading the same file twice should give the same SHA256."""
        r1 = read_pawn_file(temp_pawn_file)
        r2 = read_pawn_file(temp_pawn_file)
        assert r1['sha256'] == r2['sha256']

    def test_content_is_string(self, temp_pawn_file):
        """Content must be a string, not bytes."""
        result = read_pawn_file(temp_pawn_file)
        assert isinstance(result['content'], str)

    def test_large_file_rejected(self, temp_large_file):
        """Files larger than threshold must be rejected with FILE_TOO_LARGE."""
        result = read_pawn_file(temp_large_file)
        assert result['success'] is False
        assert result['errorCode'] == 'FILE_TOO_LARGE'
        assert 'sizeBytes' in result
        assert 'maxAllowedBytes' in result
        assert 'suggestedTools' in result
        assert 'stat_file' in result['suggestedTools']
        assert 'list_symbols' in result['suggestedTools']
        assert 'read_symbol' in result['suggestedTools']
        assert result['sizeBytes'] > result['maxAllowedBytes']

    def test_small_file_read_includes_hint(self, temp_pawn_file):
        """Small files should still return content but include a hint."""
        result = read_pawn_file(temp_pawn_file)
        assert result['success'] is True
        assert 'hint' in result
        assert 'list_symbols' in result['hint']
        assert 'content' in result

    def test_read_includes_line_count(self, temp_pawn_file):
        """read_pawn_file must include lineCount."""
        result = read_pawn_file(temp_pawn_file)
        assert result['lineCount'] > 0
