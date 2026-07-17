"""
Tests for replace_range tool.
"""

import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stat import stat_file
from tools.read_range import read_range
from tools.replace_range import replace_range


class TestReplaceRange:
    """Tests for replace_range MCP tool."""

    def test_replace_single_line(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = replace_range(temp_multi_symbol_file, 1, 1,
                               "// Replaced header", sha)
        assert result["success"] is True
        content = read_range(temp_multi_symbol_file, 1, 1)["content"]
        assert "Replaced header" in content

    def test_replace_preserves_cp1252(self, temp_pawn_file):
        sha = stat_file(temp_pawn_file)["sha256"]
        replace_range(temp_pawn_file, 1, 1, "// New header", sha)
        content = read_range(temp_pawn_file, 4, 12)["content"]
        assert "Contraseña" in content

    def test_replace_preserves_crlf(self, temp_pawn_file):
        sha = stat_file(temp_pawn_file)["sha256"]
        replace_range(temp_pawn_file, 1, 1, "// new", sha)
        result = stat_file(temp_pawn_file)
        assert result["lineEnding"] == "CRLF"

    def test_replace_preserves_surrounding_bytes(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_range(temp_multi_symbol_file, 9, 10,
                      "// removed forwards", sha)
        content = read_range(temp_multi_symbol_file, 1, 8)["content"]
        assert "Multi-symbol" in content
        assert "MAX_JUGADORES" in content

    def test_replace_multi_line(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_range(temp_multi_symbol_file, 9, 11,
                      "// Forward declarations replaced\n", sha)
        content = read_range(temp_multi_symbol_file, 9, 11)["content"]
        assert "Forward declarations replaced" in content

    def test_replace_rejects_wrong_sha(self, temp_pawn_file):
        result = replace_range(temp_pawn_file, 1, 1, "// x", "0" * 64)
        assert result["success"] is False
        assert result["errorCode"] == "SHA256_MISMATCH"

    def test_replace_invalid_range(self, temp_pawn_file):
        sha = stat_file(temp_pawn_file)["sha256"]
        result = replace_range(temp_pawn_file, 10, 5, "// x", sha)
        assert result["success"] is False
        assert result["errorCode"] == "INVALID_RANGE"

    def test_replace_returns_new_sha(self, temp_pawn_file):
        sha = stat_file(temp_pawn_file)["sha256"]
        result = replace_range(temp_pawn_file, 1, 1, "// modified", sha)
        assert result["success"] is True
        assert result["sha256"] != sha
        assert len(result["sha256"]) == 64
