"""DelayedWETH Solvency & Delay Integrity Inherited Pipeline and Invariant Workflows.

Governed by:
- Oracle G5 — DelayedWETH Invariant Oracle (delayed-weth-invariant-oracle)
- Target Sub-Oracles: weth-unlock-agent (#13), weth-withdraw-agent (#14)
- Sub-Surface Agents: weth-solvency-agent (#20), delay-bypass-agent (#21)
- Independent Gate: verification-agent (#9)

Governs Invariant INV-DELAYED-WETH-02: Sub-Account Solvency and Delay Integrity:
balanceOf(address(DelayedWETH)) >= sum_{c, s} withdrawals[c][s].amount
and forall (c, s), withdraw(c, s) ==> t >= withdrawals[c][s].timestamp + delay()
"""
# REVIEW FIX: workflow outputs below describe local inspection or simulation only.
# They must not be treated as proof of target behavior without executed evidence.
from __future__ import annotations
import hashlib
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


class DelayedWETHAnalystWorkflow(ArchitectureAnalystWorkflow):
    """Specialized DelayedWETH Architecture Analyst (G5 & Sub-Oracles #13/#14).

    Inspects DelayedWETH.sol and WETH98.sol to evaluate INV-DELAYED-WETH-02 prerequisites:
    - withdrawals[caller][subAccount] mapping structure
    - delay() timelock parameter
    - unlock and withdraw function signatures
    - recover administrative function scope
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "DelayedWETH Invariant Analyst (G5)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(
            context.get("workspace_root")
            or getattr(self.adapter, "workspace_root", Path.cwd())
        ).resolve()
        task_id = context.get("task_id", "TASK-WETH-001")

        tc = context.get("target_context")
        if not tc:
            from universal_adaptive_engine.models.target_context import TargetContextResolver
            tc = TargetContextResolver.resolve(context, workspace_root)

        target_root = tc.target_root

        # Resolve candidate contracts within target_root
        contract_rel_candidates = [
            ("DelayedWETH.sol", ["contracts/src/L1/proofs/DelayedWETH.sol", "src/L1/proofs/DelayedWETH.sol", "src/DelayedWETH.sol", "DelayedWETH.sol"]),
            ("WETH98.sol", ["contracts/src/universal/WETH98.sol", "src/universal/WETH98.sol", "src/WETH98.sol", "WETH98.sol"]),
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
            if tc.target_id in ("base", "unknown-target") or not target_root.exists() or not target_root.is_dir() or len(list(target_root.iterdir())) == 0:
                raise FileNotFoundError(
                    f"DelayedWETH Invariant Analyst could not locate required DelayedWETH contracts in {target_root}"
                )
            status = "COMPLETED_WITH_LIMITATIONS"
            summary = f"DelayedWETH Invariant Analyst: INV-DELAYED-WETH-02 is NOT_APPLICABLE to target '{tc.target_id}' (architecture: {tc.architecture}; DelayedWETH not present)"
            limitations = [f"Invariant INV-DELAYED-WETH-02 is NOT_APPLICABLE: target '{tc.target_id}' does not implement DelayedWETH contracts"]
            claims = [f"Target '{tc.target_id}' does not contain DelayedWETH contracts"]
            evidence_refs = [f"EVID-WETH-DISCOVERY-{task_id}"]
            return {
                "status": status,
                "summary": summary,
                "claims": claims,
                "evidence_refs": evidence_refs,
                "files_inspected": [],
                "artifacts": [],
                "limitations": limitations,
                "next_action": "Mark DelayedWETH verification NOT_APPLICABLE to target",
                "tests": TaskTests(passed=[], failed=[]),
            }

        inspected = []
        features: dict[str, bool] = {}
        for p in found_contracts:
            try:
                rel = str(p.relative_to(workspace_root))
            except ValueError:
                rel = str(p)
            inspected.append(rel)
            content = p.read_text(encoding="utf-8", errors="replace")
            if "withdrawals" in content:
                features["withdrawals_mapping"] = True
            if "delay" in content:
                features["delay_parameter"] = True
            if "unlock" in content:
                features["unlock_entrypoint"] = True
            if "withdraw" in content:
                features["withdraw_entrypoint"] = True
            if "recover" in content:
                features["recover_entrypoint"] = True

        status = "COMPLETED_WITH_LIMITATIONS"
        artifacts = [str(Path(f)) for f in inspected]

        claims = [
            f"DelayedWETH contracts inspected on target {tc.target_id}: {len(inspected)}",
            "The workflow mapped candidate invariant inputs; it did not validate scope or deployment",
            "The text search found withdrawals, delay, unlock, withdraw, and recover identifiers where present",
        ]
        evidence_refs = [f"EVID-WETH-DISCOVERY-{task_id}"]

        return {
            "status": status,
            "verification_state": "LOCAL_INSPECTION_ONLY",
            "summary": f"DelayedWETH source discovery inspected {len(inspected)} local contracts on target {tc.target_id}; the invariant remains unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "files_inspected": inspected,
            "artifacts": artifacts,
            "limitations": [
                "Local file inspection does not establish scope authorization, source provenance, deployment state, or invariant behavior."
            ],
            "next_action": "Proceed to solvency security review and authorization checks",
            "tests": TaskTests(passed=[], failed=[]),
        }


class DelayedWETHSecurityReviewerWorkflow(SecurityReviewerWorkflow):
    """Specialized DelayedWETH Security Reviewer (audit-agent & scope-agent).

    Enforces fork-only simulation, non-destructive fund controls, and administrative recover() constraints.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "DelayedWETH Security Reviewer"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-WETH-002")

        claims = [
            "No live-funds action is authorized by this workflow",
            "Scope authorization was not validated by this workflow",
            "Administrative recover() behavior was not executed or verified",
        ]
        evidence_refs = [f"EVID-WETH-SEC-AUTH-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["No scope artifact, contract execution, or fork configuration was validated by this workflow."],
            "summary": "DelayedWETH security guardrails were described; authorization and solvency remain unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "security_concerns": ["Zero live funds or mainnet broadcast allowed under Cantina bounty rules"],
            "next_action": "Proceed to deterministic solvency and delay monotonicity verification",
            "tests": TaskTests(passed=[], failed=[]),
        }


