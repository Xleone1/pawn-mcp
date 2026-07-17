"""
Shared symbol utilities for pawn-mcp tools.

Extracted from read_symbol so that read_symbol, replace_symbol,
insert_after_symbol, and insert_before_symbol can share the same
heuristic symbol-location logic without duplication.
"""

import re


# ── Symbol locator ───────────────────────────────────────────────────

def find_all_matching(
    lines: list[str], symbol: str
) -> list[tuple[int, str, str]]:
    """
    Scan *lines* and return every position where *symbol* appears as a
    declarable name.  Returns list of (line_number, kind, signature).
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

def find_matching_brace(lines: list[str], start_idx: int) -> int | None:
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


# ── Symbol extent resolver ───────────────────────────────────────────

def resolve_symbol_extent(
    lines: list[str],
    cand_line: int,
    cand_kind: str,
) -> tuple[int, int]:
    """
    Given a symbol candidate at *cand_line* (1-indexed) with *cand_kind*,
    return the full (startLine, endLine) extent of the symbol.

    Uses brace-matching for functions/enums, line-counting for macros
    with continuations, and heuristics for variables.
    """
    total_lines = len(lines)
    start_line = cand_line
    end_line = cand_line

    if cand_kind == "function":
        closing = find_matching_brace(lines, cand_line - 1)
        if closing is not None:
            end_line = closing + 1

    elif cand_kind == "forward":
        pass  # single line

    elif cand_kind == "macro":
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

    elif cand_kind == "enum":
        closing = find_matching_brace(lines, cand_line - 1)
        if closing is not None:
            end_line = closing + 1

    return start_line, end_line


def join_range(lines: list[str], start: int, end: int, sep: str) -> str:
    """Join line slice [start-1 : end] with *sep*."""
    if start > end:
        return ""
    return sep.join(lines[start - 1 : end])
