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
from encoding import (
    detect_line_endings,
    validate_line_ending_consistency,
)


def _raw_bytes(path: str) -> bytes:
    with open(path, 'rb') as f:
        return f.read()


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


class TestReplaceRangeLineEndingNormalization:
    """Fix — ensure new_content line endings are normalized to match the file."""

    def test_crlf_file_bare_lf_input_stays_crlf(self, temp_pawn_file):
        """CRLF file + new_content with bare \\n → result is consistently CRLF."""
        sha = stat_file(temp_pawn_file)["sha256"]
        # Multi-line replacement with only bare LF separators
        new_content = "// Línea 1\n// Línea 2 con ñ\n// Línea 3\n"
        result = replace_range(temp_pawn_file, 1, 3, new_content, sha)
        assert result["success"] is True
        assert result["lineEnding"] == "CRLF"

        raw = _raw_bytes(temp_pawn_file)
        issues = validate_line_ending_consistency(raw, "CRLF")
        assert issues == [], f"Mixed line endings found: {issues}"

    def test_lf_file_crlf_input_stays_lf(self, temp_pawn_file):
        """LF file + new_content with \\r\\n → result is consistently LF."""
        # Convert the temp CRLF file to LF by re-reading and re-writing
        import tempfile, os
        with open(temp_pawn_file, 'rb') as f:
            data = f.read()
        lf_data = data.replace(b'\r\n', b'\n')
        with open(temp_pawn_file, 'wb') as f:
            f.write(lf_data)

        sha = stat_file(temp_pawn_file)["sha256"]
        assert stat_file(temp_pawn_file)["lineEnding"] == "LF"

        new_content = "// CRLF input\r\n// Another CRLF\r\n"
        result = replace_range(temp_pawn_file, 1, 2, new_content, sha)
        assert result["success"] is True
        assert result["lineEnding"] == "LF"

        raw = _raw_bytes(temp_pawn_file)
        issues = validate_line_ending_consistency(raw, "LF")
        assert issues == [], f"CR in LF file: {issues}"

    def test_mixed_input_normalizes_cleanly(self, temp_multi_symbol_file):
        """new_content with mixed \\r\\n and \\n → result is consistently the file's style."""
        sha = stat_file(temp_multi_symbol_file)["sha256"]
        # Deliberately mixed line endings in input
        new_content = (
            "// Mixed start\r\n"
            "// Plain LF line\n"
            "// Another CRLF\r\n"
            "// Final line\n"
        )
        result = replace_range(
            temp_multi_symbol_file, 9, 11, new_content, sha
        )
        assert result["success"] is True
        assert result["lineEnding"] == "CRLF"

        raw = _raw_bytes(temp_multi_symbol_file)
        issues = validate_line_ending_consistency(raw, "CRLF")
        assert issues == [], f"Mixed line endings after normalization: {issues}"

    def test_cp1252_characters_survive(self, temp_pawn_file):
        """Spanish chars in new_content survive the round trip."""
        sha = stat_file(temp_pawn_file)["sha256"]
        new_content = "// Café con leche y ñoquis\r\n"
        result = replace_range(temp_pawn_file, 1, 1, new_content, sha)
        assert result["success"] is True

        content = read_range(temp_pawn_file, 1, 12)["content"]
        assert "Café" in content
        assert "leche" in content
        assert "ñoquis" in content
        # Also verify existing Spanish chars untouched
        assert "Contraseña" in content
        assert "Acción" in content

    def test_sanity_check_blocks_mixed_endings(self, temp_pawn_file):
        """Post-write sanity check: manually inject mixed endings and
        verify validation catches them before the file is written."""
        sha = stat_file(temp_pawn_file)["sha256"]

        # Read raw bytes, manually splice bare LF into CRLF data
        data = _raw_bytes(temp_pawn_file)
        # Replace a portion with a version that has bare LF
        mixed = data.replace(b"\r\n", b"\n")  # simulate someone bypassing normalization

        # Write the mixed data directly to disk (bypass tool)
        with open(temp_pawn_file, 'wb') as f:
            f.write(mixed)

        # Now the file has inconsistent line endings vs what stat would report
        # stat_file re-detects, so it would say LF now.  The real defense
        # is when the tool writes and the sanity check fires.  We test
        # that by calling validate_line_ending_consistency directly.
        raw_after = _raw_bytes(temp_pawn_file)
        detected = detect_line_endings(raw_after)
        issues = validate_line_ending_consistency(raw_after, "CRLF")
        # If we turned everything to LF, detection should return LF
        # and validate against "LF" should be clean
        assert detect_line_endings(raw_after) == "LF"
        issues_vs_lf = validate_line_ending_consistency(raw_after, "LF")
        assert issues_vs_lf == []

        # Now write a file with truly mixed endings (some CRLF, some bare LF)
        truly_mixed = b"// CRLF line\r\n#include <a_samp>\n\nmain()\r\n{\r\n    return 1;\n}\r\n"
        issues_mixed = validate_line_ending_consistency(truly_mixed, "CRLF")
        assert len(issues_mixed) > 0
        assert "Bare LF" in issues_mixed[0]


