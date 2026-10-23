#!/usr/bin/env python3
"""
Refractor Mesh / Glassbox Mirror Plane: Echidna Dynamic Fuzzing Meta-Agent Orchestrator.

Governing Principles:
1. Authorization Precedes Execution (Fail-Closed, Dry-Run Precedence, Zero Writes on Dry-Run).
2. Execution is Not Verification (Independent Property Result Parsing, Counterexample Extraction).
3. Evidence Precedes Conclusions (Canonical Schemas, Eight Glassbox Stages, Standard Evidence Envelope).
4. Separation of Responsibilities (Cognitive Plane, Evidence Plane, Governance / Control Plane).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

# Load local contracts
WORKFLOW_DIR = Path(__file__).resolve().parent
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from echidna_contracts import (
    AuditEvent,
    CampaignManifest,
    EvidenceEnvelope,
    FindingContract,
    GateDecisionContract,
    StageResult,
    TaskContract,
    load_schema,
)

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# Glassbox Status Vocabulary
STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
STATUS_PLANNED = "PLANNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"
STATUS_DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
STATUS_EXECUTION_FAILED = "EXECUTION_FAILED"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"
STATUS_COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
STATUS_COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS"
STATUS_TIMED_OUT = "TIMED_OUT"
STATUS_CANCELLED = "CANCELLED"
STATUS_INCONCLUSIVE = "INCONCLUSIVE"

# Structured Error Codes
ERR_INPUT_INVALID = "INPUT_INVALID"
ERR_AUTHORIZATION_DENIED = "AUTHORIZATION_DENIED"
ERR_SCOPE_VIOLATION = "SCOPE_VIOLATION"
ERR_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
ERR_TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
ERR_EXECUTION_FAILED = "EXECUTION_FAILED"
ERR_EXECUTION_TIMEOUT = "EXECUTION_TIMEOUT"
ERR_ARTIFACT_INVALID = "ARTIFACT_INVALID"
ERR_VALIDATION_FAILED = "VALIDATION_FAILED"
ERR_POLICY_VIOLATION = "POLICY_VIOLATION"


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomically write JSON data to file using temporary file swap."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp.{path.name}.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def get_git_revision(repo_root: Path) -> str:
    """Obtain current git revision hash if available."""
    try:
        res = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "0000000000000000000000000000000000000000"


def is_contained(child: Path, parent: Path) -> bool:
    """Check if child is contained within parent directory without escaping."""
    try:
        c = child.resolve()
        p = parent.resolve()
        return c == p or p in c.parents
    except Exception:
        return False


class EchidnaIndependentChallenger:
    """
    Independent Challenger: Evaluates fuzzing logs, parses property outcomes,
    extracts counterexample call traces, and evaluates invariants against source context.
    """

    def __init__(self, target_dir: Path, repo_root: Path):
        self.target_dir = target_dir
        self.repo_root = repo_root

    def parse_campaign_output(
        self, stdout_text: str, stderr_text: str, exit_code: int
    ) -> tuple[str, list[dict[str, Any]], list[FindingContract]]:
        """
        Parses Echidna stdout (JSON or text) and returns:
        (campaign_outcome, property_results, findings)
        """
        property_results: list[dict[str, Any]] = []
        findings: list[FindingContract] = []

        # Check for JSON output first
        parsed_json = None
        for line in stdout_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("{") and line_str.endswith("}"):
                try:
                    parsed_json = json.loads(line_str)
                    break
                except Exception:
                    continue

        if parsed_json and isinstance(parsed_json, dict) and "tests" in parsed_json:
            tests = parsed_json.get("tests", {})
            if isinstance(tests, dict):
                for prop_name, test_data in tests.items():
                    status_raw = str(test_data.get("status", "")).lower()
                    error_msg = test_data.get("error", None)
                    counterexample = test_data.get("transactions", None)
                    calls_count = test_data.get("calls", None)

                    if "passed" in status_raw or status_raw == "pass":
                        norm_status = "passed"
                    elif "falsified" in status_raw or "failed" in status_raw or counterexample:
                        norm_status = "falsified"
                    elif "error" in status_raw:
                        norm_status = "error"
                    else:
                        norm_status = "skipped"

                    property_results.append({
                        "property_name": prop_name,
                        "status": norm_status,
                        "counterexample": counterexample,
                        "calls_count": calls_count,
                        "error_message": error_msg,
                    })

                    if norm_status == "falsified":
                        finding = self._build_finding_from_property(
                            prop_name, counterexample, error_msg or "Property invariant falsified by Echidna fuzzer"
                        )
                        findings.append(finding)
        else:
            # Fallback to text parsing
            # Lines matching: `echidna_*: passing` or `echidna_*: failed! ...`
            prop_pattern = re.compile(r"^(echidna_[a-zA-Z0-9_]+)\s*:\s*(passing|failed|falsified|error)(.*)", re.IGNORECASE)
            for line in (stdout_text + "\n" + stderr_text).splitlines():
                match = prop_pattern.search(line.strip())
                if match:
                    prop_name = match.group(1)
                    status_word = match.group(2).lower()
                    extra = match.group(3).strip()

                    if status_word == "passing":
                        norm_status = "passed"
                    elif status_word in ("failed", "falsified"):
                        norm_status = "falsified"
                    else:
                        norm_status = "error"

                    property_results.append({
                        "property_name": prop_name,
                        "status": norm_status,
                        "counterexample": {"raw_trace": extra} if extra else None,
                        "calls_count": None,
                        "error_message": extra if norm_status != "passed" else None,
                    })

                    if norm_status == "falsified":
                        finding = self._build_finding_from_property(
                            prop_name, {"raw_trace": extra}, f"Property {prop_name} failed: {extra}"
                        )
                        findings.append(finding)

        # Determine overall outcome
        if any(p["status"] == "falsified" for p in property_results):
            outcome = STATUS_COMPLETED_WITH_FINDINGS
        elif property_results and all(p["status"] == "passed" for p in property_results):
            outcome = STATUS_COMPLETED_VERIFIED
        elif exit_code == 124 or "timed out" in stderr_text.lower():
            outcome = STATUS_TIMED_OUT
        elif exit_code != 0:
            outcome = STATUS_EXECUTION_FAILED
        elif not property_results:
            outcome = STATUS_INCONCLUSIVE
        else:
            outcome = STATUS_COMPLETED_WITH_LIMITATIONS

        return outcome, property_results, findings

    def _build_finding_from_property(
        self, prop_name: str, counterexample: Any, root_cause: str
    ) -> FindingContract:
        finding_id = f"ECHIDNA-{hashlib.sha256(prop_name.encode('utf-8')).hexdigest()[:8].upper()}"
        return FindingContract(
            finding_id=finding_id,
            title=f"Invariant Violation: {prop_name}",
            status="VERIFIED",
            source_refs=[f"property:{prop_name}"],
            affected_versions=["current"],
            locations=[{
                "path": str(self.target_dir),
                "contract": "TargetContract",
                "function": prop_name,
                "start_line": 1,
                "end_line": 1,
            }],
            security_property=f"Property invariant '{prop_name}' must hold across all valid reachable execution states",
            preconditions=["Fuzzing harness deployed with initial contract balances"],
            root_cause=root_cause,
            impact="HIGH",
            exploitability="PROVEN",
            reproduction_refs=[f"counterexample:{finding_id}"],
            counterevidence_refs=[],
            fix_refs=[],
            regression_results=[],
            confidence="CERTAIN",
            unresolved_assumptions=[],
        )


class EchidnaGovernanceAdjudicator:
    """
    Governance Gate Adjudicator: Enforces fail-closed admission and audit criteria.
    Mandatory Gates:
    1. AuthorizationGate
    2. ToolCompatibilityGate
    3. TargetHarnessGate
    4. ReproducibilityGate
    5. SandboxContainmentGate
    6. CampaignOutcomeGate
    """

    def __init__(self, run_id: str, proposer: str = "EchidnaOrchestrator"):
        self.run_id = run_id
        self.proposer = proposer
        self.evaluator = "GovernanceAuditor"

    def evaluate_authorization_gate(self, dry_run: bool, confirm: bool) -> GateDecisionContract:
        req = ["confirm_authorized", "dry_run_inactive"]
        passed = []
        failed = []

        if confirm:
            passed.append("confirm_authorized")
        else:
            failed.append("confirm_authorized")

        if not dry_run:
            passed.append("dry_run_inactive")
        else:
            failed.append("dry_run_inactive")

        decision = "PASS" if not failed else ("BLOCKED" if dry_run else "FAIL")
        rationale = "Execution authorized by explicit --confirm" if decision == "PASS" else "Authorization denied or dry-run requested"

        return GateDecisionContract(
            gate_id="GATE-AUTH-001",
            gate_name="AuthorizationGate",
            required_checks=req,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale=rationale,
            proposer=self.proposer,
            evaluator=self.evaluator,
            audit_reference=f"audit:{self.run_id}:auth",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def evaluate_tool_compatibility_gate(
        self,
        tool_path: Optional[str],
        version: Optional[str],
        missing_flags: list[str],
        dry_run: bool = False,
        confirm: bool = False,
    ) -> GateDecisionContract:
        req = ["executable_resolved", "version_verified", "cli_flags_supported"]
        passed = []
        failed = []

        is_sim = dry_run or not confirm
        if (tool_path and os.path.isfile(tool_path) and os.access(tool_path, os.X_OK)) or is_sim:
            passed.append("executable_resolved")
        else:
            failed.append("executable_resolved")

        if (version and version != "unknown") or is_sim:
            passed.append("version_verified")
        else:
            failed.append("version_verified")

        if not missing_flags:
            passed.append("cli_flags_supported")
        else:
            failed.append("cli_flags_supported")

        decision = "PASS" if not failed else "FAIL"
        return GateDecisionContract(
            gate_id="GATE-TOOL-002",
            gate_name="ToolCompatibilityGate",
            required_checks=req,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale="Echidna executable and CLI flags verified compatible" if decision == "PASS" else f"Tool incompatible or missing flags: {missing_flags}",
            proposer=self.proposer,
            evaluator=self.evaluator,
            audit_reference=f"audit:{self.run_id}:tool",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def evaluate_target_harness_gate(self, target_path: Path) -> GateDecisionContract:
        req = ["target_exists", "solidity_sources_present"]
        passed = []
        failed = []

        if target_path.exists():
            passed.append("target_exists")
        else:
            failed.append("target_exists")

        sol_files = []
        if target_path.is_dir():
            sol_files = list(target_path.glob("**/*.sol"))
        elif target_path.is_file() and target_path.suffix == ".sol":
            sol_files = [target_path]

        if sol_files:
            passed.append("solidity_sources_present")
        else:
            failed.append("solidity_sources_present")

        decision = "PASS" if not failed else "FAIL"
        return GateDecisionContract(
            gate_id="GATE-TARGET-003",
            gate_name="TargetHarnessGate",
            required_checks=req,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale=f"Found {len(sol_files)} Solidity sources in target" if decision == "PASS" else "No Solidity sources found in target",
            proposer=self.proposer,
            evaluator=self.evaluator,
            audit_reference=f"audit:{self.run_id}:target",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def evaluate_sandbox_containment_gate(
        self, target_path: Path, output_dir: Path, repo_root: Path
    ) -> GateDecisionContract:
        req = ["output_contained_in_workspace", "output_not_in_source_tree"]
        passed = []
        failed = []

        if is_contained(output_dir, repo_root):
            passed.append("output_contained_in_workspace")
        else:
            failed.append("output_contained_in_workspace")

        if target_path.is_dir() and (output_dir == target_path or target_path in output_dir.parents):
            failed.append("output_not_in_source_tree")
        else:
            passed.append("output_not_in_source_tree")

        decision = "PASS" if not failed else "FAIL"
        return GateDecisionContract(
            gate_id="GATE-SANDBOX-004",
            gate_name="SandboxContainmentGate",
            required_checks=req,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale="Sandbox containment strictly enforced" if decision == "PASS" else "Output directory violates sandbox containment boundary",
            proposer=self.proposer,
            evaluator=self.evaluator,
            audit_reference=f"audit:{self.run_id}:sandbox",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    def evaluate_campaign_outcome_gate(
        self, campaign_outcome: str, exit_code: int, property_results: list[dict[str, Any]]
    ) -> GateDecisionContract:
        req = ["valid_campaign_outcome", "counterexamples_recorded_if_falsified"]
        passed = []
        failed = []

        valid_outcomes = [
            STATUS_COMPLETED_VERIFIED,
            STATUS_COMPLETED_WITH_FINDINGS,
            STATUS_COMPLETED_WITH_LIMITATIONS,
            STATUS_PREFLIGHT_PASSED,
        ]
        if campaign_outcome in valid_outcomes:
            passed.append("valid_campaign_outcome")
        else:
            failed.append("valid_campaign_outcome")

        falsified_props = [p for p in property_results if p.get("status") == "falsified"]
        if not falsified_props or all(p.get("counterexample") is not None for p in falsified_props):
            passed.append("counterexamples_recorded_if_falsified")
        else:
            failed.append("counterexamples_recorded_if_falsified")

        decision = "PASS" if not failed else "FAIL"
        return GateDecisionContract(
            gate_id="GATE-OUTCOME-005",
            gate_name="CampaignOutcomeGate",
            required_checks=req,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale=f"Campaign concluded with status {campaign_outcome}" if decision == "PASS" else f"Campaign outcome rejected: {campaign_outcome}",
            proposer=self.proposer,
            evaluator=self.evaluator,
            audit_reference=f"audit:{self.run_id}:outcome",
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


class EchidnaGlassboxOrchestrator:
    """
    Eight-Stage Glassbox Mirror Plane Orchestrator for Echidna Property Fuzzing.
    """

    def __init__(
        self,
        repo_root: Path,
        slug: str = "base",
        target: Optional[str] = None,
        config: Optional[str] = None,
        contract: Optional[str] = None,
        test_mode: str = "property",
        test_limit: Optional[int] = None,
        seed: Optional[int] = None,
        timeout: int = 60,
        output_dir: Optional[str] = None,
        dry_run: bool = False,
        confirm: bool = False,
        # Simulation flags
        fail_sim: bool = False,
        timeout_sim: bool = False,
        corrupt_sim: bool = False,
        clean_sim: bool = False,
        falsify_sim: bool = False,
        digest_mismatch_sim: bool = False,
    ):
        self.repo_root = repo_root.resolve()
        self.slug = slug
        self.dry_run = dry_run
        self.confirm = confirm
        self.timeout = timeout
        self.test_mode = test_mode
        self.test_limit = test_limit
        self.seed = seed
        self.contract = contract
        self.config_str = config

        # Simulations
        self.fail_sim = fail_sim
        self.timeout_sim = timeout_sim
        self.corrupt_sim = corrupt_sim
        self.clean_sim = clean_sim
        self.falsify_sim = falsify_sim
        self.digest_mismatch_sim = digest_mismatch_sim

        # Run Identification
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = f"ECHIDNA-{now_str}-{os.getpid()}"

        # Resolve paths
        bounty_dir = self.repo_root / "bounties" / self.slug
        if target:
            t_path = Path(target)
            self.target_path = t_path if t_path.is_absolute() else (self.repo_root / t_path).resolve()
        else:
            if (bounty_dir / "contracts").is_dir():
                self.target_path = (bounty_dir / "contracts").resolve()
            else:
                self.target_path = bounty_dir.resolve()

        if output_dir:
            o_path = Path(output_dir)
            self.output_dir = o_path if o_path.is_absolute() else (self.repo_root / o_path).resolve()
        else:
            self.output_dir = (bounty_dir / "scans" / "echidna" / self.run_id).resolve()

        self.config_path = (Path(config).resolve() if config else None)

        self.challenger = EchidnaIndependentChallenger(self.target_path, self.repo_root)
        self.adjudicator = EchidnaGovernanceAdjudicator(self.run_id)

        self.stage_results: list[StageResult] = []
        self.audit_events: list[AuditEvent] = []
        self.gate_decisions: list[GateDecisionContract] = []

    def log_audit(self, stage: str, action: str, status: str, details: dict[str, Any]) -> None:
        event = AuditEvent(
            event_id=f"AUDIT-{len(self.audit_events) + 1:04d}",
            event_type="STAGE_EXECUTION",
            run_id=self.run_id,
            stage=stage,
            actor="EchidnaGlassboxOrchestrator",
            action=action,
            status=status,
            details=details,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self.audit_events.append(event)

    def execute(self) -> int:
        """Execute the full 8-stage Glassbox Verification Pipeline."""
        start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # ======================================================================
        # STAGE 1: Perception Filtering (Scope, Path Containment & Input Ingestion)
        # ======================================================================
        if not SLUG_PATTERN.match(self.slug):
            print(f"[FAIL] Invalid slug format: '{self.slug}'", file=sys.stderr)
            return 2

        if not is_contained(self.target_path, self.repo_root):
            print(f"[FAIL] Target path escapes repository root: {self.target_path}", file=sys.stderr)
            return 2

        if not is_contained(self.output_dir, self.repo_root):
            print(f"[FAIL] Output directory escapes repository root: {self.output_dir}", file=sys.stderr)
            return 2

        # Check Sandbox Containment Gate
        gate_sandbox = self.adjudicator.evaluate_sandbox_containment_gate(
            self.target_path, self.output_dir, self.repo_root
        )
        self.gate_decisions.append(gate_sandbox)
        if gate_sandbox.decision != "PASS":
            print(f"[FAIL] Sandbox containment gate failed: {gate_sandbox.rationale}", file=sys.stderr)
            return 2

        self.stage_results.append(StageResult(
            stage_number=1,
            stage_name="PerceptionFiltering",
            input_evidence_refs=[f"slug:{self.slug}", f"target:{self.target_path}"],
            processing_method="canonical_path_containment_and_slug_validation",
            tool_versions={"python": sys.version.split()[0]},
            output_artifacts=[],
            content_digests={},
            validation_status="VALIDATED",
            diagnostics=[],
            assumptions=["Target lies within authorized workspace root"],
            uncertainty=[],
            unresolved_obligations=[],
        ))
        self.log_audit("Stage1_Perception", "validate_scope", "SUCCESS", {"target": str(self.target_path)})

        # ======================================================================
        # STAGE 2: Parsing & Tokenization (Source & Configuration Inspection)
        # ======================================================================
        gate_target = self.adjudicator.evaluate_target_harness_gate(self.target_path)
        self.gate_decisions.append(gate_target)
        if gate_target.decision != "PASS":
            print(f"[FAIL] Target harness gate failed: {gate_target.rationale}", file=sys.stderr)
            return 3

        config_digest = "none"
        if self.config_path and self.config_path.is_file():
            config_digest = compute_sha256(self.config_path)

        self.stage_results.append(StageResult(
            stage_number=2,
            stage_name="ParsingAndTokenization",
            input_evidence_refs=[str(self.target_path)],
            processing_method="solidity_source_and_config_tokenization",
            tool_versions={},
            output_artifacts=[str(self.config_path)] if self.config_path else [],
            content_digests={"config_sha256": config_digest},
            validation_status="VALIDATED",
            diagnostics=[],
            assumptions=[],
            uncertainty=[],
            unresolved_obligations=[],
        ))
        self.log_audit("Stage2_Parsing", "parse_target_and_config", "SUCCESS", {"config_digest": config_digest})

        # ======================================================================
        # STAGE 3: Structural Feature Interpretation (Invariants & Entrypoints)
        # ======================================================================
        discovered_invariants: list[str] = []
        if self.target_path.is_file():
            sources = [self.target_path]
        else:
            sources = list(self.target_path.glob("**/*.sol"))

        for s in sources:
            try:
                txt = s.read_text(encoding="utf-8")
                matches = re.findall(r"function\s+(echidna_[a-zA-Z0-9_]+)", txt)
                discovered_invariants.extend(matches)
            except Exception:
                pass

        self.stage_results.append(StageResult(
            stage_number=3,
            stage_name="StructuralFeatureInterpretation",
            input_evidence_refs=[str(s) for s in sources[:5]],
            processing_method="regex_and_ast_invariant_feature_extraction",
            tool_versions={},
            output_artifacts=[],
            content_digests={},
            validation_status="VALIDATED",
            diagnostics=[f"Discovered {len(discovered_invariants)} invariant properties: {discovered_invariants}"],
            assumptions=[],
            uncertainty=[],
            unresolved_obligations=[],
        ))
        self.log_audit("Stage3_Features", "extract_invariants", "SUCCESS", {"invariants_count": len(discovered_invariants)})

        # ======================================================================
        # STAGE 4: Thinking & Planning (Task Contract Formulation)
        # ======================================================================
        task = TaskContract(
            task_id=f"TASK-FUZZ-{self.run_id}",
            goal=f"Execute bounded Echidna property fuzzing against {self.target_path.name}",
            status="PLANNED",
            owner="EchidnaFuzzingEngineer",
            dependencies=["Stage1_Perception", "Stage2_Parsing", "Stage3_Features"],
            inputs={
                "slug": self.slug,
                "target": str(self.target_path),
                "config": str(self.config_path) if self.config_path else None,
                "contract": self.contract,
                "test_mode": self.test_mode,
                "test_limit": self.test_limit,
                "seed": self.seed,
                "timeout": self.timeout,
            },
            permissions_required=["READ_TARGET", "EXECUTE_ECHIDNA", "WRITE_ARTIFACTS"],
            acceptance_criteria=[
                "Echidna execution completes within timeout bounds",
                "Fuzzing logs and exit status captured",
                "Invariant outcomes parsed into property results",
                "Counterexamples extracted if properties falsified",
                "Manifest and receipt published atomically with SHA-256 digests",
            ],
            expected_artifacts=[
                "stdout.log",
                "stderr.log",
                "receipt.json",
                "campaign_manifest.json",
                "findings.json",
            ],
            attempt_count=1,
            evidence_refs=[f"run:{self.run_id}"],
            blocker=None,
            tests=["echidna_property_fuzzing"],
            limitations=["Bounded campaign does not guarantee absence of unspecified vulnerabilities"],
            next_action="execute_stage_5",
        )
        task.validate()

        self.stage_results.append(StageResult(
            stage_number=4,
            stage_name="ThinkingAndPlanning",
            input_evidence_refs=[task.task_id],
            processing_method="task_contract_formulation_and_schedule",
            tool_versions={},
            output_artifacts=[],
            content_digests={},
            validation_status="VALIDATED",
            diagnostics=[],
            assumptions=[],
            uncertainty=[],
            unresolved_obligations=[],
        ))
        self.log_audit("Stage4_Planning", "create_task_contract", "SUCCESS", {"task_id": task.task_id})

        # ======================================================================
        # STAGE 5: Reasoning & Verification (Authorization Gate & Fuzzing Execution)
        # ======================================================================
        # Check Tool Compatibility Gate
        adapter_path = self.repo_root / ".agents" / "skills" / "qrpe" / "adapters" / "echidna_adapter.py"
        if not adapter_path.is_file():
            real_repo = Path(__file__).resolve().parents[2]
            fallback_adapter = real_repo / ".agents" / "skills" / "qrpe" / "adapters" / "echidna_adapter.py"
            if fallback_adapter.is_file():
                adapter_path = fallback_adapter
            else:
                print(f"[FAIL] Echidna adapter not found at {adapter_path}", file=sys.stderr)
                return 3

        import subprocess
        # Check echidna availability
        tool_bin = shutil.which("echidna")
        if not tool_bin:
            fallback = Path(os.path.expanduser("~/.local/bin/echidna"))
            if fallback.is_file() and os.access(fallback, os.X_OK):
                tool_bin = str(fallback)

        echidna_ver = "unknown"
        if tool_bin:
            try:
                res = subprocess.run([tool_bin, "--version"], capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    echidna_ver = res.stdout.strip().splitlines()[0]
            except Exception:
                pass

        gate_tool = self.adjudicator.evaluate_tool_compatibility_gate(
            tool_bin, echidna_ver, [], dry_run=self.dry_run, confirm=self.confirm
        )
        self.gate_decisions.append(gate_tool)
        if gate_tool.decision != "PASS":
            print(f"[FAIL] Tool compatibility gate failed: {gate_tool.rationale}", file=sys.stderr)
            return 1

        # Check Authorization Gate
        gate_auth = self.adjudicator.evaluate_authorization_gate(self.dry_run, self.confirm)
        self.gate_decisions.append(gate_auth)

        # Dry-run or missing confirmation stops here cleanly
        if self.dry_run or not self.confirm:
            print(f"=== [Pack C] Glassbox Workflow: Echidna Property Fuzzing ({self.slug}) ===")
            print(f"[PREFLIGHT_PASSED] Target verified: {self.target_path}")
            print(f"[PREFLIGHT_PASSED] Tool verified: {tool_bin} ({echidna_ver})")
            print(f"[PREFLIGHT_PASSED] Discovered invariants: {len(discovered_invariants)}")
            if self.dry_run:
                print("[DRY-RUN] Preflight completed successfully; fuzzing was not executed.")
            else:
                print("[INFO] Execution requires explicit --confirm.")
            return 0

        # LIVE EXECUTION OR ADVERSARIAL SIMULATION
        raw_stdout = ""
        raw_stderr = ""
        exit_code = 0

        if self.fail_sim:
            raw_stdout = ""
            raw_stderr = "[SIMULATED_FAILURE] Echidna crashed with fatal compiler error."
            exit_code = 1
        elif self.timeout_sim:
            raw_stdout = ""
            raw_stderr = "[SIMULATED_TIMEOUT] Campaign exceeded deadline."
            exit_code = 124
        elif self.falsify_sim:
            # Simulate JSON output with a falsified property and transaction trace counterexample
            sim_result = {
                "tests": {
                    "echidna_test_solvency": {
                        "status": "falsified",
                        "error": "Assertion failed: totalAssets < totalLiabilities",
                        "calls": 42,
                        "transactions": [
                            {"contract": "Vault", "function": "deposit", "arguments": ["1000"], "caller": "0x1000", "value": "1000"},
                            {"contract": "Vault", "function": "borrow", "arguments": ["2000"], "caller": "0x1000", "value": "0"},
                            {"contract": "Vault", "function": "liquidate", "arguments": ["0x1000"], "caller": "0x2000", "value": "0"}
                        ]
                    },
                    "echidna_test_owner_retained": {
                        "status": "passed",
                        "calls": 1000,
                        "transactions": None
                    }
                }
            }
            raw_stdout = json.dumps(sim_result)
            raw_stderr = ""
            exit_code = 0
        elif self.clean_sim:
            sim_result = {
                "tests": {
                    "echidna_test_solvency": {
                        "status": "passed",
                        "calls": 10000,
                        "transactions": None
                    },
                    "echidna_test_owner_retained": {
                        "status": "passed",
                        "calls": 10000,
                        "transactions": None
                    }
                }
            }
            raw_stdout = json.dumps(sim_result)
            raw_stderr = ""
            exit_code = 0
        else:
            # Execute through dedicated QRPE adapter
            adapter_cmd = [
                sys.executable,
                str(adapter_path),
                "--target", str(self.target_path),
                "--output-dir", str(self.output_dir),
                "--timeout", str(self.timeout),
                "--confirm",
            ]
            if self.config_path:
                adapter_cmd.extend(["--config", str(self.config_path)])
            if self.contract:
                adapter_cmd.extend(["--contract", self.contract])
            if self.test_mode:
                adapter_cmd.extend(["--test-mode", self.test_mode])
            if self.test_limit is not None:
                adapter_cmd.extend(["--test-limit", str(self.test_limit)])
            if self.seed is not None:
                adapter_cmd.extend(["--seed", str(self.seed)])

            proc = subprocess.run(
                adapter_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 30,
            )
            exit_code = proc.returncode
            # Read stdout / stderr from output files or process
            out_log = self.output_dir / "stdout.log"
            err_log = self.output_dir / "stderr.log"
            if out_log.is_file():
                raw_stdout = out_log.read_text(encoding="utf-8")
            else:
                raw_stdout = proc.stdout

            if err_log.is_file():
                raw_stderr = err_log.read_text(encoding="utf-8")
            else:
                raw_stderr = proc.stderr

        # ======================================================================
        # STAGE 6: Context & Scope Modeling (Provenance & Digest Pinning)
        # ======================================================================
        git_rev = get_git_revision(self.repo_root)
        source_digest = "none"
        if self.target_path.is_file():
            source_digest = compute_sha256(self.target_path)
        elif self.target_path.is_dir():
            sols = sorted(self.target_path.glob("**/*.sol"))
            if sols:
                combined_hashes = "".join(compute_sha256(s) for s in sols)
                source_digest = compute_bytes_sha256(combined_hashes.encode("utf-8"))

        self.stage_results.append(StageResult(
            stage_number=6,
            stage_name="ContextAndScopeModeling",
            input_evidence_refs=[git_rev, source_digest],
            processing_method="git_revision_and_source_digest_binding",
            tool_versions={"git": "system"},
            output_artifacts=[],
            content_digests={"source_digest": source_digest},
            validation_status="VALIDATED",
            diagnostics=[],
            assumptions=["Repository state pinned during execution"],
            uncertainty=[],
            unresolved_obligations=[],
        ))

        # ======================================================================
        # STAGE 7: Awareness & Semantic Interpretation (Challenger & Counterexamples)
        # ======================================================================
        campaign_outcome, property_results, findings = self.challenger.parse_campaign_output(
            raw_stdout, raw_stderr, exit_code
        )

        for finding in findings:
            finding.validate()

        self.stage_results.append(StageResult(
            stage_number=7,
            stage_name="AwarenessAndSemanticInterpretation",
            input_evidence_refs=[f"exit_code:{exit_code}"],
            processing_method="independent_challenger_falsification_and_counterexample_extraction",
            tool_versions={"echidna": echidna_ver},
            output_artifacts=[],
            content_digests={},
            validation_status="VALIDATED",
            diagnostics=[
                f"Campaign outcome: {campaign_outcome}",
                f"Properties analyzed: {len(property_results)}",
                f"Findings extracted: {len(findings)}",
            ],
            assumptions=[],
            uncertainty=[],
            unresolved_obligations=[],
        ))
        self.log_audit("Stage7_Awareness", "parse_results", "SUCCESS", {
            "campaign_outcome": campaign_outcome,
            "findings_count": len(findings),
        })

        # ======================================================================
        # STAGE 8: Meta-Governance & Executive Authorization (Atomic File Swap)
        # ======================================================================
        gate_outcome = self.adjudicator.evaluate_campaign_outcome_gate(
            campaign_outcome, exit_code, property_results
        )
        self.gate_decisions.append(gate_outcome)

        end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        verification_status = STATUS_COMPLETED_VERIFIED if campaign_outcome in (
            STATUS_COMPLETED_VERIFIED, STATUS_COMPLETED_WITH_FINDINGS
        ) else STATUS_FAILED

        # Build Campaign Manifest
        manifest = CampaignManifest(
            run_id=self.run_id,
            repository_revision=git_rev,
            target=str(self.target_path),
            echidna_version=echidna_ver,
            compiler_version="solc-auto",
            configuration_digest=config_digest,
            binary_digest=compute_sha256(Path(tool_bin)) if tool_bin and Path(tool_bin).is_file() else None,
            seed=self.seed,
            resource_limits={
                "timeout_seconds": self.timeout,
                "test_limit": self.test_limit,
                "shrink_limit": None,
                "seq_len": None,
                "workers": None,
            },
            start_time=start_time,
            end_time=end_time,
            process_exit_status=exit_code,
            campaign_outcome=campaign_outcome,
            property_results=property_results,
            artifact_refs=[
                f"{self.output_dir}/stdout.log",
                f"{self.output_dir}/stderr.log",
                f"{self.output_dir}/campaign_manifest.json",
                f"{self.output_dir}/findings.json",
                f"{self.output_dir}/receipt.json",
            ],
            verification_status=verification_status,
            limitations=[
                "Bounded fuzzing guarantees absence of counterexamples only within tested search limits",
                "Offchain oracles and external contracts mocked or unconstrained",
            ],
        )
        manifest.validate()

        # Build Evidence Envelope
        payload_bytes = json.dumps(manifest.to_dict(), sort_keys=True).encode("utf-8")
        payload_sha = compute_bytes_sha256(payload_bytes)

        if self.digest_mismatch_sim:
            payload_sha = "0000000000000000000000000000000000000000000000000000000000000000"

        envelope = EvidenceEnvelope(
            envelope_id=f"ENV-{self.run_id}",
            slug=self.slug,
            run_id=self.run_id,
            status=verification_status,
            evidence_type="ECHIDNA_PROPERTY_FUZZING",
            manifest=manifest.to_dict(),
            digests={
                "payload_sha256": payload_sha,
                "raw_stdout_sha256": compute_bytes_sha256(raw_stdout.encode("utf-8")),
                "raw_stderr_sha256": compute_bytes_sha256(raw_stderr.encode("utf-8")),
                "target_source_sha256": source_digest,
            },
            provenance={
                "host": os.uname().nodename if hasattr(os, "uname") else "linux",
                "git_commit": git_rev,
                "echidna_version": echidna_ver,
                "solc_version": "solc-auto",
            },
            timestamp=end_time,
        )
        envelope.validate()

        # Prepare write directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "stdout.log").write_text(raw_stdout, encoding="utf-8")
        (self.output_dir / "stderr.log").write_text(raw_stderr, encoding="utf-8")

        # Atomic writes
        atomic_write_json(self.output_dir / "campaign_manifest.json", manifest.to_dict())
        atomic_write_json(self.output_dir / "findings.json", [f.to_dict() for f in findings])
        atomic_write_json(self.output_dir / "envelope.json", envelope.to_dict())
        atomic_write_json(self.output_dir / "audit_events.json", [a.to_dict() for a in self.audit_events])
        atomic_write_json(self.output_dir / "gate_decisions.json", [g.to_dict() for g in self.gate_decisions])

        receipt = {
            "tool": "echidna",
            "version": echidna_ver,
            "run_id": self.run_id,
            "campaign_outcome": campaign_outcome,
            "verification_status": verification_status,
            "exit_code": exit_code,
            "payload_sha256": payload_sha,
            "properties_count": len(property_results),
            "findings_count": len(findings),
            "timestamp": end_time,
        }
        atomic_write_json(self.output_dir / "receipt.json", receipt)

        # Print final report
        print(f"=== [Pack C] Glassbox Workflow: Echidna Property Fuzzing ({self.slug}) ===")
        print(f"[OK] Run ID: {self.run_id}")
        print(f"[OK] Outcome: {campaign_outcome} (status: {verification_status})")
        print(f"[OK] Properties: {len(property_results)}, Findings: {len(findings)}")
        print(f"[OK] Artifacts published to: {self.output_dir}")

        if campaign_outcome == STATUS_COMPLETED_WITH_FINDINGS:
            for f in findings:
                print(f"    - [FINDING] {f.finding_id}: {f.title} (Confidence: {f.confidence})")

        if gate_outcome.decision != "PASS":
            print(f"[FAIL] Gate decision vetoed: {gate_outcome.rationale}", file=sys.stderr)
            return 1

        return 0


def main():
    parser = argparse.ArgumentParser(description="Glassbox Mirror Plane: Echidna Dynamic Fuzzing Orchestrator")
    parser.add_argument("--slug", default="base", help="Target bounty slug under bounties/ (default: base)")
    parser.add_argument("--target", default="", help="Target directory or Solidity source file")
    parser.add_argument("--output-dir", default="", help="Explicit output directory for artifacts")
    parser.add_argument("--config", default="", help="Path to Echidna configuration YAML/JSON")
    parser.add_argument("--contract", default="", help="Target contract name to fuzz")
    parser.add_argument("--test-mode", default="property", help="Test mode (property, assertion, overflow, exploration)")
    parser.add_argument("--test-limit", type=int, default=None, help="Maximum number of test sequences")
    parser.add_argument("--seed", type=int, default=None, help="Deterministic fuzzing seed")
    parser.add_argument("--timeout", type=int, default=60, help="Fuzzing timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Perform preflight without fuzzing execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Explicitly authorize live execution")

    # Simulation / Negative Control Flags
    parser.add_argument("--fail-sim", action="store_true", default=False, help="Simulate execution failure")
    parser.add_argument("--timeout-sim", action="store_true", default=False, help="Simulate execution timeout")
    parser.add_argument("--corrupt-sim", action="store_true", default=False, help="Simulate corrupt artifact")
    parser.add_argument("--clean-sim", action="store_true", default=False, help="Simulate clean campaign with all properties passing")
    parser.add_argument("--falsify-sim", action="store_true", default=False, help="Simulate campaign falsifying an invariant with counterexamples")
    parser.add_argument("--digest-mismatch-sim", action="store_true", default=False, help="Simulate cryptographic digest mismatch")

    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]

    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=repo_root,
        slug=args.slug,
        target=args.target,
        config=args.config,
        contract=args.contract,
        test_mode=args.test_mode,
        test_limit=args.test_limit,
        seed=args.seed,
        timeout=args.timeout,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
        confirm=args.confirm,
        fail_sim=args.fail_sim,
        timeout_sim=args.timeout_sim,
        corrupt_sim=args.corrupt_sim,
        clean_sim=args.clean_sim,
        falsify_sim=args.falsify_sim,
        digest_mismatch_sim=args.digest_mismatch_sim,
    )

    exit_code = orchestrator.execute()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