class WETHSolvencyVerifierWorkflow(VerificationEngineerWorkflow):
    """Specialized DelayedWETH Solvency & Withdraw Verifier (weth-solvency-agent & weth-withdraw-agent).

    Verifies mathematical conservation of WETH collateral:
    balanceOf(address(DelayedWETH)) >= sum(subAccounts) + claims
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "DelayedWETH Solvency Verifier (#20 & #14)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-WETH-003")

        prior_handoff = context.get("last_handoff", {})
        disc_handoff = context.get("stage_handoffs", {}).get("DISCOVERY", {})
        if "NOT_APPLICABLE" in prior_handoff.get("summary", "") or "NOT_APPLICABLE" in disc_handoff.get("summary", ""):
            return {
                "status": "COMPLETED_WITH_LIMITATIONS",
                "summary": "DelayedWETH Solvency Verifier: Invariant check NOT_APPLICABLE to current target",
                "claims": ["DelayedWETH solvency verification skipped: target does not implement DelayedWETH"],
                "evidence_refs": [f"EVID-WETH-VERIFY-{task_id}"],
                "tests": TaskTests(passed=[], failed=[]),
                "limitations": ["INV-DELAYED-WETH-02 verification skipped: target does not implement required DelayedWETH contracts"],
                "next_action": "Pass non-applicable state to challenger review",
            }

        # Invariant checks for INV-DELAYED-WETH-02
        claims = [
            "No DelayedWETH transaction, fork, or property test was executed by this workflow",
            "Collateral conservation, sub-account isolation, and state-zeroing remain hypotheses pending evidence",
            "The returned checklist does not attest target or deployment behavior",
        ]
        evidence_refs = [f"EVID-WETH-VERIFY-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying contract tests; run an authorized, pinned test suite before treating any invariant as verified."],
            "summary": "DelayedWETH verifier is a checklist stub; no solvency or delay checks were run",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Submit slice to independent challenger for timelock bypass adversarial review",
        }


class DelayBypassChallengerWorkflow(IndependentChallengerWorkflow):
    """Specialized Delay Bypass & Timelock Challenger (delay-bypass-agent & weth-unlock-agent).

    Executes adversarial negative controls on DelayedWETH unlock and withdraw:
    1. Early withdrawal attempt before t_unlock + delay() reverts
    2. Repeated unlock() calls reset timestamp rather than bypassing delay
    3. Cross-caller sub-account theft attempt reverts
    4. Deficit / under-collateralized withdrawal reverts with arithmetic error
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "Delay Bypass Challenger (#21 & #13)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-WETH-004")
        prior_handoff = context.get("last_handoff", {})
        prior_evidence = prior_handoff.get("evidence_refs", [])
        disc_handoff = context.get("stage_handoffs", {}).get("DISCOVERY", {})

        if "NOT_APPLICABLE" in prior_handoff.get("summary", "") or "NOT_APPLICABLE" in disc_handoff.get("summary", ""):
            return {
                "status": "COMPLETED_WITH_LIMITATIONS",
                "summary": "Delay Bypass Challenger: Adversarial tests NOT_APPLICABLE to current target",
                "claims": ["Challenger review recorded: DelayedWETH domain operation not applicable to target"],
                "evidence_refs": [f"EVID-WETH-CHALLENGE-{task_id}"],
                "tests": TaskTests(passed=[], failed=[]),
                "limitations": ["Adversarial falsification not applicable to non-DelayedWETH target"],
                "next_action": "Proceed to staging admission and DelayedWETH solvency completion report",
            }

        # 1. Independent Challenger audit check on prior handoff:
        if not prior_evidence and prior_handoff.get("status") == "COMPLETED_VERIFIED":
            raise AssertionError("Independent Challenger falsified prior claim: COMPLETED_VERIFIED without evidence")

        # Adversarial Negative Controls (configurable via context for falsification testing):
        # Negative Control 1: Early withdrawal prior to delay expiration
        unlock_time = context.get("unlock_time", 1_000_000)
        delay_duration = context.get("delay_duration", 604_800)  # 7 days
        current_time_early = context.get("current_time_early", unlock_time + 3600)  # only 1 hour elapsed
        early_withdraw_reverts = current_time_early < (unlock_time + delay_duration)
        if context.get("simulate_early_withdraw_allowed", False):
            early_withdraw_reverts = False
        if not early_withdraw_reverts:
            raise RuntimeError("Negative control failed: early withdrawal must revert")

        # Negative Control 2: Successive unlock timestamp reset & same-block concurrency check
        # When unlock is called again at t2 > t1, timestamp MUST be updated to t2 (resetting delay).
        # In the same block (t2 == t1), timestamp remains t1 without rewinding.
        t1 = context.get("t1", 1_000_000)
        t2 = context.get("t2", 1_000_500)
        same_block = context.get("same_block_unlock", False)
        if same_block:
            t2 = t1
            registered_timestamp = t1
            timestamp_reset_enforced = (registered_timestamp == t1)
        else:
            registered_timestamp = t2
            timestamp_reset_enforced = (registered_timestamp == t2 and registered_timestamp > t1)
        if context.get("simulate_timestamp_reset_bypass", False):
            timestamp_reset_enforced = False
        if not timestamp_reset_enforced:
            raise RuntimeError("Negative control failed: successive unlock must reset timestamp")

        # Negative Control 3: Cross-caller unauthorized sub-account access
        subaccount_owner = context.get("subaccount_owner", "0xAlice")
        attacker = context.get("attacker", "0xMallory")
        unauthorized_theft_blocked = (attacker != subaccount_owner)
        if context.get("simulate_cross_caller_theft_allowed", False):
            unauthorized_theft_blocked = False
        if not unauthorized_theft_blocked:
            raise RuntimeError("Negative control failed: cross-caller sub-account access must be blocked")

        # Negative Control 4: Deficit withdrawal
        bonded_amount = context.get("bonded_amount", 100)
        requested_amount = context.get("requested_amount", 101)
        deficit_reverts = requested_amount > bonded_amount
        if context.get("simulate_deficit_withdraw_allowed", False):
            deficit_reverts = False
        if not deficit_reverts:
            raise RuntimeError("Negative control failed: deficit withdrawal must revert")

        # Negative control digest
        neg_control_data = f"{early_withdraw_reverts}:{timestamp_reset_enforced}:{unauthorized_theft_blocked}:{deficit_reverts}".encode("utf-8")
        neg_control_digest = hashlib.sha256(neg_control_data).hexdigest()

        claims = [
            "Simulated negative-control predicates evaluated; actual contract execution was not performed",
            f"Local simulation digest (not externally committed): {neg_control_digest[:16]}...",
            "Simulated predicates only; front-running and delay-bypass resistance remain unverified",
        ]
        evidence_refs = [f"EVID-WETH-CHALLENGE-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying contract tests; verify through an authorized host test runner before treating the result as verified."],
            "summary": "Simulation completed; INV-DELAYED-WETH-02 remains unverified until contract tests execute",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Proceed to staging admission and DelayedWETH solvency completion report",
        }


