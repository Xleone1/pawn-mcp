"""
Tests for insert_after_symbol and insert_before_symbol tools.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stat import stat_file
from tools.read_symbol import read_symbol
from tools.insert_symbol import insert_after_symbol, insert_before_symbol


class TestInsertAfter:
    """Tests for insert_after_symbol."""

    def test_insert_after_function(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = insert_after_symbol(
            temp_multi_symbol_file, "GetDistance",
            "stock GetNewFunction()\r\n{\r\n    return 42;\r\n}",
            sha,
        )
        assert result["success"] is True

        sym = read_symbol(temp_multi_symbol_file, "GetNewFunction")
        assert sym["success"] is True
        assert "return 42" in sym["symbol"]["body"]

    def test_insert_after_preserves_cp1252(self, temp_pawn_file):
        sha = stat_file(temp_pawn_file)["sha256"]
        result = insert_after_symbol(
            temp_pawn_file, "gPlayerPassword",
            "// New comment line", sha,
        )
        assert result["success"] is True
        # File should still be valid CP1252
        from tools.verify import verify_encoding
        v = verify_encoding(temp_pawn_file)
        assert v["valid"] is True

    def test_insert_not_found(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = insert_after_symbol(
            temp_multi_symbol_file, "NonExistent", "// x", sha
        )
        assert result["success"] is False
        assert result["errorCode"] == "SYMBOL_NOT_FOUND"

    def test_insert_ambiguous(self, temp_ambiguous_file):
        sha = stat_file(temp_ambiguous_file)["sha256"]
        result = insert_after_symbol(
            temp_ambiguous_file, "OnGameModeInit", "// x", sha
        )
        assert result["success"] is False
        assert result["errorCode"] == "AMBIGUOUS_SYMBOL"

    def test_insert_returns_new_sha(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = insert_after_symbol(
            temp_multi_symbol_file, "PlayerState", "// inserted", sha
        )
        assert result["success"] is True
        assert result["sha256"] != sha


class TestInsertBefore:
    """Tests for insert_before_symbol."""

    def test_insert_before_macro(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = insert_before_symbol(
            temp_multi_symbol_file, "MAX_JUGADORES",
            "// Configuration macros\r\n", sha,
        )
        assert result["success"] is True

    def test_insert_before_returns_new_sha(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = insert_before_symbol(
            temp_multi_symbol_file, "MAX_JUGADORES", "// before macro", sha
        )
        assert result["success"] is True
        assert result["sha256"] != sha
