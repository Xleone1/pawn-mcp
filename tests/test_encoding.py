"""
Tests for encoding.py — Windows-1252 encoding utilities.

Verifies that Spanish characters survive CP1252 round-trips
and that line endings are properly detected and preserved.
"""

import hashlib
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from encoding import (
    decode_cp1252,
    encode_cp1252,
    EncodingError,
    detect_line_endings,
    compute_sha256,
    preserve_line_endings,
    has_utf8_bom,
    validate_cp1252,
)
from tests.helpers import make_cp1252_file, SPANISH_WORDS, SPANISH_PUNCTUATION


class TestSpanishCharacters:
    """Verify that Spanish characters round-trip cleanly through CP1252."""

    @pytest.mark.parametrize('word', SPANISH_WORDS)
    def test_roundtrip_word(self, word):
        """Each Spanish test word must survive encode -> decode unchanged."""
        encoded = word.encode('cp1252')
        decoded = encoded.decode('cp1252')
        assert decoded == word, f"Round-trip failed for: {word}"

    def test_contraseña_bytes(self):
        """Contraseña must produce the exact expected CP1252 bytes."""
        word = "Contraseña"
        raw = word.encode('cp1252')
        # 'ñ' is 0xF1 in CP1252
        assert raw == b'Contrase\xf1a', f"Unexpected bytes: {raw.hex()}"

    def test_spanish_punctuation(self):
        """¿ and ¡ must be encoded correctly."""
        text = SPANISH_PUNCTUATION
        raw = text.encode('cp1252')
        decoded = raw.decode('cp1252')
        assert decoded == text
        # ¿ = 0xBF, ¡ = 0xA1
        assert b'\xbf' in raw  # ¿
        assert b'\xa1' in raw  # ¡

    def test_all_vowels_with_accents(self):
        """All accented vowels must round-trip."""
        vowels = "áéíóúÁÉÍÓÚ"
        raw = vowels.encode('cp1252')
        decoded = raw.decode('cp1252')
        assert decoded == vowels

    def test_ene(self):
        """ñ and Ñ must round-trip."""
        enies = "ñÑ"
        raw = enies.encode('cp1252')
        assert raw == b'\xf1\xd1'
        assert raw.decode('cp1252') == enies


class TestLineEndings:
    """Verify line ending detection and preservation."""

    def test_detect_crlf(self):
        data = b'line1\r\nline2\r\n'
        assert detect_line_endings(data) == 'CRLF'

    def test_detect_lf(self):
        data = b'line1\nline2\n'
        assert detect_line_endings(data) == 'LF'

    def test_detect_cr(self):
        data = b'line1\rline2\r'
        assert detect_line_endings(data) == 'CR'

    def test_preserve_crlf_to_lf(self):
        text = 'line1\r\nline2\r\n'
        result = preserve_line_endings(text, 'LF')
        assert result == 'line1\nline2\n'

    def test_preserve_lf_to_crlf(self):
        text = 'line1\nline2\n'
        result = preserve_line_endings(text, 'CRLF')
        assert result == 'line1\r\nline2\r\n'

    def test_preserve_mixed_to_crlf(self):
        text = 'a\r\nb\nc\r\nd'
        result = preserve_line_endings(text, 'CRLF')
        assert result == 'a\r\nb\r\nc\r\nd'


class TestEncode:
    """Verify CP1252 encoding enforces valid characters."""

    def test_valid_string_encodes(self):
        text = "Hello, contraseña!"
        result = encode_cp1252(text)
        assert isinstance(result, bytes)
        assert result.decode('cp1252') == text

    def test_unsupported_unicode_fails(self):
        """Characters not in CP1252 must raise EncodingError."""
        text = "Hello α world"  # Greek alpha, NOT in CP1252
        with pytest.raises(EncodingError) as exc_info:
            encode_cp1252(text)
        assert 'U+03B1' in str(exc_info.value)

    def test_unsupported_unicode_never_replaced(self):
        """Verify that unsupported characters are NOT replaced with ? or FFFD."""
        text = "Test α"  # Greek alpha, NOT in CP1252
        with pytest.raises(EncodingError):
            encode_cp1252(text)

    def test_multiple_unsupported_characters(self):
        """Multiple bad characters should each be reported."""
        text = "α test 😀"  # Greek alpha and emoji, NOT in CP1252
        with pytest.raises(EncodingError) as exc:
            encode_cp1252(text)
        assert exc.value.issues is not None
        assert len(exc.value.issues) >= 2

    def test_encode_all_spanish_chars(self):
        """Encode function must handle all Spanish chars."""
        text = " ".join(SPANISH_WORDS) + " " + SPANISH_PUNCTUATION
        result = encode_cp1252(text)
        # No exception means success
        assert result.decode('cp1252') == text


class TestValidate:
    """Verify CP1252 validation."""

    def test_valid_cp1252_passes(self):
        data = "Contraseña\r\n".encode('cp1252')
        result = validate_cp1252(data)
        assert result.valid
        assert result.encoding == 'windows-1252'
        assert result.line_ending == 'CRLF'
        assert not result.has_bom

    def test_utf8_bom_detected(self):
        data = b'\xef\xbb\xbf' + "hello".encode('cp1252')
        result = validate_cp1252(data)
        assert not result.valid
        assert result.has_bom
        assert any('BOM' in issue.description for issue in result.issues)

    def test_sha256_computed(self):
        data = b'test data'
        sha = compute_sha256(data)
        expected = hashlib.sha256(data).hexdigest()
        assert sha == expected
        assert len(sha) == 64


class TestBytesPreservation:
    """Verify that unmodified bytes remain identical after decode->encode."""

    def test_roundtrip_preserves_bytes(self, pawn_source_bytes):
        """Full file round-trip must preserve every byte."""
        decoded = decode_cp1252(pawn_source_bytes)
        reencoded = encode_cp1252(decoded)
        assert reencoded == pawn_source_bytes, "Bytes changed during round-trip!"

    def test_partial_file_modification(self):
        """
        When modifying only part of a file, the unmodified regions
        must produce identical bytes.
        """
        original = "line1\r\nline2 Contraseña\r\nline3\r\n"
        raw = original.encode('cp1252')
        decoded = raw.decode('cp1252')

        # Modify only line2
        modified = decoded.replace('line2', 'changed')
        reencoded = modified.encode('cp1252')

        # "Contraseña" bytes on line 2 should still be intact
        assert b'Contrase\xf1a' in reencoded
        # Line endings preserved
        assert b'\r\n' in reencoded
