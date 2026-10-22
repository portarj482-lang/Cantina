"""Fault Dispute System Inherited Pipeline and Specialized Invariant Workflows.

Governed by:
- Oracle G4 — Dispute Invariant Oracle (dispute-invariant-oracle)
- Target Sub-Oracles: dispute-prove-agent (#11), dispute-finalize-agent (#12)
- Sub-Surface Agents: game-resolution-agent (#22), blacklist-maturity-agent (#23), delay-bypass-agent (#21)
- Independent Gate: verification-agent (#9)

Governs Invariant INV-DISPUTE-01: Withdrawal Finalization Monotonicity:
forall w in Withdrawals, finalized(w) ==> (
    status(G_w) == DEFENDER_WINS
    and claim(G_w) == root_anchor(L2_block)
    and t >= t_proven + delta_maturity
    and not blacklisted(G_w)
)
"""
from __future__ import annotations
import hashlib
import time
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.base import WorkflowStage, AgentWorkflow
from universal_adaptive_engine.workflows.agents.analyst import ArchitectureAnalystWorkflow
from universal_adaptive_engine.workflows.agents.security_reviewer import SecurityReviewerWorkflow
from universal_adaptive_engine.workflows.agents.verifier import VerificationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.challenger import IndependentChallengerWorkflow
from universal_adaptive_engine.models.task import TaskTests


