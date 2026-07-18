#!/usr/bin/env python3
"""
pawn-mcp — MCP Server for Safe Editing of Pawn/Open.MP Projects.

Provides tools to read, write, patch, and verify Pawn source files (.pwn, .inc)
while strictly preserving Windows-1252 (CP1252) encoding.

Phase 1: Lightweight semantic navigation for large codebases.
         Prefer symbol-based access (list_symbols, read_symbol) over
         full-file reads to minimize LLM context usage.

Usage:
    python server.py
    # Or via mcp CLI:
    mcp run server.py
"""

import logging
import sys
import os

# Add project root to path so tools can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

from tools.read import read_pawn_file
from tools.write import write_pawn_file
from tools.patch import apply_patch
from tools.patch import apply_string_patch_tool as apply_string_patch
from tools.verify import verify_encoding
from tools.stat import stat_file
from tools.read_range import read_range
from tools.list_symbols import list_symbols
from tools.read_symbol import read_symbol
from tools.replace_range import replace_range
from tools.replace_symbol import replace_symbol
from tools.insert_symbol import insert_after_symbol, insert_before_symbol

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger('pawn-mcp')

# ── MCP Server ───────────────────────────────────────────────────────
mcp = FastMCP(
    name="pawn-mcp",
    instructions="""
pawn-mcp is a specialized MCP server for safely navigating and editing
Pawn/Open.MP source files.  Treat it as a lightweight language server:
ask about *symbols*, not files.

All .pwn and .inc files MUST be treated as Windows-1252 (CP1252).
Never use a generic text editor for these files — always use the tools
provided here.

AVAILABLE TOOLS

  stat_file     — File metadata (SHA-256, line count, encoding) —
                  NO content. Always safe on any file size.
  list_symbols  — Paginated symbol table (functions, forwards, macros,
                  variables, enums).  Minimal context.
  read_symbol   — Full definition of a single symbol with 5-line
                  context before/after.
  read_range    — Line window (startLine..endLine).  Use sparingly.
  read_pawn_file — Full file read.  REFUSED for files > 500 KB.
  apply_string_patch — Replace by exact text match (PREFERRED editing method).
  apply_patch   — Apply a unified diff (fallback editing method).
  write_pawn_file  — Full-file write (SHA-256 gated).
  verify_encoding   — Diagnose CP1252 encoding issues.

RECOMMENDED WORKFLOW FOR LARGE FILES

  1. stat_file        → get SHA-256 and line count
  2. list_symbols     → understand what's in the file
  3. read_symbol("X") → read the exact symbol you need to edit
  4. apply_string_patch → edit by quoting the exact body text from read_symbol

IMPORTANT RULES:
  - Never convert files to UTF-8
  - Never add UTF-8 BOM
  - Always verify SHA256 before writing
  - Use apply_string_patch as the preferred editing method (no line counting needed)
  - Use apply_patch only as a fallback when you don't have the exact text from read_symbol
  - Spanish characters (á, é, í, ó, ú, ñ, ¿, ¡) must be preserved as CP1252 bytes
  - For files > 500 KB read_pawn_file will be refused — use stat_file +
    list_symbols + read_symbol instead
""",
)


# ── Tools ────────────────────────────────────────────────────────────

@mcp.tool()
def tool_read_pawn_file(path: str) -> dict:
    """
    Read a Pawn/Open.MP source file (.pwn or .inc).

    Reads the file as Windows-1252 (CP1252) and returns the content,
    encoding info, line ending style, and SHA-256 hash of the original bytes.

    IMPORTANT: Files larger than PAWN_MCP_MAX_READ_SIZE_KB (default 500 KB)
    are REFUSED.  Use stat_file + list_symbols + read_symbol instead.

    Use this tool FIRST before editing any Pawn file — you need the SHA-256
    hash for safe writes.

    Args:
        path: Absolute or relative path to the .pwn or .inc file.

    Returns:
        Dictionary with content, encoding, lineEnding, sha256, sizeBytes.
    """
    return read_pawn_file(path)


@mcp.tool()
def tool_stat_file(path: str) -> dict:
    """
    Get file metadata WITHOUT returning any content.

    Safe on files of any size.  Returns SHA-256 (needed for write/patch
    safety checks), line count, byte size, encoding, and line endings.

    Use this FIRST on any file you're about to work with — it gives you
    the SHA-256 you'll need for safe writes.

    Args:
        path: Path to the .pwn or .inc file.

    Returns:
        { success, sha256, sizeBytes, lineCount, encoding, lineEnding }
    """
    return stat_file(path)


