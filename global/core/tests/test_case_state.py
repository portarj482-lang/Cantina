import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from case_state import (
    CaseEdge,
    CaseIdentity,
    CaseNode,
    CaseState,
    CaseValidationError,
    normalized_scope_digest,
)


class CaseStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "test-bounty"
        self.root.mkdir()
        scope = "<!-- SCOPE START -->\nallowed: example\n<!-- SCOPE END -->\n"
        (self.root / "scope.md").write_text(scope, encoding="utf-8")
        scope_digest = normalized_scope_digest(self.root / "scope.md")
        (self.root / "snapshots").mkdir()
        (self.root / "snapshots" / "scope.sha256").write_text(scope_digest + "\n", encoding="utf-8")
        self.artifact = self.root / "evidence.txt"
        self.artifact.write_text("pinned evidence\n", encoding="utf-8")
        self.node = CaseNode(
            "SRC1", "SOURCE", "evidence.txt", hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        )
        self.identity = CaseIdentity("test-bounty", scope_digest)
        self.initial = CaseState(self.identity, "OPEN", 0, None, (self.node,), ())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initial_snapshot_checks_scope_and_artifact(self):
        self.initial.validate(bounty_root=self.root)
        self.artifact.write_text("changed evidence\n", encoding="utf-8")
        with self.assertRaisesRegex(CaseValidationError, "artifact digest mismatch"):
            self.initial.validate(bounty_root=self.root)

    def test_rejects_unsafe_paths_and_unhashable_ids_cleanly(self):
        unsafe = CaseState(self.identity, "OPEN", 0, None, (CaseNode("SRC1", "SOURCE", "../x", "0" * 64),))
        with self.assertRaisesRegex(CaseValidationError, "safe bounty-relative"):
            unsafe.validate()
        malformed = CaseState(self.identity, "OPEN", 0, None, (CaseNode(["bad"], "SOURCE", "x", "0" * 64),))
        with self.assertRaisesRegex(CaseValidationError, "node IDs must be strings"):
            malformed.validate()

    def test_rejects_cycles_and_duplicate_ids(self):
        second = CaseNode("TOOL1", "TOOL", "evidence.txt", self.node.sha256)
        cyclic = CaseState(
            self.identity,
            "OPEN",
            0,
            None,
            (self.node, second),
            (CaseEdge("SRC1", "TOOL1", "DERIVED_FROM"), CaseEdge("TOOL1", "SRC1", "DERIVED_FROM")),
        )
        with self.assertRaisesRegex(CaseValidationError, "contains a cycle"):
            cyclic.validate()
        duplicate = CaseState(self.identity, "OPEN", 0, None, (self.node, self.node))
        with self.assertRaisesRegex(CaseValidationError, "must be unique"):
            duplicate.validate()

    def test_successor_is_immutable_and_lineage_is_checked(self):
        stable = self.initial.successor(phase="STABILIZED")
        stable.validate(parent=self.initial, bounty_root=self.root)
        sealed = stable.successor(phase="SEALED")
        reopened = sealed.successor(phase="OPEN")
        self.assertEqual(self.initial.sequence, 0)
        self.assertIsNone(self.initial.parent_digest)
        self.assertEqual(reopened.parent_digest, sealed.digest)
        with self.assertRaisesRegex(CaseValidationError, "parent digest or sequence"):
            reopened.validate(parent=stable)

    def test_rejects_boolean_schema_version(self):
        raw = self.initial.to_dict()
        raw["schema_version"] = True
        with self.assertRaisesRegex(CaseValidationError, "unsupported schema_version"):
            CaseState.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
