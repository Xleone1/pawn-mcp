# pawn-mcp

MCP Server for Safe Editing of Pawn/Open.MP Projects with Windows-1252 (CP1252).

**Phase 1 — Lightweight Semantic Navigation for Large Codebases.**

## Why?

Pawn/Open.MP projects store source files (.pwn, .inc) in **Windows-1252 (CP1252)**.
Coding agents that assume UTF-8 will permanently corrupt these files — Spanish
characters like á, é, í, ó, ú, ñ, ¿, ¡ get destroyed.

**pawn-mcp** treats Pawn files as a lightweight language server, not a text editor.
Instead of transferring entire files, it answers *semantic questions*:
- What symbols are in this file?
- Show me the definition of `OnPlayerConnect`.
- What's on lines 100–150?

This minimizes LLM context usage — critical for large gamemodes (5–20 MB).

## Design Philosophy

```
              ┌──────────────────────────────────────┐
              │         Pawn-MCP (LSP-lite)          │
              │                                      │
              │  stat_file()     "Metadata only"     │
              │  list_symbols()  "What's here?"      │
              │  read_symbol()   "Show me X"         │
              │  read_range()    "Show lines N-M"    │
              │  apply_string_patch() "Edit this"    │
              │  apply_patch()   "Diff fallback"     │
              │  verify_encoding()"Diagnose"         │
              └──────────────────────────────────────┘
```

**Never transfer full file contents for large files.** `read_pawn_file` refuses
files > 500 KB and directs clients to use symbol-based tools instead.

## Installation

```bash
git clone https://github.com/Xleone1/pawn-mcp.git
cd pawn-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PAWN_MCP_MAX_READ_SIZE_KB` | `500` | Max file size (KB) for `read_pawn_file` |
| `PAWN_MCP_MAX_SEARCH_RESULTS` | `50` | Default result cap for paginated tools |

## Tools

### stat_file — Metadata only, never content

Safe on any file size. Use this **first** to get the SHA-256 hash for safe writes.

```json
{ "path": "gamemodes/main.pwn" }
→ { "success": true, "sha256": "...", "sizeBytes": 2345678,
    "lineCount": 28500, "encoding": "windows-1252", "lineEnding": "CRLF" }
```

### list_symbols — Paginated symbol table

Kinds: `function`, `forward`, `macro`, `variable`, `enum`.

```json
{ "path": "gamemodes/main.pwn", "kind": "function", "limit": 20, "offset": 0 }
→ { "success": true, "symbols": [{ "name": "OnPlayerConnect", "kind": "forward",
     "line": 42, "signature": "forward OnPlayerConnect(playerid);" }],
    "totalSymbols": 342, "hasMore": true }
```

### read_symbol — Single symbol with body + context

Returns signature, body (full brace-matched body for functions, multi-line
macro continuations, complete enum blocks), plus 5 lines of context before/after.
Multiple matches → `AMBIGUOUS_SYMBOL` with candidate list.

```json
{ "path": "gamemodes/main.pwn", "symbol": "OnPlayerConnect" }
→ { "success": true,
    "symbol": { "name": "OnPlayerConnect", "kind": "function",
      "startLine": 156, "endLine": 203,
      "signature": "public OnPlayerConnect(playerid)",
      "body": "{\n    // ...\n    return 1;\n}",
      "contextBefore": "...", "contextAfter": "..." } }
```

### read_range — Line window

1-indexed, inclusive. Use sparingly — prefer `read_symbol`.

```json
{ "path": "gamemodes/main.pwn", "startLine": 150, "endLine": 220 }
→ { "success": true, "content": "...", "startLine": 150, "endLine": 220,
    "totalLines": 28500 }
```

### replace_range — Direct line-range replacement

Replace a contiguous line range without diff matching.  `new_content`
line endings are **automatically normalized** to match the file's
detected style (CRLF/LF/CR).  All bytes outside the range are preserved.

**Prefer `apply_string_patch` when possible** — it uses exact text
matching and has no line-number risk at all.  Use `replace_range` only
when you specifically need a line-anchored edit and cannot match by
exact string.

**Critical:** line numbers shift after every write.  After any
`replace_range` call, especially consecutive ones on the same file,
re-run `stat_file` / `read_range` on the target area before a second
corrective edit.  When in doubt, call with `dry_run=True` first to
preview exactly what will be touched.

```json
{ "path": "gamemodes/main.pwn", "startLine": 9, "endLine": 11,
  "new_content": "// Forward declarations replaced\\n",
  "expected_sha256": "abc123...",
  "dry_run": false }
→ { "success": true, "sha256": "...", "sizeBytes": 2345678,
    "encoding": "windows-1252", "lineEnding": "CRLF",
    "linesBeforeContext": ["// line 8 content"],
    "linesAfterContext": ["// line 12 content"] }
```

**Dry-run preview (dry_run=true):** computes the operation without
writing anything to disk, letting you sanity-check boundaries:

```json
{ "path": "gamemodes/main.pwn", "startLine": 9, "endLine": 11,
  "new_content": "// Forward declarations replaced\\n",
  "expected_sha256": "abc123...",
  "dry_run": true }
→ { "success": true, "dryRun": true,
    "preview": {
      "linesBefore": ["// line 6", "// line 7", "// line 8"],
      "linesToBeReplaced": [
        {"lineNumber": 9, "content": "forward ..."},
        {"lineNumber": 10, "content": "forward ..."},
        {"lineNumber": 11, "content": "forward ..."}
      ],
      "linesAfter": ["new gVar...", "// line 13"],
      "newContentPreview": "// Forward declarations replaced\\n"
    }
  }
```

