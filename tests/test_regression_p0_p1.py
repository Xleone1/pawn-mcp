"""
Regression tests for Priority 0 and Priority 1 fixes.

P0-1: Atomic writes prevent partial-file corruption on crash
P1-2: All tool responses include a 'success' key (standardized error shape)
P1-3: encode_cp1252 reports correct column numbers in CRLF files
P1-4: ensure_trailing_newline is correct for all line-ending combinations
"""

import hashlib
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from encoding import (
    encode_cp1252,
    EncodingError,
    ensure_trailing_newline,
    atomic_write,
    read_and_verify_sha256,
)
from tools.read import read_pawn_file
from tools.write import write_pawn_file
from tools.patch import apply_patch
from tools.verify import verify_encoding


# -- P1-2: All tool responses include 'success' key --------------------

class TestStandardizedResponses:
    """Every tool must return 'success' in every response."""

    def test_read_success_has_success_key(self, temp_pawn_file):
        result = read_pawn_file(temp_pawn_file)
        assert result['success'] is True

    def test_read_error_has_success_key(self):
        result = read_pawn_file('/nonexistent/file.pwn')
        assert result['success'] is False
        assert result['error'] is True

    def test_write_success_has_success_key(self, temp_pawn_file):
        r = read_pawn_file(temp_pawn_file)
        result = write_pawn_file(temp_pawn_file, r['content'], r['sha256'])
        assert result['success'] is True

    def test_write_error_has_success_key(self, temp_pawn_file):
        result = write_pawn_file(temp_pawn_file, 'content', '0' * 64)
        assert result['success'] is False

    def test_patch_success_has_success_key(self, temp_pawn_file):
        r = read_pawn_file(temp_pawn_file)
        diff = (
            '--- a/file.pwn\n+++ b/file.pwn\n'
            '@@ -1,3 +1,3 @@\n'
            '-// Pawn test gamemode\n'
            '+// Patched\n'
            ' #include <a_samp>\n \n'
        )
        result = apply_patch(temp_pawn_file, diff, r['sha256'])
        assert result['success'] is True

    def test_patch_error_has_success_key(self, temp_pawn_file):
        result = apply_patch(temp_pawn_file, 'garbage', '0' * 64)
        assert result['success'] is False

    def test_verify_success_has_success_key(self, temp_pawn_file):
        result = verify_encoding(temp_pawn_file)
        assert result['success'] is True
        assert result['valid'] is True

    def test_verify_error_has_success_key(self):
        result = verify_encoding('/nonexistent/file.pwn')
        assert result['success'] is False
        assert result['valid'] is False


# -- P1-3: Correct column numbers in CRLF text -------------------------

class TestCrlfColumnNumbers:
    """encode_cp1252 must report correct (line, column) for CRLF files."""

    def test_column_lf_only(self):
        """With plain LF, column is character's 1-based position."""
        text = "hello\nαworld"
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        issue = exc.value.issues[0]
        assert issue.line == 2
        assert issue.column == 1

    def test_column_crlf_file(self):
        r"""With CRLF, column must NOT count \r as a column position."""
        text = "hello\r\nαworld"
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        issue = exc.value.issues[0]
        assert issue.line == 2, f"Expected line 2, got {issue.line}"
        assert issue.column == 1, (
            f"Expected column 1, got {issue.column} — "
            f"the \\r from CRLF was incorrectly counted"
        )

    def test_column_mid_line_crlf(self):
        r"""Bad character mid-line should have correct column."""
        text = "abcαdef\r\nnext"
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        issue = exc.value.issues[0]
        assert issue.line == 1
        assert issue.column == 4

    def test_multiple_issues_crlf(self):
        r"""Multiple bad chars in CRLF file — all line/col correct."""
        text = "α\r\naαb\r\n"
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        issues = exc.value.issues
        assert len(issues) == 2
        assert issues[0].line == 1 and issues[0].column == 1
        assert issues[1].line == 2 and issues[1].column == 2

    def test_column_emoji_in_crlf(self):
        r"""Emoji — correct column."""
        text = "line1\r\nline2 😀 end"
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        issue = exc.value.issues[0]
        assert issue.line == 2
        assert issue.column == 7


