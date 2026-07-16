"""
Tests for verify_encoding tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.verify import verify_encoding


class TestVerifyEncoding:
    """Tests for the verify_encoding MCP tool."""

    def test_valid_cp1252_passes(self, temp_pawn_file):
        """A clean CP1252 file should pass verification."""
        result = verify_encoding(temp_pawn_file)
        assert result['valid'] is True
        assert result['encoding'] == 'windows-1252'
        assert len(result['issues']) == 0

    def test_verify_includes_metadata(self, temp_pawn_file):
        """Verification result must include encoding metadata."""
        result = verify_encoding(temp_pawn_file)
        assert 'lineEnding' in result
        assert 'sha256' in result
        assert 'sizeBytes' in result
        assert result['lineEnding'] in ('CRLF', 'LF', 'CR')

    def test_verify_missing_file(self):
        """Non-existent file should return invalid."""
        result = verify_encoding('/nonexistent/file.pwn')
        assert result['valid'] is False

    def test_verify_detects_utf8_bom(self):
        """File with UTF-8 BOM should be flagged."""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode='wb', suffix='.pwn', delete=False
        )
        # Write UTF-8 BOM + content
        tmp.write(b'\xef\xbb\xbf' + "Contraseña".encode('utf-8'))
        tmp.close()

        try:
            result = verify_encoding(tmp.name)
            assert result['valid'] is False
            assert any('BOM' in i.get('message', '') for i in result.get('issues', []))
        finally:
            os.unlink(tmp.name)

    def test_verify_detects_crlf(self, temp_pawn_file):
        """Verify should detect CRLF line endings."""
        result = verify_encoding(temp_pawn_file)
        assert result['lineEnding'] == 'CRLF'