### read_pawn_file — Full read (REFUSED > 500 KB)

```json
{ "path": "gamemodes/main.pwn" }
→ { "success": false, "errorCode": "FILE_TOO_LARGE",
    "sizeBytes": 2300000, "maxAllowedBytes": 512000,
    "suggestedTools": ["stat_file", "list_symbols", "read_symbol", "read_range"] }
```

### apply_string_patch _(preferred editing method)_

Replace text by exact string match — no line numbers required.
Because `read_symbol()` returns the exact `body` text of a symbol,
you can quote that text verbatim as `old_string`.  This eliminates
the line-counting errors common with diff-based patching.

```json
{ "path": "gamemodes/main.pwn",
  "old_string": "    printf(\"Hello World\");\n    return 1;",
  "new_string": "    printf(\"Hello Updated World\");\n    return 1;",
  "expected_sha256": "abc123...",
  "replace_all": false }
```

### apply_patch _(fallback editing method)_

Apply a unified diff.  Use `stat_file` to get the SHA-256 first.
**Prefer `apply_string_patch`** when you have the exact text from `read_symbol()`
— it avoids line-counting mistakes that cause diff mismatches.

```json
{ "path": "gamemodes/main.pwn",
  "unified_diff": "--- a/file.pwn\n+++ b/file.pwn\n@@ -1,1 +1,1 @@\n-old\n+new\n",
  "expected_sha256": "abc123..." }
```

### write_pawn_file

Full-file write with SHA-256 safety check. Aborts on non-CP1252 characters.

### verify_encoding

Diagnose encoding issues (BOM, replacement characters, round-trip failures).

## Recommended Workflow for Large Files

```
1. stat_file            → get SHA-256 and line count
2. list_symbols         → understand what's in the file
3. read_symbol("X")     → read the exact symbol you need to edit
4. apply_string_patch   → edit by quoting the exact body text from read_symbol
```

> **Note:** `apply_string_patch` is preferred over `apply_patch` because it
> matches text verbatim (exactly as returned by `read_symbol`), eliminating
> line-counting errors. Use `apply_patch` only as a fallback.

## Structured Error Codes

| Code | Meaning |
|---|---|
| `FILE_NOT_FOUND` | Path doesn't exist |
| `FILE_TOO_LARGE` | File exceeds `PAWN_MCP_MAX_READ_SIZE_KB` |
| `PERMISSION_DENIED` | Can't read/write file |
| `SHA256_MISMATCH` | File changed externally |
| `ENCODING_ERROR` | Non-CP1252 characters detected |
| `SYMBOL_NOT_FOUND` | Symbol doesn't exist in file |
| `AMBIGUOUS_SYMBOL` | Multiple symbols match (candidates provided) |
| `INVALID_RANGE` | `startLine` > `endLine`, out of bounds, etc. |
| `STRING_NOT_FOUND` | `old_string` not found in file |
| `AMBIGUOUS_MATCH` | `old_string` matches multiple locations |
| `LINE_ENDING_INCONSISTENT` | File contains mixed line endings after edit (blocked before write) |
| `INVALID_ARGUMENT` | Bad parameter value |
| `INTERNAL_ERROR` | Unexpected failure |

Every response: `{ "success": true|false, ... }`. On error: `{ "errorCode": "...", "message": "..." }`.

## Testing

```bash
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
pawn-mcp/
    server.py            # MCP server entry point (9 tools)
    config.py            # Environment variable thresholds
    encoding.py          # CP1252 encode/decode, atomic writes, SHA256
    patching.py          # Unified diff parser/applicator + string-patch
    pyproject.toml
    tools/
        __init__.py
        errors.py        # Structured error codes & response builders
        read.py          # read_pawn_file (with large-file rejection)
        stat.py          # stat_file (metadata only, streaming SHA256)
        list_symbols.py  # list_symbols (heuristic symbol table)
        read_symbol.py   # read_symbol (body + context, brace matching)
        read_range.py    # read_range (line window)
        write.py         # write_pawn_file (atomic writes)
        patch.py         # apply_patch + apply_string_patch (atomic writes)
        verify.py        # verify_encoding
    tests/
        conftest.py      # Fixtures (large file, multi-symbol, ambiguous)
        helpers.py       # Pawn source generators
        test_encoding.py
        test_read.py
        test_stat.py
        test_list_symbols.py
        test_read_symbol.py
        test_read_range.py
        test_write.py
        test_patch.py
        test_verify.py
        test_regression_p0_p1.py
```

## Safety Guarantees

| Feature | Description |
|---|---|
| **Atomic writes** | Temp file + rename. Crash mid-write → original intact. |
| **SHA-256 verification** | Every write/patch verifies hash before modifying. |
| **No replacement characters** | Non-CP1252 chars → abort with error, never silently replace. |
| **Correct column reporting** | Accurate (line, col) even in CRLF files. |
| **Line ending preservation** | CRLF/LF/CR detected and preserved. `new_content` is auto-normalized. |
| **Line-ending consistency check** | Post-edit validation: bare `\n` in CRLF files (or vice versa) is caught and blocked before write. |
| **Large-file safety** | `read_pawn_file` refuses > 500 KB. Use symbol tools. |

## Encoding Rules

- ❌ Never convert files to UTF-8
- ❌ Never add UTF-8 BOM
- ❌ Never replace characters with `?` or `U+FFFD`
- ✅ Always read as CP1252
- ✅ Always write as CP1252
- ✅ Always preserve CRLF/LF
- ✅ Always verify SHA-256 before writing
- ✅ For large files, use `stat_file` + `list_symbols` + `read_symbol`

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
