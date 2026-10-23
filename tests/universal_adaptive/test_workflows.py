"""Unit and integration tests for Universal Adaptive Workflows, Pipelines, and Specialist Agents."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from universal_adaptive_engine.models.handoff import HandoffRecord, HandoffValidationError
from universal_adaptive_engine.models.task import TaskTests
from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.workflows.base import (
    WorkflowStage,
    AgentWorkflow,
    AgentPipeline,
    PipelineExecutionReport,
)
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.cantina_pipeline import (
    CantinaBountyPipeline,
    CantinaArchitectureAnalystWorkflow,
    CantinaSecurityReviewerWorkflow,
)
from universal_adaptive_engine.workflows.agents import (
    OrchestratorWorkflow,
    ArchitectureAnalystWorkflow,
    RepositoryInvestigatorWorkflow,
    DomainCompilerEngineerWorkflow,
    DomainSecurityResearcherWorkflow,
    SecurityReviewerWorkflow,
    ImplementationEngineerWorkflow,
    VerificationEngineerWorkflow,
    IndependentChallengerWorkflow,
    ReleaseEngineerWorkflow,
    EvaluatorWorkflow,
    KnowledgeCuratorWorkflow,
)


class TestHandoffRecord(unittest.TestCase):
    """Test suite for canonical machine-validated handoff records."""

    def test_valid_completed_verified_handoff(self):
        handoff = HandoffRecord(
            task_id="TASK-H-001",
            agent_role="Verification Engineer",
            stage="VERIFICATION",
            status="COMPLETED_VERIFIED",
            summary="All tests passed with verifiable evidence",
            claims=["Zero test regressions"],
            evidence_refs=["EVID-TEST-001"],
            tests=TaskTests(passed=["test_1", "test_2"]),
        )
        handoff.validate()
        d = handoff.to_dict()
        self.assertEqual(d["status"], "COMPLETED_VERIFIED")
        roundtrip = HandoffRecord.from_dict(d)
        roundtrip.validate()

    def test_completed_verified_rejects_empty_evidence(self):
        handoff = HandoffRecord(
            task_id="TASK-H-002",
            agent_role="Verification Engineer",
            status="COMPLETED_VERIFIED",
            summary="Claimed success without evidence",
            evidence_refs=[],
        )
        with self.assertRaises(HandoffValidationError):
            handoff.validate()

    def test_completed_verified_rejects_failed_tests(self):
        handoff = HandoffRecord(
            task_id="TASK-H-003",
            agent_role="Verification Engineer",
            status="COMPLETED_VERIFIED",
            summary="Claimed success despite failed tests",
            evidence_refs=["EVID-001"],
            tests=TaskTests(passed=["test_1"], failed=["test_2"]),
        )
        with self.assertRaises(HandoffValidationError):
            handoff.validate()

    def test_completed_with_limitations_requires_limitations_list(self):
        handoff = HandoffRecord(
            task_id="TASK-H-004",
            agent_role="Compiler Engineer",
            status="COMPLETED_WITH_LIMITATIONS",
            summary="Compiler missing but AST parsed",
            evidence_refs=["EVID-001"],
            limitations=[],  # Empty limitations must fail
        )
        with self.assertRaises(HandoffValidationError):
            handoff.validate()

    def test_completed_with_limitations_valid(self):
        handoff = HandoffRecord(
            task_id="TASK-H-005",
            agent_role="Compiler Engineer",
            status="COMPLETED_WITH_LIMITATIONS",
            summary="Compiler missing but AST parsed",
            evidence_refs=["EVID-001"],
            limitations=["solc is absent from container"],
        )
        handoff.validate()


class TestSpecialistAgentWorkflows(unittest.TestCase):
    """Test suite verifying all 12 specialist agent workflows individually."""

    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[2]
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)

    def test_orchestrator_workflow_stages(self):
        wf = OrchestratorWorkflow(self.host_adapter)
        self.assertEqual(wf.authority_level, "principal")

        # INTAKE
        h1 = wf.execute({"goal": "Test goal", "stage": WorkflowStage.INTAKE})
        self.assertEqual(h1.status, "COMPLETED_VERIFIED")

        # DECOMPOSITION
        h2 = wf.execute({"goal": "Test goal", "stage": WorkflowStage.DECOMPOSITION})
        self.assertEqual(h2.status, "COMPLETED_VERIFIED")

        # PLAN
        h3 = wf.execute({"goal": "Test goal", "stage": WorkflowStage.PLAN})
        self.assertEqual(h3.status, "COMPLETED_VERIFIED")

        # COMPLETION_REPORT
        h4 = wf.execute({
            "goal": "Test goal",
            "stage": WorkflowStage.COMPLETION_REPORT,
            "stage_handoffs": {"INTAKE": h1.to_dict()},
        })
        self.assertEqual(h4.status, "COMPLETED_VERIFIED")

        # COMPLETION_REPORT with non-verified stage
        h5 = wf.execute({
            "goal": "Test goal",
            "stage": WorkflowStage.COMPLETION_REPORT,
            "stage_handoffs": {
                "INTAKE": h1.to_dict(),
                "DISCOVERY": {"status": "COMPLETED_WITH_LIMITATIONS", "summary": "Limited discovery"},
            },
        })
        self.assertEqual(h5.status, "COMPLETED_WITH_LIMITATIONS")
        self.assertTrue(len(h5.limitations) > 0)

    def test_architecture_analyst_workflow(self):
        wf = ArchitectureAnalystWorkflow(self.host_adapter)
        h = wf.execute({"goal": "Discover architecture", "stage": WorkflowStage.DISCOVERY})
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertTrue(len(h.claims) > 0)

    def test_repository_investigator_workflow(self):
        wf = RepositoryInvestigatorWorkflow(self.host_adapter)
        h = wf.execute({
            "workspace_root": str(self.workspace_root),
            "target_files": ["INSTRUCTIONS.md"],
            "stage": WorkflowStage.BASELINE,
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertIn("INSTRUCTIONS.md", h.files_inspected)

    def test_repository_investigator_handles_missing_file_as_blocked(self):
        wf = RepositoryInvestigatorWorkflow(self.host_adapter)
        h = wf.execute({
            "workspace_root": str(self.workspace_root),
            "target_files": ["non_existent_file_definitely_missing.txt"],
            "stage": WorkflowStage.BASELINE,
        })
        self.assertEqual(h.status, "BLOCKED")
        self.assertIn("could not locate required files", h.summary)

    def test_domain_compiler_engineer_workflow(self):
        wf = DomainCompilerEngineerWorkflow(self.host_adapter)
        h = wf.execute({
            "workspace_root": str(self.workspace_root),
            "check_syntax_files": ["universal_adaptive_engine/cli.py"],
            "stage": WorkflowStage.BASELINE,
        })
        self.assertIn(h.status, ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS"))

    def test_security_reviewer_blocks_path_traversal(self):
        wf = SecurityReviewerWorkflow(self.host_adapter)
        h = wf.execute({
            "workspace_root": str(self.workspace_root),
            "target_paths": ["/etc/shadow"],
            "stage": WorkflowStage.AUTHORIZATION_CHECK,
        })
        self.assertEqual(h.status, "BLOCKED")
        self.assertIn("outside workspace", h.summary)

    def test_security_reviewer_authorizes_clean_paths(self):
        wf = SecurityReviewerWorkflow(self.host_adapter)
        h = wf.execute({
            "workspace_root": str(self.workspace_root),
            "target_paths": [str(self.workspace_root / "INSTRUCTIONS.md")],
            "stage": WorkflowStage.AUTHORIZATION_CHECK,
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")

    def test_domain_security_researcher_workflow(self):
        wf = DomainSecurityResearcherWorkflow(self.host_adapter)
        h = wf.execute({"stage": WorkflowStage.DISCOVERY, "target_contract": "CantinaEngine"})
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertIn("threat model", h.summary.lower())

    def test_implementation_engineer_workflow(self):
        wf = ImplementationEngineerWorkflow(self.host_adapter)
        h = wf.execute({
            "stage": WorkflowStage.IMPLEMENTATION,
            "files_changed": ["universal_adaptive_engine/workflows/base.py"],
            "slice_description": "Implement workflow classes",
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")

    def test_verification_engineer_workflow(self):
        wf = VerificationEngineerWorkflow(self.host_adapter)
        h = wf.execute({
            "stage": WorkflowStage.VERIFICATION,
            "workspace_root": str(self.workspace_root),
            "test_commands": ["python3 -m unittest global/core/tests/test_case_state.py"],
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertEqual(len(h.tests.passed), 1)
        self.assertEqual(len(h.commands_run), 1)
        self.assertEqual(h.commands_run[0]["exit_code"], 0)
        self.assertIn("output_digest", h.commands_run[0])
        self.assertEqual(len(h.commands_run[0]["output_digest"]), 64)

    def test_verification_engineer_forge_detection(self):
        import shutil
        wf = VerificationEngineerWorkflow(self.host_adapter)
        env = wf._resolve_tool_env()
        forge_bin = wf._resolve_forge_binary(env)
        has_forge = bool(
            shutil.which("forge")
            or any((d / "forge").exists() for d in [Path.home() / ".foundry" / "bin", Path.home() / ".cargo" / "bin", Path.home() / ".local" / "bin"])
        )
        if has_forge:
            self.assertIsNotNone(forge_bin, "Forge binary should be discoverable via toolchain search")
        else:
            self.assertIsNone(forge_bin, "Forge binary should be None when not installed")

    def test_verification_engineer_fails_on_broken_test(self):
        wf = VerificationEngineerWorkflow(self.host_adapter)
        with self.assertRaises(RuntimeError) as ctx:
            wf.run_step({
                "stage": WorkflowStage.VERIFICATION,
                "workspace_root": str(self.workspace_root),
                "test_commands": ["false"],
            })
        self.assertIn("Deterministic verification tests failed", str(ctx.exception))

        h = wf.execute({
            "stage": WorkflowStage.VERIFICATION,
            "workspace_root": str(self.workspace_root),
            "test_commands": ["false"],
        })
        self.assertIn(h.status, ["FAILED", "BLOCKED"])

    def test_independent_challenger_negative_control(self):
        wf = IndependentChallengerWorkflow(self.host_adapter)
        h = wf.execute({
            "stage": WorkflowStage.INDEPENDENT_REVIEW,
            "last_handoff": {
                "claims": ["Deterministic tests passed"],
                "evidence_refs": ["EVID-VERIFY-001"],
                "status": "COMPLETED_VERIFIED",
            },
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertIn("falsification_negative_control", h.tests.passed)

    def test_release_engineer_staging_and_approval(self):
        wf = ReleaseEngineerWorkflow(self.host_adapter)
        h_staging = wf.execute({"stage": WorkflowStage.STAGING})
        self.assertEqual(h_staging.status, "COMPLETED_VERIFIED")

        h_approval = wf.execute({"stage": WorkflowStage.APPROVAL, "approval_granted": True})
        self.assertEqual(h_approval.status, "COMPLETED_VERIFIED")

        h_denied = wf.execute({"stage": WorkflowStage.APPROVAL, "approval_granted": False})
        self.assertEqual(h_denied.status, "BLOCKED")

    def test_evaluator_workflow_detects_regressions(self):
        wf = EvaluatorWorkflow(self.host_adapter)
        h_clean = wf.execute({
            "stage": WorkflowStage.POST_DEPLOYMENT_VALIDATION,
            "current_metrics": {"regressions": 0},
        })
        self.assertEqual(h_clean.status, "COMPLETED_VERIFIED")

        h_regr = wf.execute({
            "stage": WorkflowStage.POST_DEPLOYMENT_VALIDATION,
            "current_metrics": {"regressions": 2},
        })
        self.assertEqual(h_regr.status, "FAILED")

    def test_knowledge_curator_workflow(self):
        wf = KnowledgeCuratorWorkflow(self.host_adapter)
        h = wf.execute({
            "stage": WorkflowStage.BASELINE,
            "workspace_root": str(self.workspace_root),
            "curate_file": "INSTRUCTIONS.md",
        })
        self.assertEqual(h.status, "COMPLETED_VERIFIED")
        self.assertTrue(any("Cryptographic digest" in c for c in h.claims))


class TestPipelineAndInheritance(unittest.TestCase):
    """Test suite verifying pipeline composition, inheritance, and execution."""

    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parents[2]
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)

    def test_canonical_pipeline_full_run(self):
        pipeline = CanonicalAdaptivePipeline(
            adapter=self.host_adapter,
            workspace_root=self.workspace_root,
        )
        report = pipeline.execute({"goal": "Test full canonical lifecycle"})
        self.assertEqual(report.overall_status, "COMPLETED_VERIFIED")
        self.assertEqual(len(report.stage_handoffs), 14)
        for stage_name, handoff in report.stage_handoffs.items():
            self.assertEqual(handoff["status"], "COMPLETED_VERIFIED")

    def test_canonical_pipeline_blocks_invalid_target_context_before_running_stages(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_root = Path(tmp_dir) / "missing-target"
            pipeline = CanonicalAdaptivePipeline(
                adapter=self.host_adapter,
                workspace_root=missing_root,
            )
            report = pipeline.execute({"goal": "Block when target context cannot be resolved"})

        self.assertEqual(report.overall_status, "BLOCKED")
        self.assertEqual(list(report.stage_handoffs), ["DISCOVERY"])
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "BLOCKED")
        self.assertEqual(report.evidence_collected, [])
        self.assertIn("not an existing directory", report.blockers[0])

    def test_pipeline_blocker_short_circuits_remaining_stages(self):
        pipeline = CanonicalAdaptivePipeline(
            adapter=self.host_adapter,
            workspace_root=self.workspace_root,
        )
        # Force baseline stage to fail by inspecting a non-existent file
        investigator = RepositoryInvestigatorWorkflow(self.host_adapter)
        pipeline.override_stage(WorkflowStage.BASELINE, investigator)

        report = pipeline.execute({
            "goal": "Test blocker short-circuit",
            "target_files": ["non_existent_file_definitely_missing.txt"],
        })
        self.assertEqual(report.overall_status, "BLOCKED")
        self.assertEqual(report.stage_handoffs["BASELINE"]["status"], "BLOCKED")
        self.assertEqual(report.stage_handoffs["DECOMPOSITION"]["status"], "NOT_RUN")
        self.assertEqual(report.stage_handoffs["COMPLETION_REPORT"]["status"], "NOT_RUN")

    def test_cantina_bounty_pipeline_inheritance(self):
        cantina_pipe = CantinaBountyPipeline(self.workspace_root)
        self.assertIsInstance(cantina_pipe, CanonicalAdaptivePipeline)

        report = cantina_pipe.execute({"goal": "Execute Cantina specialized pipeline"})
        # DEPLOYMENT stage is skipped by design
        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")
        self.assertIn("not applicable", report.stage_handoffs["DEPLOYMENT"]["summary"])
        # Overall status should be verified or completed with limitations (due to scope digest)
        self.assertIn(report.overall_status, ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS"))

    def test_optional_stage_failure_downgrades_to_completed_with_limitations(self):
        pipeline = CanonicalAdaptivePipeline(
            adapter=self.host_adapter,
            workspace_root=self.workspace_root,
        )
        # Make IMPLEMENTATION optional and fail
        for s in pipeline.stages:
            if s.stage == WorkflowStage.IMPLEMENTATION:
                s.required = False

        class FailingWorkflow(AgentWorkflow):
            def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
                return {
                    "status": "FAILED",
                    "summary": "Optional implementation step failed cleanly",
                    "claims": [],
                    "evidence_refs": [],
                    "limitations": ["Optional implementation failed"],
                    "next_action": "Continue with remaining stages",
                }

        pipeline.override_stage(WorkflowStage.IMPLEMENTATION, FailingWorkflow("agent-fail", "Failing Engineer", "dev"))
        report = pipeline.execute({"goal": "Test optional stage failure handling"})

        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["IMPLEMENTATION"]["status"], "FAILED")
        # Remaining stages still ran!
        self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "COMPLETED_VERIFIED")
        self.assertEqual(report.stage_handoffs["COMPLETION_REPORT"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertTrue(any("Optional stage IMPLEMENTATION failed" in lim for lim in report.limitations))

    def test_interleaved_skipped_and_failed_optional_stages(self):
        pipeline = CanonicalAdaptivePipeline(
            adapter=self.host_adapter,
            workspace_root=self.workspace_root,
        )
        # Skip STAGING
        pipeline.skip_stage(WorkflowStage.STAGING, "Staging not applicable in test mode")

        # Make APPROVAL optional and blocked
        for s in pipeline.stages:
            if s.stage == WorkflowStage.APPROVAL:
                s.required = False

        class BlockedWorkflow(AgentWorkflow):
            def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
                raise PermissionError("Approval requires multi-sig admin keys")

        pipeline.override_stage(WorkflowStage.APPROVAL, BlockedWorkflow("agent-block", "Approval Agent", "admin"))

        # Make DEPLOYMENT optional and failed
        for s in pipeline.stages:
            if s.stage == WorkflowStage.DEPLOYMENT:
                s.required = False

        class FailingDeployWorkflow(AgentWorkflow):
            def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
                return {
                    "status": "FAILED",
                    "summary": "Deploy dry-run failed",
                    "claims": [],
                    "evidence_refs": [],
                    "limitations": ["Deploy dry-run failed"],
                    "next_action": "Check configuration",
                }

        pipeline.override_stage(WorkflowStage.DEPLOYMENT, FailingDeployWorkflow("agent-deploy", "Deploy Agent", "ops"))

        report = pipeline.execute({"goal": "Test interleaved skipped and failed optional stages"})

        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["STAGING"]["status"], "NOT_RUN")
        self.assertEqual(report.stage_handoffs["APPROVAL"]["status"], "BLOCKED")
        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "FAILED")
        self.assertEqual(report.stage_handoffs["POST_DEPLOYMENT_VALIDATION"]["status"], "COMPLETED_VERIFIED")
        self.assertEqual(report.stage_handoffs["COMPLETION_REPORT"]["status"], "COMPLETED_WITH_LIMITATIONS")


if __name__ == "__main__":
    unittest.main()
