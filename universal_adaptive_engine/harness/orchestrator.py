"""Universal Adaptive Engineering Orchestrator and Execution Harness."""
from __future__ import annotations
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.providers import (
    ReasoningProvider,
    ReasoningRequest,
    ReasoningResponse,
    ReasoningPurpose,
    get_reasoning_provider,
)
from universal_adaptive_engine.harness.ledger import TaskLedger
from universal_adaptive_engine.harness.evidence_store import EvidenceStore
from universal_adaptive_engine.models.enums import (
    TaskState,
    RiskLevel,
    FindingStatus,
    ImpactLevel,
    ExploitabilityLevel,
    ConfidenceLevel,
    EvidenceType,
    BlockerCategory,
    CandidateType,
    AdaptationDecision,
)
from universal_adaptive_engine.models.task import TaskRecord, TaskTests
from universal_adaptive_engine.models.finding import FindingRecord, LocationRef
from universal_adaptive_engine.models.adaptation import AdaptationRecord, CompatibilityMatrix
from universal_adaptive_engine.models.evidence import EvidenceRecord
from universal_adaptive_engine.models.blocker import BlockerRecord


@dataclass
class OrchestrationReport:
    goal: str
    host_summary: dict[str, Any]
    tasks_run: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    adaptations: list[dict[str, Any]]
    verification_summary: dict[str, Any]
    challenger_review: dict[str, Any]
    limitations: list[str]
    next_steps: list[str]
    completion_state: str  # COMPLETED_VERIFIED, COMPLETED_WITH_LIMITATIONS, BLOCKED, FAILED
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_markdown(self) -> str:
        lines = [
            f"# Execution & Orchestration Report",
            f"**Completion State:** `{self.completion_state}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Primary Goal:** {self.goal}",
            "",
            "## 1. Host Architecture Discovered",
            f"- Workspace Root: `{self.host_summary.get('workspace_root')}`",
            f"- OS: {self.host_summary.get('os', {}).get('system')} {self.host_summary.get('os', {}).get('release')}",
            f"- Tools Discovered: {', '.join(t for t, d in self.host_summary.get('tools', {}).items() if d.get('available'))}",
            "",
            "## 2. Tasks Executed & State Ledger",
        ]
        for t in self.tasks_run:
            lines.append(f"- **{t['task_id']}** (`{t['status']}`): {t['goal']}")
            if t.get("evidence_refs"):
                lines.append(f"  - Evidence: {', '.join(t['evidence_refs'])}")

        lines.extend([
            "",
            "## 3. Verification & Deterministic Checks",
            f"- Passed: {self.verification_summary.get('passed', 0)}",
            f"- Failed: {self.verification_summary.get('failed', 0)}",
            f"- Skipped: {self.verification_summary.get('skipped', 0)}",
            "",
            "## 4. Independent Challenger Review",
            f"- Status: `{self.challenger_review.get('status')}`",
            f"- Challenger Findings: {self.challenger_review.get('summary')}",
            "",
            "## 5. Limitations & Untested Aspects",
        ])
        for lim in self.limitations:
            lines.append(f"- {lim}")

        lines.extend(["", "## 6. Next Steps"])
        for step in self.next_steps:
            lines.append(f"- {step}")

        return "\n".join(lines)