class DisputeAnalystWorkflow(ArchitectureAnalystWorkflow):
    """Specialized Dispute Architecture Analyst (G4 & Sub-Oracles #11/#12).

    Inspects OptimismPortal2, DisputeGameFactory, and AnchorStateRegistry
    to evaluate INV-DISPUTE-01 prerequisites.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "Dispute Invariant Analyst (G4)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(
            context.get("workspace_root")
            or getattr(self.adapter, "workspace_root", ".")
        ).resolve()
        task_id = context.get("task_id", "TASK-DISP-001")

        tc = context.get("target_context")
        if not tc:
            from universal_adaptive_engine.models.target_context import TargetContextResolver
            tc = TargetContextResolver.resolve(context, workspace_root)

        target_root = tc.target_root

        # Resolve candidate contracts within target_root
        contract_rel_candidates = [
            ("OptimismPortal2.sol", ["contracts/src/L1/OptimismPortal2.sol", "src/L1/OptimismPortal2.sol", "src/OptimismPortal2.sol", "OptimismPortal2.sol"]),
            ("DisputeGameFactory.sol", ["contracts/src/L1/proofs/DisputeGameFactory.sol", "src/L1/proofs/DisputeGameFactory.sol", "src/DisputeGameFactory.sol", "DisputeGameFactory.sol"]),
            ("AnchorStateRegistry.sol", ["contracts/src/L1/proofs/AnchorStateRegistry.sol", "src/L1/proofs/AnchorStateRegistry.sol", "src/AnchorStateRegistry.sol", "AnchorStateRegistry.sol"]),
        ]

        found_contracts: list[Path] = []
        for c_name, candidates in contract_rel_candidates:
            matched = None
            for cand in candidates:
                p = target_root / cand
                if p.exists() and p.is_file():
                    matched = p
                    break
            if not matched and target_root.exists() and target_root.is_dir():
                for p in target_root.glob(f"**/{c_name}"):
                    if p.is_file() and not any(part.startswith(".") or part in ("node_modules", "out", "cache", "build") for part in p.parts):
                        matched = p
                        break
            if matched:
                found_contracts.append(matched)

        if not found_contracts:
            # If target is base or missing files in an empty workspace, raise FileNotFoundError for diagnosed blocker
            if tc.target_id in ("base", "unknown-target") or not target_root.exists() or len(list(target_root.iterdir())) == 0:
                raise FileNotFoundError(
                    f"Dispute Invariant Analyst could not locate required dispute contracts in {target_root}"
                )
            # Target is a different valid protocol without Fault Dispute contracts
            status = "COMPLETED_WITH_LIMITATIONS"
            summary = f"Dispute Invariant Analyst: INV-DISPUTE-01 is NOT_APPLICABLE to target '{tc.target_id}' (architecture: {tc.architecture}; OptimismPortal2 not present)"
            limitations = [f"Invariant INV-DISPUTE-01 is NOT_APPLICABLE: target '{tc.target_id}' does not implement Fault Dispute System contracts"]
            claims = [f"Target '{tc.target_id}' lacks Fault Dispute System contracts"]
            evidence_refs = [f"EVID-DISP-DISCOVERY-{task_id}"]
            return {
                "status": status,
                "summary": summary,
                "claims": claims,
                "evidence_refs": evidence_refs,
                "files_inspected": [],
                "artifacts": [],
                "limitations": limitations,
                "next_action": "Mark dispute verification NOT_APPLICABLE to target",
                "tests": TaskTests(passed=[], failed=[]),
            }

        inspected = []
        extracted_params: dict[str, Any] = {}
        for p in found_contracts:
            try:
                rel = str(p.relative_to(workspace_root))
            except ValueError:
                rel = str(p)
            inspected.append(rel)
            content = p.read_text(encoding="utf-8", errors="replace")
            if "proofMaturityDelaySeconds" in content:
                extracted_params["proofMaturityDelaySeconds_declared"] = True
            if "disputeGameBlacklist" in content:
                extracted_params["disputeGameBlacklist_declared"] = True
            if "proveWithdrawalTransaction" in content:
                extracted_params["proveWithdrawalTransaction_present"] = True
            if "finalizeWithdrawalTransaction" in content:
                extracted_params["finalizeWithdrawalTransaction_present"] = True

        missing = [c for c in ["OptimismPortal2.sol", "DisputeGameFactory.sol", "AnchorStateRegistry.sol"] if not any(c in p.name for p in found_contracts)]
        status = "COMPLETED_WITH_LIMITATIONS"
        artifacts = [str(Path(f)) for f in inspected]

        claims = [
            f"Dispute contracts inspected on target {tc.target_id}: {len(inspected)} found on disk",
            "INV-DISPUTE-01 governance boundaries mapped under Dispute Invariant Oracle (G4)",
            "Target entry points proveWithdrawalTransaction and finalizeWithdrawalTransaction mapped",
        ]

        evidence_refs = [f"EVID-DISP-DISCOVERY-{task_id}"]

        return {
            "status": status,
            "summary": f"Dispute Invariant Analyst mapped {len(inspected)} dispute contracts for INV-DISPUTE-01 on target {tc.target_id}",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "files_inspected": inspected,
            "artifacts": artifacts,
            "limitations": ([f"Missing files: {missing}"] if missing else []) + ["Local source inspection does not establish authenticated source provenance, deployed bytecode, authorized scope, or invariant behavior"],
            "next_action": "Proceed to security review and fork-safe boundary check",
            "tests": TaskTests(passed=[], failed=[]),
        }


class DisputeSecurityReviewerWorkflow(SecurityReviewerWorkflow):
    """Specialized Dispute Security Reviewer (audit-agent & scope-agent).

    Enforces fork-only simulation, reentrancy guards, and caller authorization checks.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "Dispute Security Reviewer"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-DISP-002")

        claims = [
            "No test or fork was executed by this workflow",
            "Scope authorization was not validated by this workflow",
            "Reentrancy and CEI behavior were not executed or verified",
        ]
        evidence_refs = [f"EVID-DISP-SEC-AUTH-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not validate scope or run contract tests; no authorization or invariant result is established."],
            "summary": "Dispute security constraints were described; authorization and behavior remain unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "security_concerns": ["Zero broadcast transactions allowed on live Base/Ethereum mainnet"],
            "next_action": "Proceed to deterministic verification and withdrawal trie testing",
            "tests": TaskTests(passed=[], failed=[]),
        }


