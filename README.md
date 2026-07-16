# pawn-mcp

MCP Server for Safe Editing of Pawn/Open.MP Projects with Windows-1252 (CP1252).

## Why?

Pawn/Open.MP projects store source files (.pwn, .inc) in **Windows-1252 (CP1252)**.
Coding agents that assume UTF-8 will permanently corrupt these files — Spanish
characters like á, é, í, ó, ú, ñ, ¿, ¡ get destroyed.

**pawn-mcp** solves this by providing a safe editing pipeline that:
- Reads files as CP1252
- Writes files as CP1252
- Preserves CRLF/LF line endings
- Prevents Unicode corruption via SHA-256 safety checks

## Installation

```bash
# Clone the repo
git clone https://github.com/Xleone1/pawn-mcp.git
cd pawn-mcp

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## MCP Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "pawn-mcp": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/pawn-mcp",
      "env": {
        "PYTHONPATH": "."
      },
      "disabled": false
    }
  }
}
```

Or with the venv:

```json
{
  "mcpServers": {
    "pawn-mcp": {
      "command": "/path/to/pawn-mcp/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/path/to/pawn-mcp"
    }
  }
}
```

## Tools

### read_pawn_file

Read a Pawn source file as CP1252. Returns content, encoding info,
line endings, and SHA-256 hash.

```json
{
  "path": "gamemodes/main.pwn"
}
```

### write_pawn_file

Write content to a Pawn file with SHA-256 safety check.
Aborts if the file was modified externally.
Aborts if content contains non-CP1252 characters.

```json
{
  "path": "gamemodes/main.pwn",
  "content": "// ...",
  "expected_sha256": "abc123..."
}
```

### apply_patch _(preferred editing method)_

Apply a unified diff to a Pawn file. Preserves encoding and
line endings. Only modified regions change.

```json
{
  "path": "gamemodes/main.pwn",
  "unified_diff": "--- a/file.pwn\n+++ b/file.pwn\n@@ -1,1 +1,1 @@\n-old\n+new\n",
  "expected_sha256": "abc123..."
}
```

### verify_encoding

Diagnose encoding issues in a Pawn file.

```json
{
  "path": "gamemodes/main.pwn"
}
```

## Testing

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
pawn-mcp/
    server.py         # MCP server entry point
    encoding.py       # CP1252 encode/decode, line ending detection,
                      #   atomic writes, SHA256 verification
    patching.py       # Unified diff parser and applicator
    pyproject.toml    # Project metadata
    tools/
        read.py       # read_pawn_file tool
        write.py      # write_pawn_file tool (atomic writes)
        patch.py      # apply_patch tool (atomic writes)
        verify.py     # verify_encoding tool
    tests/
        conftest.py   # Test fixtures with Spanish char test data
        helpers.py    # Shared test utilities
        test_encoding.py
        test_read.py
        test_write.py
        test_patch.py
        test_verify.py
        test_regression_p0_p1.py  # Regression tests for critical fixes
```

## Response Format

All tools return a consistent response shape:

```json
// Success
{ "success": true, "sha256": "...", "content": "...", ... }

// Error
{ "success": false, "error": true, "message": "..." }
```

The `success` key is **always** present — check it first before accessing
any other fields.

## Safety Guarantees

| Feature | Description |
|---|---|
| **Atomic writes** | Files are written to a temp file first, then atomically renamed. A crash mid-write **never** leaves a partially-written file on disk. |
| **SHA-256 verification** | Every write/patch verifies the file hash before modifying, detecting external changes (best-effort advisory lock). |
| **No replacement characters** | If content contains a character not in CP1252, the operation **aborts** with a detailed error — never silently replaces with `?` or `U+FFFD`. |
| **Correct column reporting** | Encoding errors report accurate (line, column) positions even in CRLF files — no off-by-one from counting `\r` bytes. |
| **Line ending preservation** | CRLF, LF, and CR line endings are detected and preserved through all operations. |

## Encoding Rules

- ❌ Never convert files to UTF-8
- ❌ Never add UTF-8 BOM
- ❌ Never replace characters with `?` or `U+FFFD`
- ✅ Always read as CP1252
- ✅ Always write as CP1252
- ✅ Always preserve CRLF/LF
- ✅ Always verify SHA-256 before writing

## Spanish Character CP1252 Bytes

| Char | Byte |
|------|------|
| á    | 0xE1 |
| é    | 0xE9 |
| í    | 0xED |
| ó    | 0xF3 |
| ú    | 0xFA |
| ñ    | 0xF1 |
| Ñ    | 0xD1 |
| ¿    | 0xBF |
| ¡    | 0xA1 |
| Á    | 0xC1 |
| É    | 0xC9 |
| Í    | 0xCD |
| Ó    | 0xD3 |
| Ú    | 0xDA |