# -- P0-1: Atomic write safety -----------------------------------------

class TestAtomicWrite:
    """atomic_write must preserve original on failure, write on success."""

    def test_atomic_write_preserves_content(self):
        tmp = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        tmp.write(b'original')
        tmp.close()
        try:
            atomic_write(tmp.name, b'replaced')
            with open(tmp.name, 'rb') as f:
                assert f.read() == b'replaced'
        finally:
            os.unlink(tmp.name)

    def test_atomic_write_handles_empty(self):
        tmp = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        tmp.write(b'not empty')
        tmp.close()
        try:
            atomic_write(tmp.name, b'')
            with open(tmp.name, 'rb') as f:
                assert f.read() == b''
        finally:
            os.unlink(tmp.name)


# -- P1-4: Trailing newline preservation -------------------------------

class TestTrailingNewline:
    """ensure_trailing_newline must handle all combinations correctly."""

    def test_original_has_lf_text_has_no_newline(self):
        result = ensure_trailing_newline('hello', 'hello\n', 'LF')
        assert result == 'hello\n'

    def test_original_has_lf_text_already_has_lf(self):
        result = ensure_trailing_newline('hello\n', 'hello\n', 'LF')
        assert result == 'hello\n'

    def test_original_has_no_newline(self):
        result = ensure_trailing_newline('hello', 'hello', 'LF')
        assert result == 'hello'

    def test_original_has_crlf_text_has_no_newline(self):
        result = ensure_trailing_newline('hello', 'hello\r\n', 'CRLF')
        assert result == 'hello\r\n'

    def test_original_has_crlf_text_already_has_crlf(self):
        result = ensure_trailing_newline('hello\r\n', 'hello\r\n', 'CRLF')
        assert result == 'hello\r\n'

    def test_original_has_cr_text_has_no_newline(self):
        result = ensure_trailing_newline('hello', 'hello\r', 'CR')
        assert result == 'hello\r'

    def test_idempotent(self):
        text = 'hello'
        original = 'hello\r\n'
        first = ensure_trailing_newline(text, original, 'CRLF')
        second = ensure_trailing_newline(first, original, 'CRLF')
        assert first == second


# -- P2-2: read_and_verify_sha256 utility ------------------------------

class TestReadAndVerifySha256:
    """The shared SHA256 read+verify utility works correctly."""

    def test_matching_hash_returns_data(self):
        tmp = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        tmp.write(b'test data')
        tmp.close()
        try:
            expected = hashlib.sha256(b'test data').hexdigest()
            data = read_and_verify_sha256(tmp.name, expected)
            assert data == b'test data'
        finally:
            os.unlink(tmp.name)

    def test_mismatched_hash_raises(self):
        tmp = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        tmp.write(b'test data')
        tmp.close()
        try:
            with pytest.raises(ValueError, match='SHA256 mismatch'):
                read_and_verify_sha256(tmp.name, '0' * 64)
        finally:
            os.unlink(tmp.name)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            read_and_verify_sha256('/nonexistent/file.pwn', '0' * 64)


# -- P1-3 extra: encode_cp1252 fast-path for valid text -----------------

class TestEncodeFastPath:
    """The fast path (single encode) must produce correct bytes."""

    def test_valid_spanish_text(self):
        text = "Contrase\u00f1a\r\nInformaci\u00f3n\r\n"
        result = encode_cp1252(text)
        assert result.decode('cp1252') == text

    def test_valid_ascii(self):
        result = encode_cp1252("hello world\n")
        assert result == b'hello world\n'

    def test_all_bytes_roundtrip(self):
        """All CP1252-decodable bytes must round-trip through encode_cp1252."""
        # Build the decodable CP1252 bytes (skip undefined positions)
        valid = bytearray()
        for b in range(256):
            try:
                bytes([b]).decode('cp1252')
                valid.append(b)
            except UnicodeDecodeError:
                pass  # undefined byte in CP1252, skip
        decoded = bytes(valid).decode('cp1252')
        result = encode_cp1252(decoded)
        assert result == bytes(valid)
