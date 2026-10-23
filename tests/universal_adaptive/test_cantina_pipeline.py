"""Integration tests for CantinaBountyPipeline lifecycle and stage gating (workflows/cantina/pipeline.py)."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.policies.execution_policy import ExecutionPolicy
from universal_adaptive_engine.workflows.cantina import (
    CantinaBountyPipeline,
    CantinaArchitectureAnalystWorkflow,
    CantinaSecurityReviewerWorkflow,
)


class CantinaPipelineTestCase(unittest.TestCase):
    """Test suite evaluating CantinaBountyPipeline execution, scope gating, and stage skips."""

    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[2]

    def test_cantina_pipeline_initialization_with_strict_workspace(self):
        pipeline = CantinaBountyPipeline(self.workspace_root)
        self.assertEqual(pipeline.cantina_root, self.workspace_root.resolve())
        self.assertIsInstance(pipeline.execution_policy, ExecutionPolicy)

    def test_cantina_pipeline_rejects_non_directory_workspace(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "some_file.txt"
            file_path.write_text("not a dir", encoding="utf-8")
            with self.assertRaises(NotADirectoryError):
                CantinaBountyPipeline(file_path)

    def test_cantina_pipeline_execution_runs_with_verified_scope(self):
        pipeline = CantinaBountyPipeline(self.workspace_root)
        report = pipeline.execute({"goal": "Audit authorized Cantina bounty"})

        self.assertEqual(report.overall_status, "COMPLETED_VERIFIED")
        self.assertEqual(len(report.stage_handoffs), 14)

        # Specialized stages check
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_VERIFIED")
        self.assertIn("matched the configured trusted snapshot", " ".join(report.stage_handoffs["DISCOVERY"]["claims"]))

        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "COMPLETED_VERIFIED")
        self.assertIn("Configured execution policy prohibits broadcasting", " ".join(report.stage_handoffs["AUTHORIZATION_CHECK"]["claims"]))

        # Skipped deployment check
        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")
        self.assertIn("not applicable", report.stage_handoffs["DEPLOYMENT"]["summary"].lower())

    def test_cantina_pipeline_blocks_when_scope_unverified(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            # Create minimal cantina structure with mismatched scope
            bounty_dir = tmp_root / "bounties" / "test-bounty"
            bounty_dir.mkdir(parents=True)
            scope_file = bounty_dir / "scope.md"
            scope_file.write_text("scope A", encoding="utf-8")
            (tmp_root / "MEMORY.md").write_text("Active bounty: test-bounty\n", encoding="utf-8")
            (tmp_root / "INSTRUCTIONS.md").write_text("# Rules\n", encoding="utf-8")

            # Snapshot has mismatched hash
            snap_dir = bounty_dir / "snapshots"
            snap_dir.mkdir()
            (snap_dir / "scope.sha256").write_text("f" * 64 + "\n", encoding="utf-8")

            pipeline = CantinaBountyPipeline(tmp_root)
            report = pipeline.execute({"goal": "Audit with mismatched scope"})

            self.assertEqual(report.overall_status, "BLOCKED")
            self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "BLOCKED")
            self.assertTrue(any("Cantina scope verification failed" in lim for lim in report.stage_handoffs["DISCOVERY"]["limitations"]))
            # Downstream protected stages must NOT run
            self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "NOT_RUN")
            self.assertEqual(report.stage_handoffs["IMPLEMENTATION"]["status"], "NOT_RUN")
            self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "NOT_RUN")

    def test_deployment_stage_skipped_with_audit_rationale(self):
        pipeline = CantinaBountyPipeline(self.workspace_root)
        report = pipeline.execute({"goal": "Test deployment skip semantics"})
        deploy_stage = report.stage_handoffs["DEPLOYMENT"]
        self.assertEqual(deploy_stage["status"], "NOT_RUN")
        self.assertIn("not applicable", deploy_stage["summary"].lower())
        self.assertIn("isolated environment", deploy_stage["summary"].lower())


if __name__ == "__main__":
    unittest.main()
