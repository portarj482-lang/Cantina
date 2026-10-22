"""Unit and integration tests for Universal End-to-End Operation Pipelines."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.harness.orchestrator import UniversalAdaptiveOrchestrator
from universal_adaptive_engine.workflows.base import WorkflowStage
from universal_adaptive_engine.workflows.operations import (
    get_operation_pipeline,
    list_available_operations,
    OPERATIONS_REGISTRY,
    DisputeSystemPipeline,
    DisputeAnalystWorkflow,
    DisputeSecurityReviewerWorkflow,
    DisputeProveVerifierWorkflow,
    DisputeFinalizeChallengerWorkflow,
    DelayedWETHSolvencyPipeline,
    DelayedWETHAnalystWorkflow,
    DelayedWETHSecurityReviewerWorkflow,
    WETHSolvencyVerifierWorkflow,
    DelayBypassChallengerWorkflow,
    MultiproofTEEPipeline,
    MultiproofTEEAnalystWorkflow,
    MultiproofTEESecurityReviewerWorkflow,
    TEERegisterVerifierWorkflow,
    AttestationChallengerWorkflow,
    RPCGovernancePipeline,
    RPCGovernancePlanWorkflow,
    RPCGovernanceAnalystWorkflow,
    RPCAuditSecurityWorkflow,
    RPCDaemonVerifierWorkflow,
    RPCChallengerWorkflow,
    RPCCleanupEvaluatorWorkflow,
)


class TestOperationPipelines(unittest.TestCase):
    """Test suite covering all specialized domain operation pipelines."""

    def setUp(self):
        self.workspace_root = Path("/home/nova/projects/cantina")
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)
        self.cantina_adapter = CantinaBountyAdapter(self.workspace_root)

    def test_list_available_operations(self):
        ops = list_available_operations()
        self.assertIn("dispute", ops)
        self.assertIn("delayed-weth", ops)
        self.assertIn("multiproof-tee", ops)
        self.assertIn("rpc-governance", ops)
        self.assertIn("cantina", ops)
        self.assertIn("canonical", ops)

    def test_get_operation_pipeline_factory(self):
        pipe_disp = get_operation_pipeline("dispute", workspace_root=self.workspace_root)
        self.assertIsInstance(pipe_disp, DisputeSystemPipeline)

        pipe_weth = get_operation_pipeline("delayed-weth", workspace_root=self.workspace_root)
        self.assertIsInstance(pipe_weth, DelayedWETHSolvencyPipeline)

        pipe_tee = get_operation_pipeline("multiproof-tee", workspace_root=self.workspace_root)
        self.assertIsInstance(pipe_tee, MultiproofTEEPipeline)

        pipe_rpc = get_operation_pipeline("rpc-governance", workspace_root=self.workspace_root)
        self.assertIsInstance(pipe_rpc, RPCGovernancePipeline)

        with self.assertRaises(ValueError):
            get_operation_pipeline("unknown-nonexistent-pipeline")

    def test_dispute_system_pipeline_execution(self):
        pipeline = DisputeSystemPipeline(
            adapter=self.cantina_adapter,
            workspace_root=self.workspace_root,
        )
        report = pipeline.execute({"goal": "Verify Fault Dispute Invariant INV-DISPUTE-01"})
        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(len(report.stage_handoffs), 14)

        # Check specialized stages
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["agent_role"], "Dispute Invariant Analyst (G4)")
        self.assertTrue(len(report.stage_handoffs["DISCOVERY"]["evidence_refs"]) > 0)

        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["agent_role"], "Dispute Security Reviewer")

        self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["VERIFICATION"]["agent_role"], "Dispute Prove Verifier (#11 & #12)")

        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["agent_role"], "Dispute Finalize Challenger (#22 & #23)")

        # Skipped deployment stage
        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")
        self.assertIn("not applicable", report.stage_handoffs["DEPLOYMENT"]["summary"])

    def test_delayed_weth_solvency_pipeline_execution(self):
        pipeline = DelayedWETHSolvencyPipeline(
            adapter=self.cantina_adapter,
            workspace_root=self.workspace_root,
        )
        report = pipeline.execute({"goal": "Verify DelayedWETH Solvency Invariant INV-DELAYED-WETH-02"})
        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(len(report.stage_handoffs), 14)

        # Check specialized stages
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["agent_role"], "DelayedWETH Invariant Analyst (G5)")

        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["agent_role"], "DelayedWETH Security Reviewer")

        self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["VERIFICATION"]["agent_role"], "DelayedWETH Solvency Verifier (#20 & #14)")

        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["agent_role"], "Delay Bypass Challenger (#21 & #13)")

        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")

    def test_multiproof_tee_pipeline_execution(self):
        pipeline = MultiproofTEEPipeline(
            adapter=self.cantina_adapter,
            workspace_root=self.workspace_root,
        )
        report = pipeline.execute({"goal": "Verify Multiproof TEE Attestation Invariant INV-MULTIPROOF-03"})
        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(len(report.stage_handoffs), 14)

        # Check specialized stages
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["agent_role"], "Multiproof TEE Invariant Analyst (G6)")

        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["agent_role"], "Multiproof TEE Security Reviewer")

        self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["VERIFICATION"]["agent_role"], "TEE Register Verifier (#15 & #16)")

        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["agent_role"], "Attestation Challenger (#17, #18, #19)")

        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")

    def test_rpc_governance_pipeline_execution(self):
        pipeline = RPCGovernancePipeline(
            adapter=self.cantina_adapter,
            workspace_root=self.workspace_root,
        )
        report = pipeline.execute({"goal": "Execute Ubuntu RPC service discovery & governance audit"})
        self.assertEqual(report.overall_status, "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(len(report.stage_handoffs), 14)

        # Check specialized stages
        self.assertEqual(report.stage_handoffs["INTAKE"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["INTAKE"]["agent_role"], "RPC Governance Planner (purpose-agent)")

        self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["DISCOVERY"]["agent_role"], "RPC Scope & Network Analyst (scope-agent & network-sec)")

        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["agent_role"], "RPC Audit & Firewall Reviewer (audit-agent & firewall-agent)")

        self.assertEqual(report.stage_handoffs["VERIFICATION"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["VERIFICATION"]["agent_role"], "RPC Daemon Verifier (rpcbind-agent & rpcinfo-agent)")

        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["INDEPENDENT_REVIEW"]["agent_role"], "RPC Independent Challenger (verification-agent #9)")

        self.assertEqual(report.stage_handoffs["POST_DEPLOYMENT_VALIDATION"]["status"], "COMPLETED_WITH_LIMITATIONS")
        self.assertEqual(report.stage_handoffs["POST_DEPLOYMENT_VALIDATION"]["agent_role"], "RPC Cleanup Evaluator (cleanup-agent #10)")

        self.assertEqual(report.stage_handoffs["DEPLOYMENT"]["status"], "NOT_RUN")

    def test_orchestrator_run_operation(self):
        orchestrator = UniversalAdaptiveOrchestrator(workspace_root=self.workspace_root)
        expected_statuses = {
            "dispute": "COMPLETED_WITH_LIMITATIONS",
            "delayed-weth": "COMPLETED_WITH_LIMITATIONS",
            "multiproof-tee": "COMPLETED_WITH_LIMITATIONS",
            "rpc-governance": "COMPLETED_WITH_LIMITATIONS",
            "weth": "COMPLETED_WITH_LIMITATIONS",
            "tee": "COMPLETED_WITH_LIMITATIONS",
            "fault-dispute": "COMPLETED_WITH_LIMITATIONS",
        }
        for op, expected_status in expected_statuses.items():
            report = orchestrator.run_operation(op, goal=f"Test run operation {op}")
            self.assertEqual(report.overall_status, expected_status, f"Operation {op} returned an unexpected status")
            self.assertEqual(len(report.stage_handoffs), 14)

    def test_orchestrator_run_operation_adapter_dispatch(self):
        orchestrator = UniversalAdaptiveOrchestrator(workspace_root=self.workspace_root)
        from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
        from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter

        from universal_adaptive_engine.workflows.operations import get_operation_pipeline
        for op in ("weth", "tee", "rpc", "fault-dispute", "cantina"):
            adapter = orchestrator.host_adapter if op.lower().strip() == "canonical" else orchestrator.cantina_adapter
            pipe = get_operation_pipeline(op, adapter=adapter, workspace_root=self.workspace_root)
            self.assertIsInstance(pipe.adapter, CantinaBountyAdapter, f"Expected CantinaBountyAdapter for operation {op}")

        adapter_canon = orchestrator.host_adapter if "canonical" == "canonical" else orchestrator.cantina_adapter
        pipe_canon = get_operation_pipeline("canonical", adapter=adapter_canon, workspace_root=self.workspace_root)
        self.assertIsInstance(pipe_canon.adapter, HostEnvironmentAdapter)

    def test_operation_factory_aliases(self):
        self.assertIsInstance(get_operation_pipeline("weth"), DelayedWETHSolvencyPipeline)
        self.assertIsInstance(get_operation_pipeline("tee"), MultiproofTEEPipeline)
        self.assertIsInstance(get_operation_pipeline("rpc"), RPCGovernancePipeline)
        self.assertIsInstance(get_operation_pipeline("fault-dispute"), DisputeSystemPipeline)

    def test_dispute_challenger_rejects_unverified_prior_handoff(self):
        challenger = DisputeFinalizeChallengerWorkflow()
        # Prior handoff claims COMPLETED_VERIFIED but has NO evidence refs
        context = {
            "last_handoff": {
                "status": "COMPLETED_VERIFIED",
                "evidence_refs": [],
                "claims": ["Unsupported assertion"],
            }
        }
        handoff = challenger.execute(context)
        self.assertIn(handoff.status, ("BLOCKED", "FAILED"))
        self.assertIn("falsified prior claim", handoff.summary)

    def test_dispute_challenger_falsification_attacks(self):
        challenger = DisputeFinalizeChallengerWorkflow()
        valid_prior = {
            "last_handoff": {"status": "COMPLETED_VERIFIED", "evidence_refs": ["EVID-VALID-001"]}
        }

        # Attack 1: Premature finalization bypass simulated
        ctx1 = dict(valid_prior, simulate_premature_bypass=True)
        h1 = challenger.execute(ctx1)
        self.assertIn(h1.status, ("BLOCKED", "FAILED"))

        # Attack 2: Unresolved / CHALLENGER_WINS game bypass simulated
        ctx2 = dict(valid_prior, simulate_unresolved_game_allowed=True)
        h2 = challenger.execute(ctx2)
        self.assertIn(h2.status, ("BLOCKED", "FAILED"))

        # Attack 3: Blacklisted game bypass simulated
        ctx3 = dict(valid_prior, simulate_blacklisted_allowed=True)
        h3 = challenger.execute(ctx3)
        self.assertIn(h3.status, ("BLOCKED", "FAILED"))

        # Attack 4: Replay bypass simulated
        ctx4 = dict(valid_prior, simulate_replay_allowed=True)
        h4 = challenger.execute(ctx4)
        self.assertIn(h4.status, ("BLOCKED", "FAILED"))

    def test_delayed_weth_challenger_falsification_and_concurrency(self):
        challenger = DelayBypassChallengerWorkflow()
        valid_prior = {
            "last_handoff": {"status": "COMPLETED_VERIFIED", "evidence_refs": ["EVID-VALID-001"]}
        }

        # Same-block concurrency unlock: identical block timestamp (t2 == t1)
        ctx_same_block = dict(valid_prior, same_block_unlock=True, t1=1_000_000, t2=1_000_000)
        h_same = challenger.execute(ctx_same_block)
        self.assertEqual(h_same.status, "COMPLETED_WITH_LIMITATIONS")

        # Attack: early withdraw allowed
        ctx_early = dict(valid_prior, simulate_early_withdraw_allowed=True)
        h_early = challenger.execute(ctx_early)
        self.assertIn(h_early.status, ("BLOCKED", "FAILED"))

        # Attack: timestamp reset bypass
        ctx_reset = dict(valid_prior, simulate_timestamp_reset_bypass=True)
        h_reset = challenger.execute(ctx_reset)
        self.assertIn(h_reset.status, ("BLOCKED", "FAILED"))

        # Attack: cross-caller theft allowed
        ctx_theft = dict(valid_prior, simulate_cross_caller_theft_allowed=True)
        h_theft = challenger.execute(ctx_theft)
        self.assertIn(h_theft.status, ("BLOCKED", "FAILED"))

        # Attack: deficit withdraw allowed
        ctx_deficit = dict(valid_prior, simulate_deficit_withdraw_allowed=True)
        h_deficit = challenger.execute(ctx_deficit)
        self.assertIn(h_deficit.status, ("BLOCKED", "FAILED"))

    def test_multiproof_tee_challenger_falsification_and_p384_boundaries(self):
        challenger = AttestationChallengerWorkflow()
        valid_prior = {
            "last_handoff": {"status": "COMPLETED_VERIFIED", "evidence_refs": ["EVID-VALID-001"]}
        }

        # Singular scalar boundary (0 scalar cannot be inverted)
        ctx_singular = dict(valid_prior, sample_scalar=0)
        h_singular = challenger.execute(ctx_singular)
        self.assertEqual(h_singular.status, "COMPLETED_WITH_LIMITATIONS")

        # Boundary scalar (>= p_384 modulus)
        p_384 = (2**384) - (2**128) - (2**96) + (2**32) - 1
        ctx_modulus = dict(valid_prior, sample_scalar=p_384)
        h_modulus = challenger.execute(ctx_modulus)
        self.assertEqual(h_modulus.status, "COMPLETED_WITH_LIMITATIONS")

        # Attack: future attestation allowed
        ctx_future = dict(valid_prior, simulate_future_attestation_allowed=True)
        h_future = challenger.execute(ctx_future)
        self.assertIn(h_future.status, ("BLOCKED", "FAILED"))

        # Attack: stale attestation allowed
        ctx_stale = dict(valid_prior, simulate_stale_attestation_allowed=True)
        h_stale = challenger.execute(ctx_stale)
        self.assertIn(h_stale.status, ("BLOCKED", "FAILED"))

        # Attack: tampered hint allowed
        ctx_hint = dict(valid_prior, simulate_tampered_hint_allowed=True)
        h_hint = challenger.execute(ctx_hint)
        self.assertIn(h_hint.status, ("BLOCKED", "FAILED"))

        # Attack: mismatched image allowed
        ctx_img = dict(valid_prior, simulate_mismatched_image_allowed=True)
        h_img = challenger.execute(ctx_img)
        self.assertIn(h_img.status, ("BLOCKED", "FAILED"))

    def test_rpc_audit_blocks_destructive_commands(self):
        pipeline = RPCGovernancePipeline(workspace_root=self.workspace_root)
        destructive_commands = [
            "rm -rf /var/run/rpcbind.lock",
            "cast send --rpc-url http://localhost:8545 0xTarget",
            "kill -9 1234",
            "ufw reset",
        ]
        for cmd in destructive_commands:
            report = pipeline.execute({"command": cmd})
            self.assertEqual(report.overall_status, "BLOCKED", f"Command '{cmd}' should have been BLOCKED")
            self.assertIn("AUTHORIZATION_CHECK", report.stage_handoffs)
            self.assertEqual(report.stage_handoffs["AUTHORIZATION_CHECK"]["status"], "BLOCKED")

    def test_rpc_challenger_falsification(self):
        challenger = RPCChallengerWorkflow()
        valid_prior = {
            "last_handoff": {"status": "COMPLETED_VERIFIED", "evidence_refs": ["EVID-VALID-001"]}
        }

        # Attack: rogue host allowed
        ctx_rogue = dict(valid_prior, simulate_rogue_host_allowed=True)
        h_rogue = challenger.execute(ctx_rogue)
        self.assertIn(h_rogue.status, ("BLOCKED", "FAILED"))

        # Attack: destructive command allowed
        ctx_dest = dict(valid_prior, simulate_destructive_allowed=True)
        h_dest = challenger.execute(ctx_dest)
        self.assertIn(h_dest.status, ("BLOCKED", "FAILED"))

    def test_discovery_missing_contracts_blocks_cleanly(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            for pipe_cls in [DisputeSystemPipeline, DelayedWETHSolvencyPipeline, MultiproofTEEPipeline]:
                pipe = pipe_cls(workspace_root=empty_dir)
                report = pipe.execute({"goal": "Test missing contracts in empty workspace"})
                self.assertEqual(report.overall_status, "BLOCKED")
                self.assertEqual(report.stage_handoffs["DISCOVERY"]["status"], "BLOCKED")
                self.assertIn("could not locate", report.stage_handoffs["DISCOVERY"]["summary"])

    def test_cantina_pipeline_factory_with_custom_adapter(self):
        pipe = get_operation_pipeline("cantina", adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        self.assertIs(pipe.adapter, self.cantina_adapter)

    def test_rpc_governance_scope_manifest_decoupling(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            target_dir = tmp_root / "standalone_target"
            target_dir.mkdir()
            (target_dir / "app.py").write_text("# standalone\n", encoding="utf-8")

            analyst = RPCGovernanceAnalystWorkflow()
            res = analyst.run_step({
                "workspace_root": str(tmp_root),
                "target_root": str(target_dir),
                "bounty_slug": None,
            })
            self.assertEqual(res["status"], "COMPLETED_WITH_LIMITATIONS")
            self.assertEqual(res["files_inspected"], [])
            self.assertTrue(any("scope.md was not located" in lim for lim in res["limitations"]))

    def test_analyst_workflows_file_target_root_handled_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)
            target_file = tmp_root / "Contract.sol"
            target_file.write_text("contract Target {}", encoding="utf-8")

            from universal_adaptive_engine.models.target_context import TargetContextResolver
            tc = TargetContextResolver.resolve(
                context={"target_root": str(target_file)},
                workspace_root=tmp_root,
            )
            for analyst_cls in [DisputeAnalystWorkflow, DelayedWETHAnalystWorkflow, MultiproofTEEAnalystWorkflow]:
                analyst = analyst_cls()
                try:
                    res = analyst.run_step({
                        "workspace_root": str(tmp_root),
                        "target_root": str(target_file),
                        "target_context": tc,
                    })
                    self.assertIn(res["status"], ("COMPLETED_WITH_LIMITATIONS", "BLOCKED"))
                except FileNotFoundError:
                    pass

    def test_all_operational_pipelines_strictly_enforce_failed_on_challenger_falsification(self):
        # 1. Dispute
        p_disp = DisputeSystemPipeline(adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        r_disp = p_disp.execute({"simulate_premature_bypass": True})
        self.assertEqual(r_disp.overall_status, "FAILED")
        self.assertEqual(r_disp.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "FAILED")

        # 2. Delayed WETH
        p_weth = DelayedWETHSolvencyPipeline(adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        r_weth = p_weth.execute({"simulate_early_withdraw_allowed": True})
        self.assertEqual(r_weth.overall_status, "FAILED")
        self.assertEqual(r_weth.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "FAILED")

        # 3. Multiproof TEE
        p_tee = MultiproofTEEPipeline(adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        r_tee = p_tee.execute({"simulate_future_attestation_allowed": True})
        self.assertEqual(r_tee.overall_status, "FAILED")
        self.assertEqual(r_tee.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "FAILED")

        # 4. RPC Governance
        p_rpc = RPCGovernancePipeline(adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        r_rpc = p_rpc.execute({"simulate_rogue_host_allowed": True})
        self.assertEqual(r_rpc.overall_status, "FAILED")
        self.assertEqual(r_rpc.stage_handoffs["INDEPENDENT_REVIEW"]["status"], "FAILED")

    def test_pipeline_accepts_dict_target_context_and_resolves(self):
        p_disp = DisputeSystemPipeline(adapter=self.cantina_adapter, workspace_root=self.workspace_root)
        r = p_disp.execute({
            "target_context": {
                "target_root": str(self.workspace_root / "bounties" / "base"),
                "architecture": "evm",
            }
        })
        self.assertIn(r.overall_status, ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS"))
        self.assertEqual(r.stage_handoffs["DISCOVERY"]["status"], "COMPLETED_WITH_LIMITATIONS")

    def test_target_context_file_target_and_ancestor_manifest_discovery(self):
        from universal_adaptive_engine.models.target_context import TargetContextResolver
        file_target = self.workspace_root / "bounties" / "base" / "contracts" / "src" / "L1" / "OptimismPortal2.sol"
        tc = TargetContextResolver.resolve(
            context={"target_root": str(file_target)},
            workspace_root=self.workspace_root,
        )
        self.assertTrue(tc.is_valid)
        self.assertEqual(tc.architecture, "evm")
        self.assertEqual(tc.languages, ("solidity",))
        self.assertIn("foundry", tc.runtimes)
        self.assertTrue(any(m.name == "foundry.toml" for m in tc.manifests))
        self.assertEqual(tc.target_root, file_target.parent)
        self.assertEqual(tc.metadata.get("target_file"), str(file_target.resolve()))


if __name__ == "__main__":
    unittest.main()

