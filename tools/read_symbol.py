"""
read_symbol MCP tool.

Returns the body of a Pawn symbol (function, forward, macro, variable,
enum) with surrounding context.  Uses brace-matching for functions,
continuation stitching for macros, and line-length heuristics for
variables/enums.

When multiple symbols share the same name, returns AMBIGUOUS_SYMBOL
with a candidate list and instructs the caller to disambiguate.
"""

import logging

from tools._symbol_utils import (
    find_all_matching,
    resolve_symbol_extent,
    join_range,
)
from tools.errors import (
    success, error,
    FILE_NOT_FOUND, SYMBOL_NOT_FOUND, AMBIGUOUS_SYMBOL,
    INTERNAL_ERROR,
)

logger = logging.getLogger(__name__)


# ── Main tool ───────────────────────────────────────────────────────

def read_symbol(path: str, symbol: str) -> dict:
    """
    Read the full definition of *symbol* from *path*.

    Args:
        path: Path to the .pwn/.inc file.
        symbol: The symbol name to look up.

    Returns:
        { success, symbol: { name, kind, startLine, endLine, signature,
            body, contextBefore, contextAfter } }
    """
    logger.info(f"[read_symbol] {path} :: {symbol}")

    # ── Read file ───────────────────────────────────────────────────
    try:
        with open(path, "r", encoding="cp1252") as f:
            text = f.read()
    except FileNotFoundError:
        return error(FILE_NOT_FOUND, f"File not found: {path}")
    except PermissionError:
        return error("PERMISSION_DENIED", f"Permission denied: {path}")
    except UnicodeDecodeError as e:
        return error("ENCODING_ERROR", f"Failed to decode as Windows-1252: {e}")
    except OSError as e:
        return error(INTERNAL_ERROR, f"Failed to read file: {e}")

    # Detect line endings
    if "\r\n" in text:
        sep = "\r\n"
        le = "CRLF"
    elif "\r" in text:
        sep = "\r"
        le = "CR"
    else:
        sep = "\n"
        le = "LF"

    lines = text.split(sep)
    if text.endswith(sep) and lines and lines[-1] == "":
        lines.pop()

    total_lines = len(lines)

    # ── Find candidates ─────────────────────────────────────────────
    candidates = find_all_matching(lines, symbol)

    if not candidates:
        return error(
            SYMBOL_NOT_FOUND,
            f"Symbol '{symbol}' not found in {path}",
            symbol=symbol,
        )

    # ── Ambiguity ───────────────────────────────────────────────────
    if len(candidates) > 1:
        return error(
            AMBIGUOUS_SYMBOL,
            f"Multiple symbols named '{symbol}' found.",
            symbol=symbol,
            candidates=[
                {"line": ln, "kind": k} for ln, k, _ in candidates
            ],
        )

    cand_line, cand_kind, cand_sig = candidates[0]

    # ── Resolve extent and body ─────────────────────────────────────
    start_line, end_line = resolve_symbol_extent(lines, cand_line, cand_kind)

    if cand_kind in ("function", "enum"):
        body = join_range(lines, start_line, end_line, sep)
    elif cand_kind == "forward":
        body = lines[cand_line - 1]
    elif cand_kind == "macro":
        body = cand_sig  # already stitched by find_all_matching
    elif cand_kind == "variable":
        body = join_range(lines, start_line, end_line, sep)
    else:
        body = lines[cand_line - 1]

    # ── Context ─────────────────────────────────────────────────────
    ctx_before_start = max(1, start_line - 5)
    ctx_before = join_range(
        lines, ctx_before_start, max(1, start_line - 1), sep
    )

    ctx_after_end = min(total_lines, end_line + 5)
    ctx_after = join_range(lines, end_line + 1, ctx_after_end, sep)

    logger.info(
        f"[read_symbol] OK: {symbol} ({cand_kind}) L{start_line}-{end_line}"
    )

    return success(
        symbol=dict(
            name=symbol,
            kind=cand_kind,
            startLine=start_line,
            endLine=end_line,
            signature=cand_sig,
            body=body,
            contextBefore=ctx_before,
            contextAfter=ctx_after,
        ),
        lineEnding=le,
        encoding="windows-1252",
    )