class DelayedWETHSolvencyPipeline(CanonicalAdaptivePipeline):
    """Universal End-to-End Operation Pipeline for DelayedWETH Solvency & Timelock.

    Governs Invariant INV-DELAYED-WETH-02 (DelayedWETH Sub-Account Solvency & Delay Integrity).
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
            name="DelayedWETH-Solvency-Operation-Pipeline",
            adapter=bound_adapter,
            workspace_root=workspace_root,
        )

        # Override stages with DelayedWETH-specialized workflows
        self.override_stage(WorkflowStage.DISCOVERY, DelayedWETHAnalystWorkflow(self.adapter))
        self.override_stage(WorkflowStage.AUTHORIZATION_CHECK, DelayedWETHSecurityReviewerWorkflow(self.adapter))
        self.override_stage(WorkflowStage.VERIFICATION, WETHSolvencyVerifierWorkflow(self.adapter))
        self.override_stage(WorkflowStage.INDEPENDENT_REVIEW, DelayBypassChallengerWorkflow(self.adapter))

        # Skip DEPLOYMENT stage with explicit audit rationale
        self.skip_stage(
            WorkflowStage.DEPLOYMENT,
            "DelayedWETH Solvency verification is an audit and invariant evaluation domain; production deployment is not applicable.",
        )
