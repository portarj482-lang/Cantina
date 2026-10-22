"""Unit tests for the execution harness, vertical slice, and blocker diagnosis."""
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.harness.orchestrator import UniversalAdaptiveOrchestrator
from universal_adaptive_engine.harness.evidence_store import EvidenceStore
from universal_adaptive_engine.models import (
    BlockerCategory,
    TaskState,
)


class HarnessVerticalSliceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_root = Path(self.temp_dir.name)
        # Create a mock target file
        self.target_file = self.test_root / "SAMPLE_ARTIFACT.md"
        self.target_file.write_text("# Target Artifact\nContent for testing.\n", encoding="utf-8")

        # Create memory file for cantina adapter compatibility
        (self.test_root / "MEMORY.md").write_text("# Memory\nActive bounty: none\n", encoding="utf-8")
        (self.test_root / "INSTRUCTIONS.md").write_text("# Instructions\n", encoding="utf-8")

        self.orchestrator = UniversalAdaptiveOrchestrator(
            workspace_root=self.test_root,
            storage_dir=self.test_root / ".orchestrator_state",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_run_vertical_slice_end_to_end(self):
        report = self.orchestrator.run_vertical_slice(
            goal="Verify test artifact integrity and provenance",
            target_file="SAMPLE_ARTIFACT.md",
        )
        self.assertEqual(report.completion_state, "COMPLETED_VERIFIED")
        self.assertEqual(len(report.tasks_run), 2)
        self.assertTrue(all(t["status"] == TaskState.COMPLETED_VERIFIED.value for t in report.tasks_run))
        self.assertEqual(report.challenger_review["status"], "PASSED")
        self.assertTrue(report.challenger_review["negative_control_verified"])
        self.assertTrue(len(report.findings) > 0)
        self.assertTrue(len(report.adaptations) > 0)

        # Markdown representation is complete
        md = report.to_markdown()
        self.assertIn("Execution & Orchestration Report", md)
        self.assertIn("COMPLETED_VERIFIED", md)
        self.assertIn("SAMPLE_ARTIFACT.md", md)

        # Evidence store has records and all match disk digests
        evidence_results = self.orchestrator.evidence_store.verify_all_artifacts()
        self.assertEqual(len(evidence_results["mismatched"]), 0)
        self.assertEqual(len(evidence_results["missing"]), 0)

    def test_blocker_diagnosis_taxonomy(self):
        # 1. Permission error
        b_perm = self.orchestrator.diagnose_blocker(PermissionError("Permission denied: /root/secret"))
        self.assertEqual(b_perm.category, BlockerCategory.PERMISSION_DENIED)
        self.assertFalse(b_perm.recoverable)
        self.assertIn("Request authorized permission", b_perm.recovery_action)

        # 2. Missing file
        b_miss = self.orchestrator.diagnose_blocker(FileNotFoundError("No such file or directory: missing.txt"))
        self.assertEqual(b_miss.category, BlockerCategory.MISSING_CONTEXT)
        self.assertTrue(b_miss.recoverable)

        # 3. Schema / validation failure
        b_val = self.orchestrator.diagnose_blocker(ValueError("Schema validation error: missing task_id"))
        self.assertEqual(b_val.category, BlockerCategory.INVALID_INPUT)
        self.assertTrue(b_val.recoverable)

        # 4. Policy block
        b_pol = self.orchestrator.diagnose_blocker(RuntimeError("Action violates policy guardrail: network forbidden"))
        self.assertEqual(b_pol.category, BlockerCategory.POLICY_BLOCK)
        self.assertFalse(b_pol.recoverable)

        # 5. Timeout
        b_to = self.orchestrator.diagnose_blocker(TimeoutError("Command execution timed out after 30s"))
        self.assertEqual(b_to.category, BlockerCategory.RESOURCE_LIMIT)
        self.assertTrue(b_to.recoverable)

    def test_vertical_slice_missing_target_file_blocks_cleanly(self):
        # A missing artifact must not crash, must diagnose MISSING_CONTEXT and return BLOCKED
        report = self.orchestrator.run_vertical_slice(
            goal="Inspect non-existent artifact",
            target_file="DEFINITELY_NOT_EXISTING.txt",
        )
        self.assertEqual(report.completion_state, "BLOCKED")
        self.assertEqual(len(report.tasks_run), 2)
        # Both task1 and task2 should be marked BLOCKED in ledger and report
        task1 = report.tasks_run[0]
        task2 = report.tasks_run[1]
        self.assertEqual(task1["status"], TaskState.BLOCKED.value)
        self.assertEqual(task1["blocker"]["category"], BlockerCategory.MISSING_CONTEXT.value)
        self.assertEqual(task2["status"], TaskState.BLOCKED.value)
        self.assertEqual(task2["blocker"]["category"], BlockerCategory.DEPENDENCY_FAILURE.value)
        self.assertEqual(report.challenger_review["status"], "NOT_RUN")

    def test_vertical_slice_escaped_path_blocks_cleanly(self):
        report = self.orchestrator.run_vertical_slice(
            goal="Inspect escaped path",
            target_file="../../../etc/passwd",
        )
        self.assertEqual(report.completion_state, "BLOCKED")
        task1 = report.tasks_run[0]
        self.assertEqual(task1["status"], TaskState.BLOCKED.value)
        self.assertEqual(task1["blocker"]["category"], BlockerCategory.PERMISSION_DENIED.value)


if __name__ == "__main__":
    unittest.main()
