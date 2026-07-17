"""
Tests for replace_symbol tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.stat import stat_file
from tools.read_symbol import read_symbol
from tools.replace_symbol import replace_symbol


class TestReplaceSymbol:
    """Tests for replace_symbol MCP tool."""

    def test_replace_function(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        new_body = (
            "stock GetPlayerName(playerid, name[], len)\r\n"
            "{\r\n"
            "    // Modified implementation\r\n"
            "    GetPlayerName(playerid, name, len);\r\n"
            "    strcat(name, \" [MOD]\", len);\r\n"
            "    return 1;\r\n"
            "}"
        )
        result = replace_symbol(temp_multi_symbol_file, "GetPlayerName",
                                new_body, sha)
        assert result["success"] is True
        sym = read_symbol(temp_multi_symbol_file, "GetPlayerName")
        assert "MOD" in sym["symbol"]["body"]

    def test_replace_function_tabs(self, temp_tab_file):
        """Replacing tab-indented function must work regardless of whitespace."""
        sha = stat_file(temp_tab_file)["sha256"]
        new_body = (
            "stock GetPlayerName(playerid, name[], len)\r\n"
            "{\r\n"
            "    new str[128];\r\n"
            "    GetPlayerName(playerid, name, len);\r\n"
            "    if (name[0] == EOS)\r\n"
            "    {\r\n"
            "        format(str, sizeof(str), \"Player_%d\", playerid);\r\n"
            "        strcat(name, str, len);\r\n"
            "    }\r\n"
            "    return 1;\r\n"
            "}"
        )
        result = replace_symbol(temp_tab_file, "GetPlayerName", new_body, sha)
        assert result["success"] is True
        sym = read_symbol(temp_tab_file, "GetPlayerName")
        assert "Player_%d" in sym["symbol"]["body"]

    def test_replace_function_surrounding_intact(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_symbol(temp_multi_symbol_file, "GetPlayerName",
            "stock GetPlayerName(playerid, name[], len)\r\n{\r\n    return 0;\r\n}",
            sha)
        sym = read_symbol(temp_multi_symbol_file, "MAX_JUGADORES")
        assert sym["success"] is True

    def test_replace_macro(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_symbol(temp_multi_symbol_file, "MAX_JUGADORES",
                       "#define MAX_JUGADORES 200", sha)
        sym = read_symbol(temp_multi_symbol_file, "MAX_JUGADORES")
        assert "200" in sym["symbol"]["body"]



    def test_replace_not_found(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = replace_symbol(temp_multi_symbol_file, "NonExistent", "// x", sha)
        assert result["success"] is False
        assert result["errorCode"] == "SYMBOL_NOT_FOUND"

    def test_replace_ambiguous(self, temp_ambiguous_file):
        sha = stat_file(temp_ambiguous_file)["sha256"]
        result = replace_symbol(temp_ambiguous_file, "OnGameModeInit", "// x", sha)
        assert result["success"] is False
        assert result["errorCode"] == "AMBIGUOUS_SYMBOL"

    def test_replace_returns_new_sha(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        result = replace_symbol(temp_multi_symbol_file, "MAX_JUGADORES",
                                "#define MAX_JUGADORES 500", sha)
        assert result["success"] is True
        assert result["sha256"] != sha
        assert len(result["sha256"]) == 64

    def test_replace_wrong_sha(self, temp_pawn_file):
        result = replace_symbol(temp_pawn_file, "whatever", "// x", "0" * 64)
        assert result["success"] is False
        assert result["errorCode"] == "SHA256_MISMATCH"

    def test_replace_enum(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_symbol(temp_multi_symbol_file, "PlayerState",
            "enum PlayerState {\r\n    STATE_NONE,\r\n    STATE_ACTIVE,\r\n    STATE_SPAWNED\r\n}",
            sha)
        sym = read_symbol(temp_multi_symbol_file, "PlayerState")
        assert "STATE_ACTIVE" in sym["symbol"]["body"]

    def test_replace_variable(self, temp_multi_symbol_file):
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        replace_symbol(temp_multi_symbol_file, "gPlayerScore",
                       "new gPlayerScore[MAX_PLAYERS] = {0, ...};", sha)
        sym = read_symbol(temp_multi_symbol_file, "gPlayerScore")
        assert "{0, ...}" in sym["symbol"]["body"]
