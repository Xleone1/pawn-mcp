"""
Tests for apply_patch tool.
"""

import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read import read_pawn_file
from tools.patch import apply_patch
from tools.patch import apply_string_patch_tool as apply_string_patch


class TestApplyPatch:
    """Tests for the apply_patch MCP tool."""

    def test_patch_modifies_content(self, temp_pawn_file):
        """Applying a valid patch should modify the file."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,3 @@
-// Pawn test gamemode
+// Pawn test gamemode MODIFIED
 #include <a_samp>
 
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is True

        # Verify the change
        content_after = read_pawn_file(temp_pawn_file)['content']
        assert 'MODIFIED' in content_after

    def test_patch_preserves_encoding(self, temp_pawn_file):
        """Patch must not corrupt Spanish characters."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        # Apply a patch that only changes a comment
        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,3 @@
-// Pawn test gamemode
+// Pawn test gamemode v2
 #include <a_samp>
 
"""
        apply_patch(temp_pawn_file, diff, sha)

        content = read_pawn_file(temp_pawn_file)['content']
        assert 'Contraseña' in content
        assert 'Último' in content
        assert 'Información' in content
        assert '¿' in content

    def test_patch_preserves_crlf(self, temp_pawn_file):
        """Patch must preserve CRLF line endings."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,3 @@
-// Pawn test gamemode
+// Pawn test gamemode v3
 #include <a_samp>
 
"""
        apply_patch(temp_pawn_file, diff, sha)
        result2 = read_pawn_file(temp_pawn_file)
        assert result2['lineEnding'] == 'CRLF'

    def test_patch_rejects_wrong_sha256(self, temp_pawn_file):
        """Patch with wrong SHA256 must be rejected."""
        fake_sha = '0' * 64
        diff = "--- a/f.pwn\n+++ b/f.pwn\n@@ -1,1 +1,1 @@\n-old\n+new\n"

        result = apply_patch(temp_pawn_file, diff, fake_sha)
        assert result['success'] is False

    def test_patch_fails_with_invalid_diff(self, temp_pawn_file):
        """An invalid diff should return an error."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        bad_diff = "not a valid diff"
        result = apply_patch(temp_pawn_file, bad_diff, sha)
        assert result['success'] is False

    def test_patch_add_line(self, temp_pawn_file):
        """Adding a new line via patch should work."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        content = read_result['content']

        # Find the last line before main()
        lines = content.split('\n')

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -9,6 +9,7 @@
 new gAction[32] = "Acción";
 
 new gGreeting[] = "¿Cómo estás? ¡Hola!";
+new gNewVar = 42;
 
 main()
 {
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is True

        content_after = read_pawn_file(temp_pawn_file)['content']
        assert 'new gNewVar' in content_after

    def test_patch_remove_line(self, temp_pawn_file):
        """Removing a line via patch should work."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -9,6 +9,5 @@
 new gAction[32] = "Acción";
 
 new gGreeting[] = "¿Cómo estás? ¡Hola!";
