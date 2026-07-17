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
import re

from tools.errors import (
    success, error,
    FILE_NOT_FOUND, SYMBOL_NOT_FOUND, AMBIGUOUS_SYMBOL,
    INTERNAL_ERROR,
)

logger = logging.getLogger(__name__)


# ── Symbol locator ───────────────────────────────────────────────────

def _find_all_matching(
    lines: list[str], symbol: str
) -> list[tuple[int, str, str]]:
    """
    Scan *lines* and return every position where *symbol* appears as a
    declarable name.  Returns list of (line_number, kind, matched_line).
    """
    candidates: list[tuple[int, str, str]] = []
    esc = re.escape(symbol)

    pat_forward = re.compile(rf"^\s*forward\s+({esc})\s*\([^;]*\)\s*;", re.I)
    pat_func = re.compile(
        rf"^\s*(?:public|stock|static\s+stock|static)\s+(?:\w+:\s*)*({esc})\s*\([^)]*\)",
    )
    pat_macro = re.compile(rf"^\s*#define\s+({esc})\b")
    pat_var = re.compile(
        rf"^\s*(?:new(?:\s+const)?|static(?:\s+const)?)\s+({esc})\b",
    )
    pat_enum = re.compile(rf"^\s*enum\s+({esc})\b")

    for i, line in enumerate(lines):
        if m := pat_forward.match(line):
            candidates.append((i + 1, "forward", line.strip()))
        elif m := pat_func.match(line):
            candidates.append((i + 1, "function", line.strip()))
        elif m := pat_macro.match(line):
            sig = line.strip()
            if sig.endswith("\\"):
                j = i + 1
                while j < len(lines):
                    cont = lines[j].strip()
                    sig = sig.rstrip("\\").rstrip() + " " + cont
                    if not cont.endswith("\\"):
                        break
                    j += 1
            candidates.append((i + 1, "macro", sig))
        elif m := pat_enum.match(line):
            candidates.append((i + 1, "enum", line.strip()))
        elif m := pat_var.match(line):
            candidates.append((i + 1, "variable", line.strip()))

    return candidates


# ── Brace matching ───────────────────────────────────────────────────

def _find_matching_brace(lines: list[str], start_idx: int) -> int | None:
    """
    Starting from *start_idx* (0-indexed), find the matching '}' for
    the first '{' encountered.

    Returns 0-indexed line of the matching '}', or None.
    """
    search_from = start_idx
    while search_from < len(lines):
        stripped = lines[search_from].strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            search_from += 1
            continue
        if "{" in lines[search_from]:
            brace_line = search_from
            break
        search_from += 1
    else:
        return None

    # Count braces starting from the first '{' on brace_line
    rest = lines[brace_line]
    idx = rest.index("{")
    depth = 0

    for li in range(brace_line, len(lines)):
        line = lines[li]
        start_col = idx if li == brace_line else 0
        for ci in range(start_col, len(line)):
            ch = line[ci]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return li

    return None


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
    candidates = _find_all_matching(lines, symbol)

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
    start_line = cand_line
    end_line = cand_line

    # ── Resolve body ────────────────────────────────────────────────
    if cand_kind == "function":
        closing = _find_matching_brace(lines, cand_line - 1)
        if closing is not None:
            end_line = closing + 1
        body = _join_range(lines, start_line, end_line, sep)

    elif cand_kind == "forward":
        body = lines[cand_line - 1]

    elif cand_kind == "macro":
        # cand_sig is already fully stitched from _find_all_matching,
        # but we need the physical line extent from the original file.
        body = cand_sig
        i = cand_line - 1
        end_line = cand_line
        line_i = lines[i].rstrip("\r")
        while line_i.endswith("\\") and i + 1 < total_lines:
            i += 1
            end_line = i + 1
            line_i = lines[i].rstrip("\r")

    elif cand_kind == "variable":
        body_lines = [lines[cand_line - 1]]
        i = cand_line
        while i < total_lines:
            if ";" in body_lines[-1]:
                break
            i += 1
            body_lines.append(lines[i - 1])
            if len(body_lines) > 10:
                break
        end_line = i
        body = sep.join(body_lines)

    elif cand_kind == "enum":
        closing = _find_matching_brace(lines, cand_line - 1)
        if closing is not None:
            end_line = closing + 1
        body = _join_range(lines, start_line, end_line, sep)

    else:
        body = lines[cand_line - 1]

    # ── Context ─────────────────────────────────────────────────────
    ctx_before_start = max(1, start_line - 5)
    ctx_before = _join_range(
        lines, ctx_before_start, max(1, start_line - 1), sep
    )

    ctx_after_end = min(total_lines, end_line + 5)
    ctx_after = _join_range(lines, end_line + 1, ctx_after_end, sep)

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


# ── Internal helper ──────────────────────────────────────────────────

def _join_range(lines: list[str], start: int, end: int, sep: str) -> str:
    """Join line slice [start-1 : end] with *sep*."""
    if start > end:
        return ""
    return sep.join(lines[start - 1 : end])


    for li in range(brace_line, len(lines)):
        line = lines[li]
        start_col = idx if li == brace_line else 0
        for ci in range(start_col, len(line)):
            ch = line[ci]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return li

    return None
