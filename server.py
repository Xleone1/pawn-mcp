#!/usr/bin/env python3
"""
pawn-mcp — MCP Server for Safe Editing of Pawn/Open.MP Projects.

Provides tools to read, write, patch, and verify Pawn source files (.pwn, .inc)
while strictly preserving Windows-1252 (CP1252) encoding.

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
from tools.verify import verify_encoding

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
pawn-mcp is a specialized MCP server for safely editing Pawn/Open.MP source files.

All .pwn and .inc files MUST be treated as Windows-1252 (CP1252).
Never use a generic text editor for these files — always use the tools provided here.

Available tools:
  - read_pawn_file: Read a file with CP1252 encoding, get content + SHA256 hash
  - write_pawn_file: Write CP1252 content with SHA256 safety check
  - apply_patch: Apply a unified diff to a CP1252 file (PREFERRED for edits)
  - verify_encoding: Verify a file is valid CP1252

IMPORTANT RULES:
  - Never convert files to UTF-8
  - Never add UTF-8 BOM
  - Always verify SHA256 before writing
  - Use apply_patch as the preferred editing method
  - Spanish characters (á, é, í, ó, ú, ñ, ¿, ¡) must be preserved as CP1252 bytes
""",
)


# ── Tools ────────────────────────────────────────────────────────────

@mcp.tool()
def tool_read_pawn_file(path: str) -> dict:
    """
    Read a Pawn/Open.MP source file (.pwn or .inc).

    Reads the file as Windows-1252 (CP1252) and returns the content,
    encoding info, line ending style, and SHA-256 hash of the original bytes.

    Use this tool FIRST before editing any Pawn file — you need the SHA-256
    hash for safe writes.

    Args:
        path: Absolute or relative path to the .pwn or .inc file.

    Returns:
        Dictionary with content, encoding, lineEnding, sha256, sizeBytes.
    """
    return read_pawn_file(path)


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
        expected_sha256: SHA-256 hash from read_pawn_file (proves you read
                        this version and nobody else modified it).

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
        expected_sha256: SHA-256 hash from read_pawn_file.

    Returns:
        Dictionary with success status and new SHA-256 hash.
    """
    return apply_patch(path, unified_diff, expected_sha256)


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
