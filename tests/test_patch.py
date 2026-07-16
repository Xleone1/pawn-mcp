"""
Tests for apply_patch tool.
"""

import hashlib
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.read import read_pawn_file
from tools.patch import apply_patch


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
