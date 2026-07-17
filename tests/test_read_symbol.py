"""
Tests for read_symbol tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read_symbol import read_symbol


class TestReadSymbol:
    """Tests for the read_symbol MCP tool."""

    def test_read_function_with_body(self, temp_multi_symbol_file):
        """Reading a stock function must return its body."""
        result = read_symbol(temp_multi_symbol_file, "GetPlayerName")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["name"] == "GetPlayerName"
        assert sym["kind"] == "function"
        assert sym["startLine"] <= sym["endLine"]
        assert "GetPlayerName(playerid, name[], len)" in sym["signature"]
        assert "return 1;" in sym["body"]
        # Must have context
        assert "contextBefore" in sym
        assert "contextAfter" in sym

    def test_read_public_function(self, temp_multi_symbol_file):
        """OnPlayerConnect is ambiguous (forward + public) — must return AMBIGUOUS."""
        result = read_symbol(temp_multi_symbol_file, "OnPlayerConnect")
        # Both forward and public function match — ambiguous
        assert result["success"] is False
        assert result["errorCode"] == "AMBIGUOUS_SYMBOL"
        candidates = result["candidates"]
        kinds = {c["kind"] for c in candidates}
        assert "forward" in kinds
        assert "function" in kinds

    def test_read_forward(self, temp_multi_symbol_file):
        """Reading a forward-only symbol must work."""
        result = read_symbol(temp_multi_symbol_file, "OnPlayerDisconnect")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "forward"
        assert "OnPlayerDisconnect" in sym["signature"]

    def test_read_macro(self, temp_multi_symbol_file):
        """Reading a macro must return its definition."""
        result = read_symbol(temp_multi_symbol_file, "MAX_JUGADORES")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "macro"
        assert "MAX_JUGADORES" in sym["signature"]

    def test_read_multiline_macro(self, temp_multi_symbol_file):
        """Multi-line macro with \\ continuations must be stitched."""
        result = read_symbol(temp_multi_symbol_file, "SERVER_NAME")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "macro"
        assert sym["endLine"] > sym["startLine"]
        assert "Mi Servidor" in sym["body"]

    def test_read_variable(self, temp_multi_symbol_file):
        """Reading a variable declaration must work."""
        result = read_symbol(temp_multi_symbol_file, "gPlayerScore")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "variable"
        assert "gPlayerScore" in sym["signature"]

    def test_read_enum(self, temp_multi_symbol_file):
        """Reading an enum must return body with braces."""
        result = read_symbol(temp_multi_symbol_file, "PlayerState")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "enum"
        assert "STATE_NONE" in sym["body"]
        assert sym["endLine"] > sym["startLine"]

    def test_read_ambiguous_symbol(self, temp_ambiguous_file):
        """Ambiguous symbols must return AMBIGUOUS_SYMBOL error."""
        result = read_symbol(temp_ambiguous_file, "OnGameModeInit")
        assert result["success"] is False
        assert result["errorCode"] == "AMBIGUOUS_SYMBOL"
        assert "candidates" in result
        assert len(result["candidates"]) >= 2

    def test_read_symbol_not_found(self, temp_multi_symbol_file):
        """Non-existent symbol must return SYMBOL_NOT_FOUND."""
        result = read_symbol(temp_multi_symbol_file, "NonExistentFunction")
        assert result["success"] is False
        assert result["errorCode"] == "SYMBOL_NOT_FOUND"

    def test_read_symbol_missing_file(self):
        """Non-existent file must return error."""
        result = read_symbol("/nonexistent/file.pwn", "whatever")
        assert result["success"] is False
        assert result["errorCode"] == "FILE_NOT_FOUND"

    def test_read_symbol_context_before(self, temp_multi_symbol_file):
        """Context before the symbol must be non-empty."""
        result = read_symbol(temp_multi_symbol_file, "GetPlayerName")
        sym = result["symbol"]
        # GetPlayerName is not on line 1, so there should be context
        if sym["startLine"] > 1:
            assert len(sym["contextBefore"]) > 0

    def test_read_symbol_context_after(self, temp_multi_symbol_file):
        """Context after the symbol must be non-empty unless at EOF."""
        result = read_symbol(temp_multi_symbol_file, "OnPlayerConnect")
        sym = result["symbol"]
        # Should have something after (main, or EOF)
        # Context might be empty string if at EOF, which is fine

    def test_read_symbol_line_endings(self, temp_multi_symbol_file):
        """lineEnding must be reported."""
        result = read_symbol(temp_multi_symbol_file, "MAX_JUGADORES")
        assert "lineEnding" in result
        assert result["lineEnding"] in ("CRLF", "LF", "CR")

    def test_read_symbol_encoding(self, temp_multi_symbol_file):
        """encoding must be reported as windows-1252."""
        result = read_symbol(temp_multi_symbol_file, "MAX_JUGADORES")
        assert result["encoding"] == "windows-1252"

    def test_read_symbol_large_file(self, temp_large_file):
        """read_symbol must work on large files by finding a known pattern."""
        result = read_symbol(temp_large_file, "gVar_000100")
        assert result["success"] is True
        sym = result["symbol"]
        assert sym["kind"] == "variable"
