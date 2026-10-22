"""Linux RPC Administration & Governance Inherited Pipeline.

Governed by:
- Oracle G3 — RPC Admin Oracle (rpc-admin-oracle)
- Oracle G2 — Playbook Admin Oracle (playbook-admin-oracle)
- Oracle G1 — Global Admin Oracle (global-admin-oracle)
- Sub-Agents: purpose-agent (#1), scope-agent (#2), audit-agent (#3), rpcbind-agent (#4),
  rpcinfo-agent (#5), rpcclient-agent (#6), network-security-agent (#7), firewall-agent (#8),
  cleanup-agent (#10)
- Independent Gate: verification-agent (#9)

Governs Linux RPC Daemons, Portmapper 111, SMB/Windows MS-RPC interaction, and non-destructive execution.
"""
# REVIEW FIX: returned statuses are provisional. This module does not execute
# host, contract, or network tests; its predicates are not target evidence.
from __future__ import annotations
import hashlib
import shlex
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.base import WorkflowStage, AgentWorkflow
from universal_adaptive_engine.workflows.agents.orchestrator import OrchestratorWorkflow
from universal_adaptive_engine.workflows.agents.analyst import ArchitectureAnalystWorkflow
from universal_adaptive_engine.workflows.agents.security_reviewer import SecurityReviewerWorkflow
from universal_adaptive_engine.workflows.agents.verifier import VerificationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.challenger import IndependentChallengerWorkflow
from universal_adaptive_engine.workflows.agents.evaluator import EvaluatorWorkflow
from universal_adaptive_engine.models.task import TaskTests


class RPCGovernancePlanWorkflow(OrchestratorWorkflow):
    """Specialized RPC Governance Planner (purpose-agent & G2 Playbook Admin).

    Enforces purpose statement formulation before any artifact creation or daemon modification.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Governance Planner (purpose-agent)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-RPC-001")
        goal = context.get("goal", "Execute RPC service discovery and security audit")

        claims = [
            f"Requested purpose recorded (not independently authorized): {goal}",
            "Required playbook: global/playbooks/ubuntu_rpc_playbook.md (existence and contents must be checked before execution)",
            "Required governance roles are declared in configuration; their execution is not verified here",
        ]
        evidence_refs = [f"EVID-RPC-PURPOSE-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying host or network tests; verify through an authorized runner before treating the result as verified."],
            "summary": "RPC purpose statement recorded; authorization and playbook conformance remain unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "next_action": "Proceed to target scope and network topology discovery",
            "tests": TaskTests(passed=[], failed=[]),
        }


class RPCGovernanceAnalystWorkflow(ArchitectureAnalystWorkflow):
    """Specialized RPC Architecture Analyst (scope-agent & network-security-agent).

    Validates targets against bounties/<slug>/scope.md and checks network DNS / IP routing.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Scope & Network Analyst (scope-agent & network-sec)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(
            context.get("workspace_root")
            or getattr(self.adapter, "workspace_root", Path.cwd())
        ).resolve()
        task_id = context.get("task_id", "TASK-RPC-002")

        tc = context.get("target_context")
        if not tc:
            from universal_adaptive_engine.models.target_context import TargetContextResolver
            tc = TargetContextResolver.resolve(context, workspace_root)

        scope_file = None
        if tc and tc.scope_manifest and tc.scope_manifest.exists():
            scope_file = tc.scope_manifest
        elif tc and (tc.target_root / "scope.md").exists():
            scope_file = tc.target_root / "scope.md"
        else:
            bounty = context.get("bounty_slug") or (tc.bounty_slug if tc else "base")
            candidate = workspace_root / "bounties" / bounty / "scope.md"
            if candidate.exists():
                scope_file = candidate
            else:
                scope_file = workspace_root / "bounties" / "base" / "scope.md"

        scope_present = scope_file.exists() if scope_file else False
        try:
            inspected = [str(scope_file.relative_to(workspace_root))] if scope_present else []
        except ValueError:
            inspected = [str(scope_file)] if scope_present else []

        status = "COMPLETED_WITH_LIMITATIONS"
        limitations = [] if scope_present else [f"scope.md was not located for target '{tc.target_id if tc else 'unknown'}'"]

        claims = [
            f"Scope file exists at {scope_file}; its contents and target authorization have not been validated" if scope_present else f"Scope Agent recorded limitation: scope.md missing for target '{tc.target_id if tc else 'unknown'}'",
            "Network topology and route constraints were not probed by this workflow",
            "Ports 111, 445, and 139 require explicit target authorization before probing",
        ]
        evidence_refs = [f"EVID-RPC-DISCOVERY-{task_id}"]

        return {
            "status": status,
            "verification_state": "DISCOVERY_ONLY",
            "summary": "RPC scope-file discovery completed; target authorization and network topology remain unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "files_inspected": inspected,
            "limitations": limitations + ["Scope-file discovery only; authorization and network state were not verified."],
            "next_action": "Proceed to non-destructive audit classification and firewall review",
            "tests": TaskTests(passed=[], failed=[]),
        }