class TestReplaceRangeBoundary:
    """Exact boundary tests — 1-indexed → 0-indexed conversion correctness."""

    def test_exact_five_line_boundary(self, tmp_path):
        """replace_range(startLine=2, endLine=3) on a 5-line file
        must produce [L1, X, Y, L4, L5] — L1/L4/L5 untouched."""
        import tempfile
        content = "L1\nL2\nL3\nL4\nL5\n"
        path = tmp_path / "five.pwn"
        path.write_text(content, encoding="cp1252")

        from tools.stat import stat_file
        from tools.read_range import read_range
        from tools.replace_range import replace_range

        sha = stat_file(str(path))["sha256"]
        new_content = "X\nY\n"
        result = replace_range(str(path), 2, 3, new_content, sha)
        assert result["success"] is True

        # Read back and verify exact content
        full = read_range(str(path), 1, 5)["content"]
        assert full == "L1\nX\nY\nL4\nL5\n", f"Unexpected content: {full!r}"

        # Verify context lines in response
        assert result.get("linesBeforeContext") == ["L1"]
        assert result.get("linesAfterContext") == ["L4", "L5"]

    def test_brace_before_range_survives(self, tmp_path):
        """A '{' immediately before the replaced range MUST survive untouched."""
        import tempfile
        content = "line1\n{\nline3\nline4\nline5\nline6\n"
        path = tmp_path / "brace.pwn"
        path.write_text(content, encoding="cp1252")

        from tools.stat import stat_file
        from tools.read_range import read_range
        from tools.replace_range import replace_range

        sha = stat_file(str(path))["sha256"]

        # Replace lines 3-4 — line 2 (the '{') must survive.
        result = replace_range(str(path), 3, 4, "NEW3\nNEW4\n", sha)
        assert result["success"] is True

        full = read_range(str(path), 1, 6)["content"]
        assert full == "line1\n{\nNEW3\nNEW4\nline5\nline6\n", f"Brace not preserved: {full!r}"

        # Verify context confirms the brace was untouched
        assert result.get("linesBeforeContext") == ["line1", "{"]
        assert result.get("linesAfterContext") == ["line5", "line6"]


class TestReplaceRangeDryRun:
    """dry_run=True tests — preview without mutation."""

    def test_dry_run_no_file_mutation(self, tmp_path):
        """dry_run=True must NOT write to disk or change mtime."""
        import tempfile, os
        content = "L1\nL2\nL3\nL4\nL5\n"
        path = tmp_path / "dry.pwn"
        path.write_text(content, encoding="cp1252")

        from tools.stat import stat_file
        from tools.replace_range import replace_range

        sha = stat_file(str(path))["sha256"]
        mtime_before = os.path.getmtime(str(path))

        result = replace_range(str(path), 2, 3, "X\nY\n", sha, dry_run=True)
        assert result["success"] is True
        assert result["dryRun"] is True

        # File must be untouched
        mtime_after = os.path.getmtime(str(path))
        assert mtime_after == mtime_before, "File was modified during dry_run!"
        assert path.read_text(encoding="cp1252") == content, "File content changed during dry_run!"

        # Preview must accurately describe the operation
        preview = result["preview"]
        assert preview["linesBefore"] == ["L1"]
        assert preview["linesToBeReplaced"] == [
            {"lineNumber": 2, "content": "L2"},
            {"lineNumber": 3, "content": "L3"},
        ]
        assert preview["linesAfter"] == ["L4", "L5"]
        assert preview["newContentPreview"] == "X\nY\n"

    def test_dry_run_preserves_file_after_real_write(self, tmp_path):
        """After a real write, dry_run on the updated file shows new state."""
        import tempfile
        content = "A\nB\nC\nD\nE\n"
        path = tmp_path / "dry2.pwn"
        path.write_text(content, encoding="cp1252")

        from tools.stat import stat_file
        from tools.replace_range import replace_range

        # Real write: replace lines 2-3 with "X\n"
        sha1 = stat_file(str(path))["sha256"]
        r1 = replace_range(str(path), 2, 3, "X\n", sha1)
        assert r1["success"] is True

        # dry_run on updated file should show shifted line numbers
        sha2 = stat_file(str(path))["sha256"]
        r2 = replace_range(str(path), 2, 2, "Y\n", sha2, dry_run=True)
        assert r2["success"] is True
        assert r2["dryRun"] is True
        # After first edit: A, X, D, E — line 2 is now "X"
        assert r2["preview"]["linesToBeReplaced"] == [
            {"lineNumber": 2, "content": "X"},
        ]
        assert r2["preview"]["linesBefore"] == ["A"]
        assert r2["preview"]["linesAfter"] == ["D", "E"]
