"""
Tests for stat_file tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stat import stat_file
from tools.errors import success


class TestStatFile:
    """Tests for the stat_file MCP tool."""

    def test_stat_returns_metadata(self, temp_pawn_file):
        """stat_file must return metadata without content."""
        result = stat_file(temp_pawn_file)
        assert result["success"] is True
        assert "content" not in result
        assert "sha256" in result
        assert len(result["sha256"]) == 64
        assert result["sizeBytes"] > 0
        assert result["lineCount"] > 0
        assert result["encoding"] == "windows-1252"
        assert result["lineEnding"] in ("CRLF", "LF", "CR")

    def test_stat_crlf_file(self, temp_pawn_file):
        """CRLF detection must work."""
        result = stat_file(temp_pawn_file)
        assert result["lineEnding"] == "CRLF"

    def test_stat_consistent_sha256(self, temp_pawn_file):
        """Two stat calls must return identical SHA256."""
        r1 = stat_file(temp_pawn_file)
        r2 = stat_file(temp_pawn_file)
        assert r1["sha256"] == r2["sha256"]

    def test_stat_large_file(self, temp_large_file):
        """stat_file must work on files > 500 KB."""
        result = stat_file(temp_large_file)
        assert result["success"] is True
        assert result["sizeBytes"] > 500 * 1024
        assert result["lineCount"] > 1000
        assert len(result["sha256"]) == 64

    def test_stat_missing_file(self):
        """Non-existent file must return structured error."""
        result = stat_file("/nonexistent/file.pwn")
        assert result["success"] is False
        assert result["errorCode"] == "FILE_NOT_FOUND"

    def test_stat_returns_valid_sha256_format(self, temp_pawn_file):
        """SHA256 must be lowercase hex."""
        sha = stat_file(temp_pawn_file)["sha256"]
        assert len(sha) == 64
        assert all(c in "0123456789abcdef" for c in sha)

    def test_stat_multi_symbol_file(self, temp_multi_symbol_file):
        """stat_file must work on multi-symbol files."""
        result = stat_file(temp_multi_symbol_file)
        assert result["success"] is True
        assert result["lineCount"] > 10