@mcp.tool()
def tool_list_symbols(
    path: str,
    kind: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict:
    """
    List symbols (functions, forwards, macros, variables, enums) in a Pawn file.

    Provides a lightweight symbol table — the fastest way to understand
    what's in a file without reading it.  Supports pagination for very
    large files.

    Args:
        path: Path to the .pwn or .inc file.
        kind: Optional filter: "function", "forward", "macro", "variable", "enum".
        limit: Max results per page (default: 50).
        offset: Pagination offset (0-indexed).

    Returns:
        { success, symbols: [{ name, kind, line, signature }],
          totalSymbols, hasMore, limit, offset }
    """
    return list_symbols(path, kind=kind, limit=limit, offset=offset)


@mcp.tool()
def tool_read_symbol(path: str, symbol: str) -> dict:
    """
    Read the complete definition of a single symbol.

    Returns the symbol's signature, body (full function body with braces,
    multi-line macro continuation, complete enum block, etc.), plus
    5 lines of context before and after.

    If multiple symbols share the same name, returns AMBIGUOUS_SYMBOL
    with a candidate list.

    Args:
        path: Path to the .pwn or .inc file.
        symbol: The symbol name to look up.

    Returns:
        { success,
          symbol: { name, kind, startLine, endLine, signature, body,
                    contextBefore, contextAfter },
          lineEnding, encoding }
    """
    return read_symbol(path, symbol)


@mcp.tool()
def tool_read_range(path: str, startLine: int, endLine: int) -> dict:
    """
    Read a specific range of lines from a Pawn file.

    Line-based only (1-indexed, inclusive).  Use this sparingly —
    prefer read_symbol for symbol-level access when possible.

    Args:
        path: Path to the .pwn or .inc file.
        startLine: 1-indexed start line (inclusive).
        endLine: 1-indexed end line (inclusive).

    Returns:
        { success, content, startLine, endLine, totalLines,
          encoding, lineEnding }
    """
    return read_range(path, startLine, endLine)


@mcp.tool()
def tool_replace_range(
    path: str,
    startLine: int,
    endLine: int,
    new_content: str,
    expected_sha256: str,
) -> dict:
    """
    Replace a line range directly — no diff matching.

    Replaces lines [startLine..endLine] (inclusive, 1-indexed) with
    new_content.  All bytes outside the range are preserved exactly.
    CP1252 encoding and line endings are preserved.

    ``new_content`` line endings are **automatically normalized** to match
    the file's detected style (CRLF/LF/CR).  A post-write consistency check
    blocks the edit before touching disk if mixed line endings are detected.

    Prefer this over apply_patch for AI-generated replacements where
    whitespace matching is unreliable.

    Args:
        path: Path to the .pwn or .inc file.
        startLine: 1-indexed start line (inclusive).
        endLine: 1-indexed end line (inclusive).
        new_content: The replacement text (may contain line breaks; line
            endings will be normalized to match the file).
        expected_sha256: SHA-256 hash from stat_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    return replace_range(path, startLine, endLine, new_content, expected_sha256)


@mcp.tool()
def tool_replace_symbol(
    path: str,
    symbol: str,
    new_content: str,
    expected_sha256: str,
) -> dict:
    """
    Replace a symbol's body directly — no diff matching.

    Finds the symbol by name (functions, forwards, macros, variables, enums),
    determines its full extent (brace-matched for functions/enums), and
    replaces only that region.

    No whitespace-sensitive diff matching — the replacement is applied
    directly regardless of indentation differences.

    Args:
        path: Path to the .pwn or .inc file.
        symbol: The symbol name to replace.
        new_content: The new definition (may contain line breaks).
        expected_sha256: SHA-256 hash from stat_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    return replace_symbol(path, symbol, new_content, expected_sha256)


@mcp.tool()
def tool_insert_after_symbol(
    path: str,
    symbol: str,
    content: str,
    expected_sha256: str,
) -> dict:
    """
    Insert content immediately after a symbol's definition.

    Useful for adding new callbacks, functions, or helper functions
    after an existing symbol.

    Args:
        path: Path to the .pwn or .inc file.
        symbol: The symbol to insert after.
        content: The content to insert.
        expected_sha256: SHA-256 hash from stat_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    return insert_after_symbol(path, symbol, content, expected_sha256)


@mcp.tool()
def tool_insert_before_symbol(
    path: str,
    symbol: str,
    content: str,
    expected_sha256: str,
) -> dict:
    """
    Insert content immediately before a symbol's definition.

    Args:
        path: Path to the .pwn or .inc file.
        symbol: The symbol to insert before.
        content: The content to insert.
        expected_sha256: SHA-256 hash from stat_file.

    Returns:
        { success, sha256, sizeBytes, encoding, lineEnding }
    """
    return insert_before_symbol(path, symbol, content, expected_sha256)


@mcp.tool()
def tool_write_pawn_file(path: str, content: str, expected_sha256: str) -> dict:
    """
    Write content to a Pawn/Open.MP source file with CP1252 encoding.

    Performs a safety check: verifies that the file on disk still matches
    expected_sha256 before writing, preventing accidental overwrites of
    externally modified files.

    IMPORTANT:
    - Content will be encoded as Windows-1252 (CP1252).
    - If any character cannot be represented in CP1252, the write ABORTS
      with a detailed error — no replacement characters are used.
    - Original line endings (CRLF/LF) are preserved.

    Args:
        path: Path to the .pwn or .inc file.
        content: The complete new file content as a string.
        expected_sha256: SHA-256 hash from stat_file or read_pawn_file.

    Returns:
        Dictionary with success status and new SHA-256 hash.
    """
    return write_pawn_file(path, content, expected_sha256)


@mcp.tool()
def tool_apply_patch(path: str, unified_diff: str, expected_sha256: str) -> dict:
    """
    Apply a unified diff patch to a Pawn/Open.MP source file.

    This is the PREFERRED method for editing Pawn files. Instead of
    rewriting the entire file, provide a unified diff describing only
    the changes. The tool applies the patch while preserving CP1252
    encoding, line endings, and unmodified bytes.

    Safety:
    - SHA-256 check ensures no external modifications
    - CP1252 encoding is enforced — unsupported Unicode aborts the edit
    - Line endings are preserved

    Args:
        path: Path to the .pwn or .inc file.
        unified_diff: A standard unified diff string.
        expected_sha256: SHA-256 hash from stat_file or read_pawn_file.

    Returns:
        Dictionary with success status and new SHA-256 hash.
    """
    return apply_patch(path, unified_diff, expected_sha256)


@mcp.tool()
def tool_apply_string_patch(
    path: str,
    old_string: str,
    new_string: str,
    expected_sha256: str,
    replace_all: bool = False,
) -> dict:
    """
    Replace old_string with new_string in a Pawn source file by exact text match.

    This is the **PREFERRED** editing tool.  Because ``read_symbol()`` returns
    the exact ``body`` text of a symbol, you can quote that text verbatim as
    ``old_string`` without needing to count lines or generate line-number
    diffs — the match is purely textual.

    Safety:
    - SHA-256 check ensures no external modifications
    - CP1252 encoding is enforced — unsupported Unicode aborts the edit
    - Line endings are preserved

    Args:
        path: Path to the .pwn or .inc file.
        old_string: Exact text to find and replace. Must match verbatim,
            including whitespace and line endings.
        new_string: Replacement text.
        expected_sha256: SHA-256 hash from stat_file or read_pawn_file.
        replace_all: If True, replace all occurrences. If False (default),
            old_string must match exactly once or the edit is rejected.

    Returns:
        Dictionary with success status and new SHA-256 hash.
    """
    return apply_string_patch(path, old_string, new_string, expected_sha256, replace_all)


@mcp.tool()
def tool_verify_encoding(path: str) -> dict:
    """
    Verify that a file is properly encoded as Windows-1252.

    Checks:
    - File is readable
    - No UTF-8 BOM (EF BB BF)
    - No replacement characters (U+FFFD)
    - All bytes decode cleanly as CP1252
    - Round-trip: decode → encode produces identical bytes

    Use this to diagnose encoding problems in .pwn/.inc files.

    Args:
        path: Path to the file to verify.

    Returns:
        Dictionary with valid status, encoding info, and any issues found.
    """
    return verify_encoding(path)


# ── Entry Point ──────────────────────────────────────────────────────

def main():
    """Run the MCP server via stdio."""
    logger.info('[Setup] Starting pawn-mcp server...')
    mcp.run()


if __name__ == '__main__':
    main()