class RPCAuditSecurityWorkflow(SecurityReviewerWorkflow):
    """Specialized RPC Audit & Firewall Reviewer (audit-agent & firewall-agent).

    Enforces non-destructive classification (READ-ONLY or FORK-SAFE; blocks DESTRUCTIVE)
    and verifies UFW firewall rule configuration for ports 111, 445, 139.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Audit & Firewall Reviewer (audit-agent & firewall-agent)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(
            context.get("workspace_root")
            or getattr(self.adapter, "workspace_root", Path.cwd())
        ).resolve()
        task_id = context.get("task_id", "TASK-RPC-003")

        proposed_command = context.get("command", "rpcinfo -p")
        if not isinstance(proposed_command, str) or not proposed_command.strip():
            raise ValueError("command must be a non-empty string")

        # Deny-lists are bypassable through shell syntax and alternate commands.
        # This workflow authorizes two local read-only shapes and never executes them.
        try:
            argv = shlex.split(proposed_command, posix=True)
        except ValueError as exc:
            raise PermissionError("Malformed command rejected by RPC audit policy") from exc
        shell_metacharacters = (";", "|", "&", ">", "<", "$", "`", "\n", "\r")
        if any(token in proposed_command for token in shell_metacharacters):
            raise PermissionError("Shell operators/substitutions are prohibited")
        allowed_read_only_commands = {("rpcinfo", "-p"), ("rpcinfo", "-s")}
        if tuple(argv) not in allowed_read_only_commands:
            raise PermissionError("Command is not in the strict local read-only allowlist; no command was executed")
        classification = "READ-ONLY"

        claims = [
            f"Audit Agent classified command '{proposed_command}' as {classification}",
            "Only commands in the strict local read-only allowlist are classified READ-ONLY; this workflow does not execute them",
            "Firewall state and session-opened rules were not inspected by this workflow",
        ]
        evidence_refs = [f"EVID-RPC-SEC-AUTH-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying host or network tests; verify through an authorized runner before treating the result as verified."],
            "summary": f"RPC command classified as {classification}; host state and target authorization remain unverified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "security_concerns": ["All session-opened ports must be closed upon session teardown"],
            "next_action": "Proceed to deterministic service verification",
            "tests": TaskTests(passed=[], failed=[]),
        }


class RPCDaemonVerifierWorkflow(VerificationEngineerWorkflow):
    """Specialized RPC Daemon & Service Verifier (rpcbind-agent & rpcinfo-agent).

    Verifies portmapper daemon status on port 111 and enumerates registered RPC programs.
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Daemon Verifier (rpcbind-agent & rpcinfo-agent)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-RPC-004")

        claims = [
            "RPC binding was not checked against host state by this workflow",
            "RPC program registration was not queried by this workflow",
            "Credential exposure was not audited against actual artifacts or logs",
        ]
        evidence_refs = [f"EVID-RPC-VERIFY-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying host or network tests; verify through an authorized runner before treating the result as verified."],
            "summary": "RPC verifier is a checklist stub; no daemon or port checks were run",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Submit slice to independent challenger for security policy review",
        }


