"""
Tests for read_range tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_range import read_range


class TestReadRange:
    """Tests for the read_range MCP tool."""

    def test_read_single_line(self, temp_multi_symbol_file):
        """Reading a single line must work."""
        result = read_range(temp_multi_symbol_file, 1, 1)
        assert result["success"] is True
        assert result["startLine"] == 1
        assert result["endLine"] == 1
        assert "// Multi-symbol test file" in result["content"]

    def test_read_range_preserves_encoding(self, temp_pawn_file):
        """Spanish characters must survive a ranged read."""
        result = read_range(temp_pawn_file, 4, 12)
        assert result["success"] is True
        content = result["content"]
        assert "Contraseña" in content
        assert "Último" in content

    def test_read_range_preserves_crlf(self, temp_pawn_file):
        """CRLF line endings must be preserved."""
        result = read_range(temp_pawn_file, 1, 3)
        assert result["lineEnding"] == "CRLF"
        assert "\r\n" in result["content"]

    def test_read_range_start_equals_end(self, temp_multi_symbol_file):
        """startLine == endLine must return exactly one line."""
        result = read_range(temp_multi_symbol_file, 4, 4)
        assert result["success"] is True
        assert result["startLine"] == 4
        assert result["endLine"] == 4
        # Should not contain line 5 content
        lines = result["content"].split("\n")
        assert len(lines) <= 2  # may have trailing newline

    def test_read_range_out_of_bounds(self, temp_pawn_file):
        """startLine beyond EOF must return error."""
        result = read_range(temp_pawn_file, 99999, 99999)
        assert result["success"] is False
        assert result["errorCode"] == "INVALID_RANGE"

    def test_read_range_end_clamped(self, temp_multi_symbol_file):
        """endLine beyond EOF must be clamped to total lines."""
        result = read_range(temp_multi_symbol_file, 1, 99999)
        assert result["success"] is True
        assert result["endLine"] < 99999

    def test_read_range_invalid_start(self, temp_pawn_file):
        """startLine < 1 must return error."""
        result = read_range(temp_pawn_file, 0, 10)
        assert result["success"] is False
        assert result["errorCode"] == "INVALID_RANGE"

    def test_read_range_start_greater_than_end(self, temp_pawn_file):
        """startLine > endLine must return error."""
        result = read_range(temp_pawn_file, 10, 5)
        assert result["success"] is False
        assert result["errorCode"] == "INVALID_RANGE"

    def test_read_range_missing_file(self):
        """Non-existent file must return error."""
        result = read_range("/nonexistent/file.pwn", 1, 10)
        assert result["success"] is False
        assert result["errorCode"] == "FILE_NOT_FOUND"

    def test_read_range_total_lines_returned(self, temp_multi_symbol_file):
        """totalLines must be returned."""
        result = read_range(temp_multi_symbol_file, 1, 5)
        assert "totalLines" in result
        assert result["totalLines"] > 0

    def test_read_range_large_file(self, temp_large_file):
        """read_range must work on large files without loading everything."""
        result = read_range(temp_large_file, 100, 110)
        assert result["success"] is True
        assert result["startLine"] == 100
        assert result["endLine"] == 110
        assert "gVar_" in result["content"]
