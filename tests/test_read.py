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
        assert result.get('error') is True
        assert 'not found' in result.get('message', '').lower()

    def test_read_consistent_sha256(self, temp_pawn_file):
        """Reading the same file twice should give the same SHA256."""
        r1 = read_pawn_file(temp_pawn_file)
        r2 = read_pawn_file(temp_pawn_file)
        assert r1['sha256'] == r2['sha256']

    def test_content_is_string(self, temp_pawn_file):
        """Content must be a string, not bytes."""
        result = read_pawn_file(temp_pawn_file)
        assert isinstance(result['content'], str)
