"""
Tests for list_symbols tool.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.list_symbols import list_symbols


class TestListSymbols:
    """Tests for the list_symbols MCP tool."""

    def test_list_detects_functions(self, temp_multi_symbol_file):
        """Must detect public/stock functions."""
        result = list_symbols(temp_multi_symbol_file)
        assert result["success"] is True
        names = {s["name"] for s in result["symbols"]}
        assert "OnPlayerConnect" in names
        assert "GetPlayerName" in names
        assert "GetDistance" in names

    def test_list_detects_forwards(self, temp_multi_symbol_file):
        """Must detect forward declarations."""
        result = list_symbols(temp_multi_symbol_file)
        fwd = [s for s in result["symbols"] if s["kind"] == "forward"]
        names = {s["name"] for s in fwd}
        assert "OnPlayerConnect" in names
        assert "OnPlayerDisconnect" in names

    def test_list_detects_macros(self, temp_multi_symbol_file):
        """Must detect #define macros."""
        result = list_symbols(temp_multi_symbol_file)
        macros = [s for s in result["symbols"] if s["kind"] == "macro"]
        names = {s["name"] for s in macros}
        assert "MAX_JUGADORES" in names

    def test_list_detects_variables(self, temp_multi_symbol_file):
        """Must detect new/static variable declarations."""
        result = list_symbols(temp_multi_symbol_file)
        vars_ = [s for s in result["symbols"] if s["kind"] == "variable"]
        names = {s["name"] for s in vars_}
        assert "gPlayerName" in names
        assert "gServerUptime" in names

    def test_list_detects_enums(self, temp_multi_symbol_file):
        """Must detect enum declarations."""
        result = list_symbols(temp_multi_symbol_file)
        enums = [s for s in result["symbols"] if s["kind"] == "enum"]
        names = {s["name"] for s in enums}
        assert "PlayerState" in names
        assert "eVehicleType" in names

    def test_list_filter_by_kind(self, temp_multi_symbol_file):
        """Filtering by kind must work."""
        result = list_symbols(temp_multi_symbol_file, kind="function")
        assert result["success"] is True
        for s in result["symbols"]:
            assert s["kind"] == "function"
        # Should have at least public functions
        assert len(result["symbols"]) >= 2

    def test_list_invalid_kind(self, temp_multi_symbol_file):
        """Invalid kind must return error."""
        result = list_symbols(temp_multi_symbol_file, kind="class")
        assert result["success"] is False
        assert result["errorCode"] == "INVALID_ARGUMENT"

    def test_list_pagination(self, temp_multi_symbol_file):
        """Pagination with limit and offset must work."""
        result = list_symbols(temp_multi_symbol_file, limit=2, offset=0)
        assert result["success"] is True
        assert len(result["symbols"]) == 2
        assert result["totalSymbols"] > 2
        assert result["hasMore"] is True
        assert result["limit"] == 2
        assert result["offset"] == 0

    def test_list_pagination_second_page(self, temp_multi_symbol_file):
        """Second page must have different symbols."""
        page1 = list_symbols(temp_multi_symbol_file, limit=3, offset=0)
        page2 = list_symbols(temp_multi_symbol_file, limit=3, offset=3)
        names1 = {s["name"] for s in page1["symbols"]}
        names2 = {s["name"] for s in page2["symbols"]}
        assert names1 != names2

    def test_list_has_more_false_at_end(self, temp_multi_symbol_file):
        """hasMore must be False when all symbols returned."""
        total = list_symbols(temp_multi_symbol_file)["totalSymbols"]
        result = list_symbols(temp_multi_symbol_file, limit=total + 100, offset=0)
        assert result["hasMore"] is False

    def test_list_symbols_have_signatures(self, temp_multi_symbol_file):
        """Every symbol must have a signature string."""
        result = list_symbols(temp_multi_symbol_file)
        for s in result["symbols"]:
            assert "signature" in s
            assert isinstance(s["signature"], str)
            assert len(s["signature"]) > 0

    def test_list_symbols_have_line_numbers(self, temp_multi_symbol_file):
        """Every symbol must have a 1-indexed line number."""
        result = list_symbols(temp_multi_symbol_file)
        for s in result["symbols"]:
            assert s["line"] >= 1

    def test_list_missing_file(self):
        """Non-existent file must return error."""
        result = list_symbols("/nonexistent/file.pwn")
        assert result["success"] is False
        assert result["errorCode"] == "FILE_NOT_FOUND"

    def test_list_large_file(self, temp_large_file):
        """list_symbols must work on large files."""
        result = list_symbols(temp_large_file, limit=10, offset=0)
        assert result["success"] is True
        assert result["totalSymbols"] > 0
        assert len(result["symbols"]) <= 10
