"""Unit and integration tests for execution safety and fail-closed gates (workflows/cantina/)."""
from __future__ import annotations

import unittest
from pathlib import Path

from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.policies.execution_policy import ExecutionPolicy
from universal_adaptive_engine.workflows.base import WorkflowStage
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.cantina import (
    CantinaArchitectureAnalystWorkflow,
    CantinaSecurityReviewerWorkflow,
    CantinaAuditWorkflow,
)


class CantinaExecutionSafetyTestCase(unittest.TestCase):
    """Test suite evaluating execution safety boundaries, non-synthetic tests, and fail-closed gates."""

    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[2]
        self.cantina_adapter = CantinaBountyAdapter(self.workspace_root)
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)

    def test_analyst_fails_closed_without_cantina_adapter(self):
        # Passing a generic host adapter must fail cleanly
        analyst = CantinaArchitectureAnalystWorkflow(self.host_adapter)
        handoff = analyst.execute({"stage": WorkflowStage.DISCOVERY})
        self.assertIn(handoff.status, ("BLOCKED", "FAILED"))
        self.assertIn("requires CantinaBountyAdapter", handoff.summary)

    def test_security_reviewer_no_synthetic_pass(self):
        reviewer = CantinaSecurityReviewerWorkflow(self.cantina_adapter)
        handoff = reviewer.execute({"stage": WorkflowStage.AUTHORIZATION_CHECK})
        self.assertEqual(handoff.status, "COMPLETED_VERIFIED")
        # Ensure reviewer did not append any synthetic "cantina_fork_only_guardrail" test pass
        self.assertNotIn("cantina_fork_only_guardrail", handoff.tests.passed)

    def test_security_reviewer_blocks_invalid_policy(self):
        invalid_policy = ExecutionPolicy(allow_broadcast=True)
        reviewer = CantinaSecurityReviewerWorkflow(self.cantina_adapter, policy=invalid_policy)
        handoff = reviewer.execute({"stage": WorkflowStage.AUTHORIZATION_CHECK})
        self.assertIn(handoff.status, ("BLOCKED", "FAILED"))
        self.assertIn("Transaction broadcasting is prohibited", handoff.summary)

    def test_audit_workflow_blocks_cast_send_and_broadcast(self):
        audit = CantinaAuditWorkflow(self.cantina_adapter)

        # Attack 1: cast send in commands_run
        ctx_cast = {
            "commands_run": ["cast send --rpc-url http://mainnet.eth 0xTarget"],
            "stage": WorkflowStage.POST_DEPLOYMENT_VALIDATION,
        }
        h_cast = audit.execute(ctx_cast)
        self.assertIn(h_cast.status, ("BLOCKED", "FAILED"))
        self.assertIn("FORK-SAFE violated", h_cast.summary)

        # Attack 2: forge broadcast in commands_run
        ctx_bcast = {
            "commands_run": ["forge script Script --broadcast"],
            "stage": WorkflowStage.POST_DEPLOYMENT_VALIDATION,
        }
        h_bcast = audit.execute(ctx_bcast)
        self.assertIn(h_bcast.status, ("BLOCKED", "FAILED"))
        self.assertIn("FORK-SAFE violated", h_bcast.summary)

    def test_audit_workflow_verifies_clean_execution(self):
        audit = CantinaAuditWorkflow(self.cantina_adapter)
        ctx_clean = {
            "commands_run": ["forge test --fork-url http://localhost:8545", "slither ."],
            "stage": WorkflowStage.POST_DEPLOYMENT_VALIDATION,
        }
        h_clean = audit.execute(ctx_clean)
        self.assertEqual(h_clean.status, "COMPLETED_VERIFIED")
        self.assertIn("audit_fork_only_safety_invariants", h_clean.tests.passed)


if __name__ == "__main__":
    unittest.main()
