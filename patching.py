"""
Unified diff application for Pawn source files.

This module parses and applies unified diffs while preserving
Windows-1252 encoding and line endings.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Hunk:
    """A single hunk from a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[str] = field(default_factory=list)


@dataclass
class PatchError:
    """Structured error from patch application."""
    message: str
    hunk_index: Optional[int] = None
    line: Optional[int] = None
    context: Optional[str] = None


def parse_unified_diff(diff_text: str) -> tuple[list[Hunk], str, str]:
    """
    Parse a unified diff into hunks.

    Returns:
        (hunks, old_file, new_file)
    """
    lines = diff_text.split('\n')

    # Handle possible trailing newline in diff
    if lines and lines[-1] == '':
        lines = lines[:-1]

    hunks: list[Hunk] = []
    old_file = ''
    new_file = ''
    current_hunk: Optional[Hunk] = None

    hunk_header_re = re.compile(
        r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?$'
    )

    for line in lines:
        if line.startswith('--- '):
            old_file = line[4:].strip()
            if old_file.startswith('a/'):
                old_file = old_file[2:]
        elif line.startswith('+++ '):
            new_file = line[4:].strip()
            if new_file.startswith('b/'):
                new_file = new_file[2:]
        elif line.startswith('@@'):
            match = hunk_header_re.match(line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) is not None else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) is not None else 1
                current_hunk = Hunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                )
                hunks.append(current_hunk)
        elif current_hunk is not None:
            current_hunk.lines.append(line)

    return hunks, old_file, new_file


def apply_hunk(original_lines: list[str], hunk: Hunk) -> list[str]:
    """
    Apply a single hunk to the original content.

    Returns the modified lines or raises ValueError.
    """
    result: list[str] = []
    old_idx = hunk.old_start - 1  # Convert to 0-indexed
    new_idx = hunk.new_start - 1

    # Copy lines before the hunk
    result.extend(original_lines[:old_idx])

    # Track position in original
    orig_pos = old_idx
    expected_new_lines = hunk.new_count

    for line in hunk.lines:
        if line.startswith(' '):  # Context line
            if orig_pos >= len(original_lines):
                raise ValueError(
                    f"Context line at offset {orig_pos + 1} exceeds original file length "
                    f"({len(original_lines)} lines)"
                )
            expected = line[1:]
            actual = original_lines[orig_pos]
            # Be lenient with trailing whitespace / empty lines
            if expected.rstrip('\r') != actual.rstrip('\r'):
                raise ValueError(
                    f"Context mismatch at line {orig_pos + 1}:\n"
                    f"  Expected: {expected!r}\n"
                    f"  Actual:   {actual!r}"
                )
            result.append(original_lines[orig_pos])
            orig_pos += 1
        elif line.startswith('-'):  # Remove line
            if orig_pos >= len(original_lines):
                raise ValueError(
                    f"Cannot remove line at offset {orig_pos + 1}: "
                    f"exceeds original file length ({len(original_lines)} lines)"
                )
            expected = line[1:]
            actual = original_lines[orig_pos]
            if expected.rstrip('\r') != actual.rstrip('\r'):
                raise ValueError(
                    f"Removal mismatch at line {orig_pos + 1}:\n"
                    f"  Expected to remove: {expected!r}\n"
                    f"  Actual:             {actual!r}"
                )
            orig_pos += 1
        elif line.startswith('+'):  # Add line
            result.append(line[1:])
        # Lines starting with \ are "No newline at end of file" markers,
        # ignore them for now

    # Copy remaining original lines after the hunk
    result.extend(original_lines[orig_pos:])

    return result


def apply_unified_diff(original: str, diff_text: str) -> str:
    """
    Apply a unified diff to original content.

    Args:
        original: The original file content.
        diff_text: A unified diff string.

    Returns:
        The patched content.

    Raises:
        ValueError: If the patch cannot be applied.
    """
    # Preserve trailing newline information
    original_ends_with_newline = original.endswith('\n')

    hunks, old_file, new_file = parse_unified_diff(diff_text)

    if not hunks:
        raise ValueError("No hunks found in diff")

    # Split into lines preserving line endings
    original_lines = original.split('\n')
    # If original ends with newline, split produces an empty string at the end
    if original_ends_with_newline and original_lines and original_lines[-1] == '':
        original_lines = original_lines[:-1]

    # Track the character position for '\n' handling
    # Reconstruct lines with their original '\n' after each
    current_lines = list(original_lines)

    # Apply hunks in reverse order to maintain line offsets
    for hunk_idx, hunk in enumerate(reversed(hunks)):
        try:
            current_lines = apply_hunk(current_lines, hunk)
        except ValueError as e:
            actual_hunk_idx = len(hunks) - 1 - hunk_idx
            raise ValueError(
                f"Hunk #{actual_hunk_idx + 1} failed at line {hunk.old_start}: {e}"
            )

    # Rejoin with '\n'
    result = '\n'.join(current_lines)
    if original_ends_with_newline:
        result += '\n'

    return result