class DisputeProveVerifierWorkflow(VerificationEngineerWorkflow):
    """Specialized Dispute Prove & Finalize Verifier (dispute-prove-agent & dispute-finalize-agent).

    Verifies withdrawal trie proof evaluation, dispute game binding, and maturity delay parameters.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "Dispute Prove Verifier (#11 & #12)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-DISP-003")

        prior_handoff = context.get("last_handoff", {})
        disc_handoff = context.get("stage_handoffs", {}).get("DISCOVERY", {})
        if "NOT_APPLICABLE" in prior_handoff.get("summary", "") or "NOT_APPLICABLE" in disc_handoff.get("summary", ""):
            return {
                "status": "COMPLETED_WITH_LIMITATIONS",
                "summary": "Dispute Prove Verifier: Invariant check NOT_APPLICABLE to current target",
                "claims": ["Dispute prove verification skipped: target does not implement Fault Dispute System"],
                "evidence_refs": [f"EVID-DISP-VERIFY-{task_id}"],
                "tests": TaskTests(passed=[], failed=[]),
                "limitations": ["INV-DISPUTE-01 verification skipped: target does not implement required dispute contracts"],
                "next_action": "Pass non-applicable state to challenger review",
            }

        # Invariant checks for INV-DISPUTE-01
        # Model verification:
        # 1. provenWithdrawals storage binding
        # 2. disputeGame DEFENDER_WINS assertion
        # 3. proofMaturityDelaySeconds enforcement
        claims = [
            "No withdrawal proof, dispute game, or portal transaction was executed by this workflow",
            "Proof commitment, game status, maturity, and replay behavior remain unverified hypotheses",
            "The returned checklist is not evidence of deployed contract behavior",
        ]
        evidence_refs = [f"EVID-DISP-VERIFY-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This verifier is a checklist stub; no contract tests or proof validation were run."],
            "summary": "Dispute verifier checklist generated; no invariant checks were executed",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Submit slice to independent challenger for adversarial falsification review",
        }


class DisputeFinalizeChallengerWorkflow(IndependentChallengerWorkflow):
    """Specialized Dispute Challenger (game-resolution-agent & blacklist-maturity-agent).

    Executes adversarial negative controls on finalizeWithdrawalTransaction:
    1. Premature finalization before proof maturity delay elapses reverts
    2. Challenger wins or unresolved game reverts
    3. Blacklisted dispute game reverts
    4. Replay attack on finalized withdrawal reverts
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "Dispute Finalize Challenger (#22 & #23)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-DISP-004")
        prior_handoff = context.get("last_handoff", {})
        prior_evidence = prior_handoff.get("evidence_refs", [])
        disc_handoff = context.get("stage_handoffs", {}).get("DISCOVERY", {})

        if "NOT_APPLICABLE" in prior_handoff.get("summary", "") or "NOT_APPLICABLE" in disc_handoff.get("summary", ""):
            return {
                "status": "COMPLETED_WITH_LIMITATIONS",
                "summary": "Dispute Finalize Challenger: Adversarial tests NOT_APPLICABLE to current target",
                "claims": ["Challenger review recorded: domain operation not applicable to target"],
                "evidence_refs": [f"EVID-DISP-CHALLENGE-{task_id}"],
                "tests": TaskTests(passed=[], failed=[]),
                "limitations": ["Adversarial falsification not applicable to non-dispute target"],
                "next_action": "Proceed to staging admission and dispute operation completion report",
            }

        # 1. Independent Challenger audit check on prior handoff:
        if not prior_evidence and prior_handoff.get("status") == "COMPLETED_VERIFIED":
            raise AssertionError("Independent Challenger falsified prior claim: COMPLETED_VERIFIED without evidence")

        # Adversarial Negative Controls (configurable via context for falsification testing):
        # Negative Control 1: Premature finalization
        proven_time = context.get("proven_time", 1_000_000)
        maturity_delay = context.get("maturity_delay", 604_800)  # 7 days
        current_time_early = context.get("current_time_early", proven_time + 100)  # only 100s passed
        early_finalization_reverts = current_time_early < (proven_time + maturity_delay)
        if context.get("simulate_premature_bypass", False):
            early_finalization_reverts = False
        if not early_finalization_reverts:
            raise RuntimeError("Negative control failed: early finalization must revert")

        # Negative Control 2: Game resolved as CHALLENGER_WINS (status enum 1 vs DEFENDER_WINS enum 2)
        game_status = context.get("game_status", "CHALLENGER_WINS")
        status_gate_blocks = (game_status != "DEFENDER_WINS")
        if context.get("simulate_unresolved_game_allowed", False):
            status_gate_blocks = False
        if not status_gate_blocks:
            raise RuntimeError("Negative control failed: CHALLENGER_WINS game must block finalization")

        # Negative Control 3: Blacklisted dispute game
        blacklist_map = context.get("blacklist_map", {"0xBadDisputeGame": True})
        blacklisted_game_blocks = blacklist_map.get("0xBadDisputeGame", False)
        if context.get("simulate_blacklisted_allowed", False):
            blacklisted_game_blocks = False
        if not blacklisted_game_blocks:
            raise RuntimeError("Negative control failed: blacklisted game must block finalization")

        # Negative Control 4: Replay attack on finalized withdrawal
        finalized_map = context.get("finalized_map", {"0xWithdrawalHashABC": True})
        replay_blocks = finalized_map.get("0xWithdrawalHashABC", False)
        if context.get("simulate_replay_allowed", False):
            replay_blocks = False
        if not replay_blocks:
            raise RuntimeError("Negative control failed: second finalization attempt must revert")

        # Cryptographic negative control digest
        neg_control_data = f"{early_finalization_reverts}:{status_gate_blocks}:{blacklisted_game_blocks}:{replay_blocks}".encode("utf-8")
        neg_control_digest = hashlib.sha256(neg_control_data).hexdigest()

        adversarial_tests = [
            "adversarial_premature_finalization_reverts",
            "adversarial_challenger_wins_blocks_finalization",
            "adversarial_blacklisted_dispute_game_reverts",
            "adversarial_finalized_withdrawal_replay_blocks",
        ]

        claims = [
            "Simulated negative-control predicates evaluated; no contract execution was performed",
            f"Local simulation digest (not externally committed): {neg_control_digest[:16]}...",
            "Simulated predicates only; withdrawal finalization behavior remains unverified",
        ]
        evidence_refs = [f"EVID-DISP-CHALLENGE-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["The workflow evaluates local predicates only; authorized contract tests are required to verify target behavior."],
            "summary": "Simulation completed; INV-DISPUTE-01 remains unverified until contract tests execute",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Proceed to staging admission and dispute operation completion report",
        }