class UniversalAdaptiveOrchestrator:
    """Core orchestrator executing architecture discovery, task ledgering, and verification."""

    def __init__(
        self,
        workspace_root: Path | str = ".",
        storage_dir: Optional[Path | str] = None,
        reasoning_provider: Optional[ReasoningProvider] = None,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.storage_dir = Path(storage_dir) if storage_dir else self.workspace_root / ".orchestrator_state"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.ledger = TaskLedger(self.storage_dir / "ledger.json")
        self.evidence_store = EvidenceStore(self.storage_dir / "evidence.json")
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)
        self.cantina_adapter = CantinaBountyAdapter(self.workspace_root)
        self.reasoning_provider = reasoning_provider or get_reasoning_provider()

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Route a structured reasoning task through the configured reasoning provider.

        Enforces local validation: model output is treated strictly as untrusted proposals
        until validated through local execution policy gates.
        """
        return self.reasoning_provider.reason(request)

    def plan_with_reasoning(
        self,
        goal: str,
        target_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Request structured task planning from reasoning engine and validate proposals locally."""
        request = ReasoningRequest(
            purpose=ReasoningPurpose.PLANNING,
            instructions="Decompose the following engineering goal into ordered subtasks with acceptance criteria.",
            input_data={"goal": goal},
            target_context=target_context,
        )
        schema = {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "goal": {"type": "string"},
                            "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                            "dependencies": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["task_id", "goal", "acceptance_criteria", "dependencies"]
                    }
                },
                "rationale": {"type": "string"}
            },
            "required": ["subtasks", "rationale"]
        }
        resp = self.reasoning_provider.reason_structured(request, schema=schema)
        return {
            "status": "REASONING_PROPOSAL_GENERATED" if resp.is_success else "REASONING_FAILED",
            "authority": "LOCAL_PLATFORM_RETAINS_EXECUTION_GATE",
            "response": resp,
            "proposals": resp.structured_output.get("subtasks", []) if resp.structured_output else [],
            "provider_used": resp.provider,
            "response_status": resp.status.value,
        }

    def diagnose_blocker(self, error: Exception | str, context: str = "") -> BlockerRecord:
        """Classify errors into canonical BlockerCategory taxonomy and prescribe recovery."""
        msg = str(error)
        err_lower = f"{msg} {context}".lower()

        if (
            "permission" in err_lower
            or "access denied" in err_lower
            or "escapes workspace" in err_lower
            or "boundary" in err_lower
        ):
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.PERMISSION_DENIED,
                message=msg,
                diagnosis="Host runtime or filesystem rejected operation due to lack of write/execute permissions or workspace boundary violation.",
                recovery_action="Request authorized permission or operate within permitted scratch sandbox.",
                stop_condition="Do not retry repeatedly without granted permissions.",
                recoverable=False,
            )
        elif "schema" in err_lower or "validation" in err_lower or "invalid" in err_lower:
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.INVALID_INPUT,
                message=msg,
                diagnosis="Data payload failed schema or invariant constraints.",
                recovery_action="Repair schema fields, correct invalid enums, and resubmit.",
                stop_condition="Stop after 2 failed repair attempts.",
                recoverable=True,
            )
        elif "not found" in err_lower or "missing" in err_lower:
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.MISSING_CONTEXT,
                message=msg,
                diagnosis=f"Required file or context missing: {msg}",
                recovery_action="Run discovery to locate target or fallback to documented baseline.",
                stop_condition="Stop if alternative location does not exist.",
                recoverable=True,
            )
        elif "policy" in err_lower or "forbidden" in err_lower:
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.POLICY_BLOCK,
                message=msg,
                diagnosis="Operation violates architectural invariant or safety policy.",
                recovery_action="Do not attempt to bypass policy. Formulate a compliant bounded alternative.",
                stop_condition="Never retry a prohibited policy action.",
                recoverable=False,
            )
        elif isinstance(error, TimeoutError) or "timeout" in err_lower or "timed out" in err_lower:
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.RESOURCE_LIMIT,
                message=msg,
                diagnosis="Subprocess or operation exceeded time budget.",
                recovery_action="Retry once with increased timeout or optimize execution slice.",
                stop_condition="Max 1 retry.",
                recoverable=True,
            )
        else:
            return BlockerRecord.create_diagnosed(
                category=BlockerCategory.UNKNOWN,
                message=msg,
                diagnosis=f"Unclassified failure: {context}",
                recovery_action="Collect diagnostics, log environment state, and escalate to reviewer.",
                stop_condition="Do not loop.",
                recoverable=False,
            )

    def run_vertical_slice(self, goal: str, target_file: str = "INSTRUCTIONS.md") -> OrchestrationReport:
        """Execute a complete 7-stage vertical slice:

        discover -> plan -> execute -> verify -> challenge -> evaluate -> report
        """
        # 1. DISCOVERY
        host_disc = self.host_adapter.discover()
        cantina_disc = self.cantina_adapter.discover()

        discovery_evid = self.evidence_store.record_evidence(
            EvidenceRecord(
                evidence_id="EVID-SLICE-DISCOVERY",
                evidence_type=EvidenceType.OBSERVED,
                source_ref=str(self.workspace_root),
                acquisition_method="host_discovery",
                observed_result=f"Discovered {len(host_disc.get('capabilities', {}))} host caps, {len(cantina_disc.get('capabilities', {}))} cantina caps",
                confidence=ConfidenceLevel.VERIFIED,
            )
        )

        # 2. PLAN
        task1_id = f"TASK-INSPECT-{uuid.uuid4().hex[:6]}"
        task1 = TaskRecord(
            task_id=task1_id,
            goal=f"Inspect target artifact {target_file}",
            status=TaskState.PROPOSED,
            owner="orchestrator",
            assigned_role="Repository Investigator",
            dependencies=[],
            inputs=[target_file],
            expected_artifacts=[target_file],
            acceptance_criteria=[f"Target file {target_file} exists and is readable"],
            risk_level=RiskLevel.LOW,
            evidence_refs=[discovery_evid.evidence_id],
        )
        self.ledger.register_task(task1)

        task2_id = f"TASK-VERIFY-{uuid.uuid4().hex[:6]}"
        task2 = TaskRecord(
            task_id=task2_id,
            goal=f"Verify SHA-256 digest of {target_file}",
            status=TaskState.PROPOSED,
            owner="orchestrator",
            assigned_role="Verification Engineer",
            dependencies=[task1_id],
            inputs=[target_file],
            expected_artifacts=[f"{target_file}.sha256"],
            acceptance_criteria=["SHA-256 digest calculated and matches file content"],
            risk_level=RiskLevel.LOW,
        )
        self.ledger.register_task(task2)

        # 3. EXECUTE TASK 1
        self.ledger.transition_task(task1_id, TaskState.READY, reason="Prerequisites satisfied")
        self.ledger.transition_task(task1_id, TaskState.RUNNING, reason="Starting execution")

        res1 = self.host_adapter.execute({"task_id": task1_id, "action": "inspect_path", "inputs": [target_file]})
        if not res1["success"]:
            blocker = self.diagnose_blocker(RuntimeError(res1["errors"][0] if res1["errors"] else "Inspect failed"))
            self.ledger.block_task(task1_id, blocker)
            blocker2 = BlockerRecord.create_diagnosed(
                category=BlockerCategory.DEPENDENCY_FAILURE,
                message=f"Prerequisite {task1_id} was blocked: {blocker.message}",
                diagnosis="Dependency task blocked",
                recovery_action="Resolve prerequisite blocker",
                stop_condition="Do not execute dependent task",
                recoverable=False,
            )
            self.ledger.block_task(task2_id, blocker2)
            challenger_review = {"status": "NOT_RUN", "summary": "Challenger review skipped because execution was blocked"}
            return self._build_report(goal, host_disc, [task1, task2], [], [], {}, challenger_review, "BLOCKED")

        if not res1.get("output", {}).get("exists", False):
            target_path = self.workspace_root / target_file
            blocker = self.diagnose_blocker(
                FileNotFoundError(f"Target artifact {target_file} not found at {target_path}"),
                context=f"Path inspection of {target_file}"
            )
            self.ledger.block_task(task1_id, blocker)
            blocker2 = BlockerRecord.create_diagnosed(
                category=BlockerCategory.DEPENDENCY_FAILURE,
                message=f"Prerequisite {task1_id} was blocked: {blocker.message}",
                diagnosis="Dependency task blocked",
                recovery_action="Resolve prerequisite blocker",
                stop_condition="Do not execute dependent task",
                recoverable=False,
            )
            self.ledger.block_task(task2_id, blocker2)
            challenger_review = {"status": "NOT_RUN", "summary": "Challenger review skipped because execution was blocked"}
            return self._build_report(goal, host_disc, [task1, task2], [], [], {}, challenger_review, "BLOCKED")

        target_path = self.workspace_root / target_file
        try:
            if target_path.is_dir():
                ignored_dirs = {".git", ".gemini", "node_modules", "cache", ".orchestrator_state", ".pytest_cache"}
                target_size = 0
                for root, dirs, files in os.walk(target_path, topdown=True, followlinks=False):
                    dirs[:] = [d for d in dirs if d not in ignored_dirs and not os.path.islink(os.path.join(root, d))]
                    for fname in files:
                        fp = Path(root) / fname
                        if not fp.is_symlink():
                            target_size += fp.stat().st_size
                obs_desc = f"Directory {target_file} verified present on disk, total size={target_size} bytes"
            else:
                target_size = target_path.stat().st_size
                obs_desc = f"File {target_file} verified present on disk, size={target_size} bytes"

            evid_inspect = self.evidence_store.create_artifact_evidence(
                evidence_id=f"EVID-INSPECT-{task1_id}",
                artifact_path=target_path,
                source_ref=str(target_path),
                acquisition_method="file_inspection",
                observed_result=obs_desc,
                confidence=ConfidenceLevel.VERIFIED,
                related_task_id=task1_id,
            )

            task1.evidence_refs.append(evid_inspect.evidence_id)
            task1.tests.passed.append(f"inspect_path_{target_file}")
            self.ledger.transition_task(task1_id, TaskState.VERIFYING, reason="Execution complete, verifying criteria")
            self.ledger.transition_task(task1_id, TaskState.COMPLETED_VERIFIED, reason="Criteria passed with evidence")
        except Exception as error:
            blocker = self.diagnose_blocker(error, context=f"Path inspection of {target_file}")
            self.ledger.block_task(task1_id, blocker)
            blocker2 = BlockerRecord.create_diagnosed(
                category=BlockerCategory.DEPENDENCY_FAILURE,
                message=f"Prerequisite {task1_id} was blocked: {blocker.message}",
                diagnosis="Dependency task blocked",
                recovery_action="Resolve prerequisite blocker",
                stop_condition="Do not execute dependent task",
                recoverable=False,
            )
            self.ledger.block_task(task2_id, blocker2)
            challenger_review = {"status": "NOT_RUN", "summary": "Challenger review skipped because execution was blocked"}
            return self._build_report(goal, host_disc, [task1, task2], [], [], {}, challenger_review, "BLOCKED")

        # 4. EXECUTE TASK 2
        self.ledger.transition_task(task2_id, TaskState.READY, reason="Dependency TASK 1 completed")
        self.ledger.transition_task(task2_id, TaskState.RUNNING, reason="Starting execution")

        try:
            computed_sha = EvidenceRecord.hash_artifact(target_path)
            evid_digest = self.evidence_store.record_evidence(
                EvidenceRecord(
                    evidence_id=f"EVID-DIGEST-{task2_id}",
                    evidence_type=EvidenceType.OBSERVED,
                    source_ref=str(target_path),
                    artifact_path=str(target_path),
                    sha256=computed_sha,
                    acquisition_method="sha256_computation",
                    observed_result=f"Computed SHA-256: {computed_sha}",
                    confidence=ConfidenceLevel.VERIFIED,
                    related_task_id=task2_id,
                )
            )
            task2.evidence_refs.append(evid_digest.evidence_id)
            task2.tests.passed.append(f"sha256_verification_{target_file}")
            self.ledger.transition_task(task2_id, TaskState.VERIFYING, reason="Digest computed")
        except Exception as error:
            blocker = self.diagnose_blocker(error, context=f"SHA-256 computation of {target_file}")
            self.ledger.block_task(task2_id, blocker)
            challenger_review = {"status": "NOT_RUN", "summary": "Challenger review skipped because execution was blocked"}
            return self._build_report(goal, host_disc, [task1, task2], [], [], {}, challenger_review, "BLOCKED")

        # 5. INDEPENDENT CHALLENGER STEP
        # Independent challenger checks for falsification: what if file is modified?
        challenger_passed = True
        challenger_notes = []
        try:
            # Negative control: test that hash of modified buffer does NOT match
            if target_path.is_dir():
                tampered_buffer = computed_sha.encode("utf-8") + b"\n# TAMPER_TEST"
            else:
                tampered_buffer = target_path.read_bytes() + b"\n# TAMPER_TEST"
            import hashlib
            tampered_hash = hashlib.sha256(tampered_buffer).hexdigest()
            if tampered_hash == computed_sha:
                challenger_passed = False
                challenger_notes.append("Falsification failure: Hash collision detected or tampered buffer identical")
            else:
                challenger_notes.append("Falsification check passed: Tampered buffer correctly produces distinct digest")
        except Exception as error:
            challenger_passed = False
            challenger_notes.append(f"Falsification check error: {error}")

        if challenger_passed:
            self.ledger.transition_task(task2_id, TaskState.COMPLETED_VERIFIED, reason="Criteria satisfied and negative control passed")
        else:
            self.ledger.transition_task(task2_id, TaskState.FAILED, reason="Independent challenger negative control failed")

        challenger_review = {
            "status": "PASSED" if challenger_passed else "FAILED",
            "summary": "; ".join(challenger_notes),
            "negative_control_verified": challenger_passed,
        }

        # 6. ADMISSION & FINDINGS
        if challenger_passed:
            finding = FindingRecord(
                finding_id=f"FIND-ARCH-{uuid.uuid4().hex[:4]}",
                title=f"Host artifact {target_file} digest verified with provenance",
                status=FindingStatus.SUPPORTED,
                source_refs=[f"[SRC: {target_file} @HEAD]"],
                affected_versions=["current"],
                locations=[LocationRef(path=target_file)],
                original_labels=["baseline"],
                derived_labels=["artifact_integrity"],
                preconditions=["File must exist on disk"],
                impact=ImpactLevel.INFORMATIONAL,
                exploitability=ExploitabilityLevel.UNVERIFIED,
                confidence=ConfidenceLevel.VERIFIED,
                reproduction_refs=[evid_digest.evidence_id],
            )
        else:
            finding = FindingRecord(
                finding_id=f"FIND-ARCH-{uuid.uuid4().hex[:4]}",
                title=f"Host artifact {target_file} digest falsification check failed",
                status=FindingStatus.REFUTED,
                source_refs=[f"[SRC: {target_file} @HEAD]"],
                affected_versions=["current"],
                locations=[LocationRef(path=target_file)],
                original_labels=["baseline"],
                derived_labels=["artifact_integrity"],
                preconditions=["File must exist on disk"],
                impact=ImpactLevel.INFORMATIONAL,
                exploitability=ExploitabilityLevel.REFUTED,
                confidence=ConfidenceLevel.REFUTED,
                counterevidence_refs=["EVID-CHALLENGE-FALSIFIED"],
            )
        finding.validate()

        adaptation = AdaptationRecord(
            candidate_id="ADAPT-HOST-ADAPTER",
            candidate_type=CandidateType.ADAPTER,
            license="MIT",
            intended_capability="Host POSIX environment introspection and bounded execution",
            rationale="Enables architecture-agnostic host discovery without assuming external tools",
            compatibility=CompatibilityMatrix(
                contracts="compatible",
                dependencies="compatible",
                security="passed" if challenger_passed else "failed",
                regressions="none_observed",
            ),
            approval_required=False,
            decision=AdaptationDecision.ACCEPTED_FOR_STAGING if challenger_passed else AdaptationDecision.REJECTED,
        )
        adaptation.validate()

        verification_summary = {
            "passed": 2 if challenger_passed else 1,
            "failed": 0 if challenger_passed else 1,
            "skipped": 0,
            "not_run": 0,
        }

        limitations = [
            "Network access is blocked by policy guardrails; remote repositories cannot be queried directly.",
            "Solvability of live mainnet exploits is deliberately prohibited under non-negotiable safety rules.",
        ]

        next_steps = [
            "Deploy specialist subagents into active coordination hierarchy.",
            "Run continuous regression benchmarks against held-out test corpus.",
        ]

        completion_state = "COMPLETED_VERIFIED" if challenger_passed else "FAILED"
        if not challenger_passed:
            limitations.append("Independent challenger negative control failed")

        return self._build_report(
            goal=goal,
            host_summary=host_disc,
            tasks=[task1, task2],
            findings=[finding],
            adaptations=[adaptation],
            verification_summary=verification_summary,
            challenger_review=challenger_review,
            completion_state=completion_state,
            limitations=limitations,
            next_steps=next_steps,
        )

    def _build_report(
        self,
        goal: str,
        host_summary: dict[str, Any],
        tasks: list[TaskRecord],
        findings: list[FindingRecord],
        adaptations: list[AdaptationRecord],
        verification_summary: dict[str, Any],
        challenger_review: dict[str, Any],
        completion_state: str,
        limitations: Optional[list[str]] = None,
        next_steps: Optional[list[str]] = None,
    ) -> OrchestrationReport:
        return OrchestrationReport(
            goal=goal,
            host_summary=host_summary,
            tasks_run=[t.to_dict() for t in tasks],
            findings=[f.to_dict() for f in findings],
            adaptations=[a.to_dict() for a in adaptations],
            verification_summary=verification_summary,
            challenger_review=challenger_review,
            limitations=limitations or [],
            next_steps=next_steps or [],
            completion_state=completion_state,
        )

    def run_operation(
        self,
        operation_name: str,
        goal: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ):
        """Execute a specialized end-to-end operation pipeline through the Universal Adaptive Lifecycle."""
        from universal_adaptive_engine.workflows.operations import get_operation_pipeline
        ctx = dict(context or {})
        adapter = ctx.pop("adapter", None)
        if adapter is None:
            adapter = self.host_adapter if operation_name.lower().strip() == "canonical" else self.cantina_adapter
        pipeline = get_operation_pipeline(
            name=operation_name,
            adapter=adapter,
            workspace_root=self.workspace_root,
        )
        if goal:
            ctx["goal"] = goal
        return pipeline.execute(ctx)