-
 main()
 {
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is True

    def test_patch_context_mismatch(self, temp_pawn_file):
        """A patch with wrong context lines should fail."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,3 @@
-// This line does not exist
+// New line
 #include <a_samp>
 
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is False


class TestHunkCountValidation:
    """Fix 1 — validate hunk header counts against actual body lines."""

    def test_mismatched_old_count_raises_and_preserves_file(self, temp_pawn_file):
        """Hunk with declared old_count=3 but only 2 context/removal lines
        must raise ValueError and leave the file unchanged."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        original_content = read_result['content']

        # This diff header claims old_count=3 but the body has only
        # 2 context/removal lines (one ' ' context line + one '-' line).
        # The actual count is 2, declared is 3.
        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,2 @@
-// Pawn test gamemode
 #include <a_samp>
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is False
        assert 'old_count mismatch' in result['message'].lower()

        # Verify the file is completely unchanged
        content_after = read_pawn_file(temp_pawn_file)['content']
        assert content_after == original_content

    def test_correct_hunk_counts_still_apply(self, temp_pawn_file):
        """A correct hunk where counts match must still apply cleanly."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        diff = """--- a/file.pwn
+++ b/file.pwn
@@ -1,3 +1,3 @@
-// Pawn test gamemode
+// Pawn test gamemode CORRECT
 #include <a_samp>
 
"""
        result = apply_patch(temp_pawn_file, diff, sha)
        assert result['success'] is True

        content_after = read_pawn_file(temp_pawn_file)['content']
        assert 'CORRECT' in content_after


class TestApplyStringPatch:
    """Fix 2 — tests for apply_string_patch (preferred editing method)."""

    def test_no_match_raises_error(self, temp_pawn_file):
        """A string not present in the file should fail cleanly."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        result = apply_string_patch(
            temp_pawn_file,
            old_string="this text does not exist in the file",
            new_string="replacement",
            expected_sha256=sha,
        )
        assert result['success'] is False
        assert 'not found' in result['message'].lower()

    def test_single_match_succeeds(self, temp_pawn_file):
        """A single, exact match should be replaced successfully."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        original_content = read_result['content']

        result = apply_string_patch(
            temp_pawn_file,
            old_string="// Pawn test gamemode",
            new_string="// Pawn test gamemode STRING PATCHED",
            expected_sha256=sha,
        )
        assert result['success'] is True

        content_after = read_pawn_file(temp_pawn_file)['content']
        assert 'STRING PATCHED' in content_after
        # Verify only one occurrence was changed
        assert content_after.count('STRING PATCHED') == 1

    def test_multiple_matches_without_replace_all_fails(self, temp_pawn_file):
        """Multiple matches without replace_all should raise an error."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']
        original_content = read_result['content']

        # 'new ' appears on multiple lines in the test file
        result = apply_string_patch(
            temp_pawn_file,
            old_string="new ",
            new_string="NEW ",
            expected_sha256=sha,
        )
        assert result['success'] is False
        assert 'match' in result['message'].lower()

        # File should be unchanged
        content_after = read_pawn_file(temp_pawn_file)['content']
        assert content_after == original_content

    def test_multiple_matches_with_replace_all_succeeds(self, temp_pawn_file):
        """Multiple matches with replace_all=True should replace all."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        # 'new ' appears on multiple lines
        result = apply_string_patch(
            temp_pawn_file,
            old_string="new ",
            new_string="NEW ",
            expected_sha256=sha,
            replace_all=True,
        )
        assert result['success'] is True

        content_after = read_pawn_file(temp_pawn_file)['content']
        # All occurrences of 'new ' should be replaced
        assert 'new ' not in content_after
        assert 'NEW ' in content_after

    def test_cp1252_characters_survive_round_trip(self, temp_pawn_file):
        """Spanish accented characters must survive the string patch unchanged."""
        read_result = read_pawn_file(temp_pawn_file)
        sha = read_result['sha256']

        # Replace a line that has multiple Spanish characters near it
        result = apply_string_patch(
            temp_pawn_file,
            old_string='new gAction[32] = "Acción";',
            new_string='new gAction[32] = "Acción Modificada";',
            expected_sha256=sha,
        )
        assert result['success'] is True

        content = read_pawn_file(temp_pawn_file)['content']
        assert 'Contraseña' in content
        assert 'Último' in content
        assert 'Información' in content
        assert 'Vehículo' in content
        assert 'Niño' in content
        assert 'Acción Modificada' in content
        assert '¿' in content
        assert '¡' in content

    def test_rejects_wrong_sha256(self, temp_pawn_file):
        """String patch with wrong SHA256 must be rejected."""
        fake_sha = '0' * 64
        result = apply_string_patch(
            temp_pawn_file,
            old_string="// Pawn test gamemode",
            new_string="// changed",
            expected_sha256=fake_sha,
        )
        assert result['success'] is False
