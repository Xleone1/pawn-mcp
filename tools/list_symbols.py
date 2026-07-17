"""
list_symbols MCP tool.

Lightweight Pawn symbol index using heuristic line-by-line matching.
No full parser — just regex patterns that cover the common Pawn idiom.
"""

import logging
import os
import re

from config import max_search_results
from tools.errors import success, error, FILE_NOT_FOUND, INTERNAL_ERROR

logger = logging.getLogger(__name__)

# ── Heuristic patterns (order matters — first match wins per line) ───

# Pre-compiled regexes; each returns (name, kind, signature) groups.
# Patterns are tried in order; the first match per line wins.

_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # forward Name(args);
    ("forward", "forward", re.compile(
        r"^\s*forward\s+(\w+)\s*\(([^;]*)\)\s*;",
        re.IGNORECASE,
    )),
    # #define NAME ...   (possibly multiline continuation via \)
    ("macro", "macro", re.compile(
        r"^\s*#define\s+(\w+)\b(.*)",
    )),
    # public/stock/static function:  public Name(args)
    # Supports tag return types: stock Float:Name(...), static bool:Name(...)
    ("function", "function", re.compile(
        r"^\s*(?:public|stock|static\s+stock|static)\s+(?:\w+:\s*)*(\w+)\s*\(([^)]*)\)",
    )),
    # enum Name {  or  enum Name (<<= ...) {
    ("enum", "enum", re.compile(
        r"^\s*enum\s+(\w+)\b",
    )),
    # new variable declaration:  new Name[...] or new Name = or new Name;
    # Also: new const, static const, static
    ("variable", "variable", re.compile(
        r"^\s*(?:new(?:\s+const)?|static(?:\s+const)?)\s+(\w[\w.]*)",
    )),
]


def _scan_symbols(lines: list[str]) -> list[dict]:
    """Scan raw lines and produce a list of symbol dictionaries."""
    symbols: list[dict] = []
    # Track line index (0-based) for continuation detection
    for i, line in enumerate(lines):
        for kind_id, kind_label, pat in _PATTERNS:
            m = pat.match(line)
            if m:
                name = m.group(1)
                # Build a clean signature: the full matched line, stripped
                sig = line.strip()
                # For macros with continuation, stitch them
                if kind_id == "macro" and sig.endswith("\\"):
                    j = i + 1
                    while j < len(lines):
                        continuation = lines[j].strip()
                        sig = sig.rstrip("\\").rstrip() + " " + continuation
                        if not continuation.endswith("\\"):
                            break
                        j += 1

                symbols.append({
                    "name": name,
                    "kind": kind_label,
                    "line": i + 1,  # 1-indexed
                    "signature": sig,
                })
                break  # one match per line

    return symbols


def list_symbols(
    path: str,
    kind: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> dict:
    """
    Produce a paginated symbol table for a Pawn file.

    Args:
        path: Path to the .pwn/.inc file.
        kind: Optional filter: "function", "forward", "macro", "variable", "enum".
        limit: Max symbols to return (default: PAWN_MCP_MAX_SEARCH_RESULTS).
        offset: 0-indexed pagination offset.

    Returns:
        { success, symbols: [...], totalSymbols, limit, offset, hasMore }
    """
    logger.info(
        f"[list_symbols] {path} kind={kind} limit={limit} offset={offset}"
    )

    # ── Validate kind ────────────────────────────────────────────────
    valid_kinds = {"function", "forward", "macro", "variable", "enum"}
    if kind is not None and kind not in valid_kinds:
        return error(
            "INVALID_ARGUMENT",
            f"Unknown kind '{kind}'. Valid: {', '.join(sorted(valid_kinds))}",
        )

    if limit is None:
        limit = max_search_results()

    if offset < 0:
        offset = 0

    # ── Read the file line-by-line ───────────────────────────────────
    try:
        with open(path, "r", encoding="cp1252") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied: {path}")
    except UnicodeDecodeError as e:
        return error("ENCODING_ERROR", f"Failed to decode as Windows-1252: {e}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to read file: {e}")

    # ── Scan for symbols ─────────────────────────────────────────────
    all_symbols = _scan_symbols(lines)

    # ── Filter by kind if requested ──────────────────────────────────
    if kind is not None:
        all_symbols = [s for s in all_symbols if s["kind"] == kind]

    total = len(all_symbols)

    # ── Paginate ─────────────────────────────────────────────────────
    page = all_symbols[offset : offset + limit]
    has_more = (offset + limit) < total

    logger.info(
        f"[list_symbols] OK: {total} symbols total, "
        f"returning {len(page)} (offset={offset})"
    )

    return success(
        symbols=page,
        totalSymbols=total,
        limit=limit,
        offset=offset,
        hasMore=has_more,
    )
