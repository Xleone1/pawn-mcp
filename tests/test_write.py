"""
Tests for write_pawn_file tool.
"""

import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read import read_pawn_file
from tools.write import write_pawn_file


class TestWritePawnFile:
    """Tests for the write_pawn_file MCP tool."""

    def test_write_preserves_encoding(self, temp_pawn_file):
        """Writing must preserve CP1252 encoding."""
        # Read first
        read_result = read_pawn_file(temp_pawn_file)
        content = read_result['content']
        sha = read_result['sha256']

        # Write back unchanged
        write_result = write_pawn_file(temp_pawn_file, content, sha)
        assert write_result['success'] is True
        assert write_result['encoding'] == 'windows-1252'

    def test_write_preserves_spanish_chars(self, temp_pawn_file):
        """Spanish characters must survive a write."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        # Write back same content
        write_pawn_file(temp_pawn_file, read_result['content'], sha)

        # Read again and verify
        result2 = read_pawn_file(temp_pawn_file)
        assert 'Contraseña' in result2['content']
        assert 'Último' in result2['content']
        assert 'Información' in result2['content']
        assert 'Vehículo' in result2['content']
        assert 'Niño' in result2['content']
        assert 'Acción' in result2['content']

    def test_write_preserves_crlf(self, temp_pawn_file):
        """CRLF line endings must be preserved after write."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        write_pawn_file(temp_pawn_file, read_result['content'], sha)
        result2 = read_pawn_file(temp_pawn_file)
        assert result2['lineEnding'] == 'CRLF'

    def test_write_rejects_wrong_sha256(self, temp_pawn_file):
        """Writing with wrong SHA256 must fail."""
        read_result = read_pawn_file(temp_pawn_file)
        content = read_result['content']
        fake_sha = '0' * 64

        write_result = write_pawn_file(temp_pawn_file, content, fake_sha)
        assert write_result['success'] is False
        assert 'SHA256' in write_result.get('message', '')

    def test_write_rejects_unsupported_unicode(self, temp_pawn_file):
        """Writing content with non-CP1252 characters must fail."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        content = read_result['content']

        # Add an emoji (definitely not in CP1252)
        bad_content = content + "\r\n// \U0001f600\r\n"

        write_result = write_pawn_file(temp_pawn_file, bad_content, sha)
        assert write_result['success'] is False
        assert 'encodingIssues' in write_result or 'encode' in write_result.get('message', '').lower()

    def test_write_returns_new_sha256(self, temp_pawn_file):
        """Successful write must return the new SHA256."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        content = read_result['content']

        write_result = write_pawn_file(temp_pawn_file, content, sha)
        assert write_result['success'] is True
        assert 'sha256' in write_result
        assert len(write_result['sha256']) == 64

    def test_write_missing_file(self):
        """Writing to non-existent file should fail."""
        result = write_pawn_file('/nonexistent/file.pwn', 'content', '0' * 64)
        assert result['success'] is False

    def test_write_identical_content_same_sha256(self, temp_pawn_file):
        """Writing unchanged content should produce the same SHA256."""
        read_result = read_pawn_file(temp_pawn_file)
        original_sha = read_result['sha256']

        write_result = write_pawn_file(temp_pawn_file, read_result['content'], original_sha)
        assert write_result['sha256'] == original_sha