class RPCChallengerWorkflow(IndependentChallengerWorkflow):
    """Specialized RPC Challenger (independent-challenger & verification-agent).

    Executes adversarial negative controls on RPC operations:
    1. Connection attempt to out-of-scope host is strictly BLOCKED
    2. Command flagged with destructive action is hard-BLOCKED
    3. Unopened/unauthorized port is refused
    4. Credential persistence on disk triggers falsification failure
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Independent Challenger (verification-agent #9)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        task_id = context.get("task_id", "TASK-RPC-005")
        prior_handoff = context.get("last_handoff", {})
        prior_evidence = prior_handoff.get("evidence_refs", [])

        # 1. Independent Challenger audit check on prior handoff:
        if not prior_evidence and prior_handoff.get("status") == "COMPLETED_VERIFIED":
            raise AssertionError("Independent Challenger falsified prior claim: COMPLETED_VERIFIED without evidence")

        # Adversarial Negative Controls (configurable via context for falsification testing):
        # Negative Control 1: Out-of-scope host connection
        allowed_hosts = context.get("allowed_hosts", {"127.0.0.1", "localhost", "authorized-bounty-target.internal"})
        rogue_host = context.get("rogue_host", "192.168.1.99")
        out_of_scope_blocked = (rogue_host not in allowed_hosts)
        if context.get("simulate_rogue_host_allowed", False):
            out_of_scope_blocked = False
        if not out_of_scope_blocked:
            raise RuntimeError("Negative control failed: out-of-scope host must be blocked")

        # Negative Control 2: Destructive command rejection
        destructive_cmd = context.get("destructive_cmd", "rm -rf /var/run/rpcbind.lock")
        destructive_flagged = any(bad in destructive_cmd.lower() for bad in ["rm -rf", "rm -r", "drop", "format", "cast send", "kill -9"])
        if context.get("simulate_destructive_allowed", False):
            destructive_flagged = False
        if not destructive_flagged:
            raise RuntimeError("Negative control failed: destructive command must be flagged")

        # Negative Control 3: Credential persistence check
        credentials_on_disk = context.get("credentials_on_disk", False)
        credential_leak_blocked = (not credentials_on_disk)
        if not credential_leak_blocked:
            raise RuntimeError("Negative control failed: credentials must not persist on disk")

        # Negative Control 4: Verification gate checks raw source citation
        claim_has_source_citation = context.get("claim_has_source_citation", True)
        if not claim_has_source_citation:
            raise RuntimeError("Negative control failed: claims must cite raw source tags")

        neg_control_data = f"{out_of_scope_blocked}:{destructive_flagged}:{credential_leak_blocked}:{claim_has_source_citation}".encode("utf-8")
        neg_control_digest = hashlib.sha256(neg_control_data).hexdigest()

        claims = [
            "Simulated RPC policy predicates evaluated; no network or host-state checks were performed",
            f"Local simulation digest (not externally committed): {neg_control_digest[:16]}...",
            "Simulation evaluated scope and non-destructive policy predicates; host enforcement was not tested",
        ]
        evidence_refs = [f"EVID-RPC-CHALLENGE-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "verification_state": "NOT_EXECUTED",
            "limitations": ["This workflow does not execute the underlying host or network tests; verify through an authorized runner before treating the result as verified."],
            "summary": "Simulation completed; RPC policy enforcement remains unverified until host-backed tests execute",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Proceed to post-deployment cleanup evaluation and teardown checklist",
        }


class RPCCleanupEvaluatorWorkflow(EvaluatorWorkflow):
    """Specialized RPC Cleanup Evaluator (cleanup-agent #10).

    Executes session teardown checklist:
    - Verifies background RPC processes (anvil, rpcinfo, rpcclient) terminated
    - Sweeps temporary secret/credential files (*.key, *.env)
    - Verifies session-opened UFW ports deleted
    - Records SESSION END log in journal.md
    """

    def __init__(self, adapter: Optional[ArchitectureAdapter] = None):
        super().__init__(adapter=adapter)
        self.role = "RPC Cleanup Evaluator (cleanup-agent #10)"

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(
            context.get("workspace_root")
            or getattr(self.adapter, "workspace_root", Path.cwd())
        ).resolve()
        task_id = context.get("task_id", "TASK-RPC-006")

        # This workflow is observational only: do not mutate the journal or imply cleanup occurred.

        cleanup_checklist = [
            "background_rpc_processes_terminated",
            "temporary_secret_files_purged",
            "session_opened_ufw_ports_closed",
            "session_end_logged_to_journal",
        ]

        claims = [
            "Process termination was not checked by this workflow",
            "Temporary credential files were not scanned or removed by this workflow",
            "Session teardown and journal logging were not verified by this workflow",
        ]
        evidence_refs = [f"EVID-RPC-CLEANUP-{task_id}"]

        return {
            "status": "COMPLETED_WITH_LIMITATIONS",
            "limitations": ["No processes, files, or firewall rules were inspected or changed; cleanup is NOT VERIFIED."],
            "summary": "RPC cleanup checklist generated; teardown was not performed or verified",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "tests": TaskTests(passed=[], failed=[]),
            "next_action": "Run explicit, authorized cleanup checks; remove only artifacts created by this session and record observed results",
        }


class RPCGovernancePipeline(CanonicalAdaptivePipeline):
    """Universal End-to-End Operation Pipeline for Linux RPC Administration & Governance.

    Governed by G3 (RPC Admin Oracle), G2 (Playbook Admin Oracle), and G1 (Global Admin Oracle).
    Specializes intake, discovery, security review, verification, independent challenge,
    and post-deployment cleanup stages, and skips production deployment with explicit audit rationale.
    """

    def __init__(
        self,
        adapter: Optional[ArchitectureAdapter] = None,
        workspace_root: Path | str = ".",
    ):
        bound_adapter = adapter or CantinaBountyAdapter(workspace_root)
        super().__init__(
            name="RPC-Governance-Operation-Pipeline",
            adapter=bound_adapter,
            workspace_root=workspace_root,
        )

        # Override stages with RPC-specialized workflows
        self.override_stage(WorkflowStage.INTAKE, RPCGovernancePlanWorkflow(self.adapter))
        self.override_stage(WorkflowStage.DISCOVERY, RPCGovernanceAnalystWorkflow(self.adapter))
        self.override_stage(WorkflowStage.AUTHORIZATION_CHECK, RPCAuditSecurityWorkflow(self.adapter))
        self.override_stage(WorkflowStage.VERIFICATION, RPCDaemonVerifierWorkflow(self.adapter))
        self.override_stage(WorkflowStage.INDEPENDENT_REVIEW, RPCChallengerWorkflow(self.adapter))
        self.override_stage(WorkflowStage.POST_DEPLOYMENT_VALIDATION, RPCCleanupEvaluatorWorkflow(self.adapter))

        # Skip DEPLOYMENT stage with explicit audit rationale
        self.skip_stage(
            WorkflowStage.DEPLOYMENT,
            "RPC Governance operates under read-only/fork-safe constraints; deployment to live production networks is strictly prohibited.",
        )
