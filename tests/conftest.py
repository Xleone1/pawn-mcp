"""
Shared test fixtures for pawn-mcp tests.

Creates temporary .pwn files with Spanish characters in CP1252 encoding.
Phase 1 additions: large-file fixture, multi-symbol fixture, ambiguous symbol fixture.
"""

import os
import tempfile
import pytest

from tests.helpers import (
    make_pawn_source,
    make_multi_symbol_source,
    make_ambiguous_source,
    SPANISH_WORDS,
    SPANISH_PUNCTUATION,
)

__all__ = [
    'temp_pawn_file',
    'temp_multi_symbol_file',
    'temp_ambiguous_file',
    'temp_large_file',
    'spanish_words',
    'pawn_source_content',
    'pawn_source_bytes',
]


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
def temp_multi_symbol_file():
    """
    Create a .pwn file with functions, forwards, macros, vars, and enums.
    """
    content = make_multi_symbol_source()
    raw = content.encode('cp1252')

    tmp = tempfile.NamedTemporaryFile(
        mode='wb', suffix='.pwn', delete=False
    )
    tmp.write(raw)
    tmp.close()

    yield tmp.name

    os.unlink(tmp.name)


@pytest.fixture
def temp_ambiguous_file():
    """
    Create a .pwn file with multiple symbols sharing the same name.
    """
    content = make_ambiguous_source()
    raw = content.encode('cp1252')

    tmp = tempfile.NamedTemporaryFile(
        mode='wb', suffix='.pwn', delete=False
    )
    tmp.write(raw)
    tmp.close()

    yield tmp.name

    os.unlink(tmp.name)


@pytest.fixture
def temp_large_file():
    """
    Create a .pwn file larger than the default 500 KB threshold.
    """
    # Generate ~510 KB of Pawn-looking content (line with new + comment)
    header = "// Large auto-generated Pawn file\r\n#include <a_samp>\r\n\r\n"
    line_template = "new gVar_{0:06d} = {0};\r\n"
    target_size = 520 * 1024  # 520 KB

    lines = [header]
    i = 0
    current_size = len(header.encode('cp1252'))
    while current_size < target_size:
        line = line_template.format(i)
        lines.append(line)
        current_size += len(line.encode('cp1252'))
        i += 1

    content = ''.join(lines)
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
