"""Unit tests for deterministic scope verification boundary (policies/scope_verifier.py)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.policies.scope_verifier import (
    verify_scope_file,
    ScopeVerification,
)


class CantinaScopeVerifierTestCase(unittest.TestCase):
    """Test suite evaluating scope verification invariants and boundary defenses."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_trusted_digest_matches_scope(self):
        scope_path = self.test_dir / "scope.md"
        content = b"# Authorized Cantina Scope\n- Contract: 0x12345678901234567890\n"
        scope_path.write_bytes(content)

        trusted_sha = hashlib.sha256(content).hexdigest()
        result = verify_scope_file(scope_path, trusted_sha)

        self.assertIsInstance(result, ScopeVerification)
        self.assertTrue(result.verified)
        self.assertEqual(result.computed_sha256, trusted_sha)
        self.assertEqual(result.expected_sha256, trusted_sha)
        self.assertEqual(result.reason, "Digest matched.")

    def test_scope_digest_mismatch_fails_closed(self):
        scope_path = self.test_dir / "scope.md"
        scope_path.write_bytes(b"authorized target A")

        wrong_digest = hashlib.sha256(b"authorized target B").hexdigest()
        result = verify_scope_file(scope_path, wrong_digest)

        self.assertFalse(result.verified)
        self.assertNotEqual(result.computed_sha256, wrong_digest)
        self.assertIn("does not match", result.reason)

    def test_missing_scope_file_fails_closed(self):
        non_existent = self.test_dir / "non_existent_scope.md"
        valid_looking_sha = "0" * 64
        result = verify_scope_file(non_existent, valid_looking_sha)

        self.assertFalse(result.verified)
        self.assertIn("missing or unreadable", result.reason)

    def test_malformed_trusted_digest_fails_closed(self):
        scope_path = self.test_dir / "scope.md"
        scope_path.write_bytes(b"some content")

        malformed_digests = [
            "tooshort",
            "g" * 64,  # non-hex
            " " * 64,
            "",
            "12345",
        ]
        for bad_sha in malformed_digests:
            result = verify_scope_file(scope_path, bad_sha)
            self.assertFalse(result.verified, f"Malformed digest '{bad_sha}' should have failed")
            self.assertIn("Invalid trusted SHA-256", result.reason)

    def test_directory_as_scope_path_fails_closed(self):
        dir_path = self.test_dir / "not_a_file"
        dir_path.mkdir()
        result = verify_scope_file(dir_path, "a" * 64)

        self.assertFalse(result.verified)
        self.assertIn("missing or unreadable", result.reason)


if __name__ == "__main__":
    unittest.main()