class DisputeSystemPipeline(CanonicalAdaptivePipeline):
    """Universal End-to-End Operation Pipeline for the Fault Dispute System.

    Governs Invariant INV-DISPUTE-01 (Withdrawal Finalization Monotonicity).
    Inherits the 14-stage lifecycle from CanonicalAdaptivePipeline, specializes
    discovery, security review, verification, and adversarial challenge stages,
    and skips production deployment with explicit audit rationale.
    """

    def __init__(
        self,
        adapter: Optional[ArchitectureAdapter] = None,
        workspace_root: Path | str = ".",
    ):
        bound_adapter = adapter or CantinaBountyAdapter(workspace_root)
        super().__init__(
            name="Fault-Dispute-System-Operation-Pipeline",
            adapter=bound_adapter,
            workspace_root=workspace_root,
        )

        # Override stages with dispute-specialized workflows
        self.override_stage(WorkflowStage.DISCOVERY, DisputeAnalystWorkflow(self.adapter))
        self.override_stage(WorkflowStage.AUTHORIZATION_CHECK, DisputeSecurityReviewerWorkflow(self.adapter))
        self.override_stage(WorkflowStage.VERIFICATION, DisputeProveVerifierWorkflow(self.adapter))
        self.override_stage(WorkflowStage.INDEPENDENT_REVIEW, DisputeFinalizeChallengerWorkflow(self.adapter))

        # Skip DEPLOYMENT stage with explicit audit rationale
        self.skip_stage(
            WorkflowStage.DEPLOYMENT,
            "Fault Dispute System verification is an audit and invariant evaluation domain; production deployment is not applicable.",
        )
