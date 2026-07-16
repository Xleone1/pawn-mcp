"""
Shared test fixtures for pawn-mcp tests.

Creates temporary .pwn files with Spanish characters in CP1252 encoding.
"""

import os
import tempfile
import pytest

from tests.helpers import make_pawn_source, SPANISH_WORDS, SPANISH_PUNCTUATION  # noqa: F401 - re-exported


__all__ = ['temp_pawn_file', 'spanish_words', 'pawn_source_content', 'pawn_source_bytes']



@pytest.fixture
def temp_pawn_file():
    """
    Create a temporary .pwn file with CP1252 content including Spanish chars.
    Returns the file path.
    """
    content = make_pawn_source()
    raw = content.encode('cp1252')

    tmp = tempfile.NamedTemporaryFile(
        mode='wb', suffix='.pwn', delete=False
    )
    tmp.write(raw)
    tmp.close()

    yield tmp.name

    os.unlink(tmp.name)


@pytest.fixture
def spanish_words():
    """Return the list of Spanish test words."""
    return SPANISH_WORDS


@pytest.fixture
def pawn_source_content():
    """Return a sample Pawn source string with Spanish characters."""
    return make_pawn_source()


@pytest.fixture
def pawn_source_bytes():
    """Return sample Pawn source as CP1252 bytes (CRLF)."""
    content = make_pawn_source()
    return content.encode('cp1252')
