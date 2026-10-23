#!/usr/bin/env python3
"""
Oracle Agentic Mesh (OAM) Orchestrator & SAMA Triage Engine for Aderyn Static Analysis.

Governing Principles:
1. Authorization Precedes Execution (Fail-Closed, Dry-Run Precedence).
2. Execution is Not Validation (Independent Artifact Verification & Cryptographic Checks).
3. Evidence Precedes Conclusions (Standard Evidence Envelope, Deterministic State Transitions).
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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# Consistent OAM Status Vocabulary
STATUS_PLANNED = "PLANNED"
STATUS_BLOCKED = "BLOCKED"
STATUS_DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
STATUS_RUNNING = "RUNNING"
STATUS_EXECUTION_FAILED = "EXECUTION_FAILED"
STATUS_EXECUTED_UNVALIDATED = "EXECUTED_UNVALIDATED"
STATUS_VALIDATION_FAILED = "VALIDATION_FAILED"
STATUS_COMPLETED_WITH_FINDINGS = "COMPLETED_WITH_FINDINGS"
STATUS_COMPLETED_CLEAN = "COMPLETED_CLEAN"
STATUS_PARTIAL = "PARTIAL"
STATUS_CANCELLED = "CANCELLED"

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
ERR_ATTRIBUTION_MISMATCH = "ATTRIBUTION_MISMATCH"
ERR_POLICY_VIOLATION = "POLICY_VIOLATION"


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> str:
    """Atomically write JSON data using temporary file swap and verified read-back digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp.{path.name}.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Verify tmp file parses before swap
        with open(tmp_path, "r", encoding="utf-8") as f:
            json.load(f)
        os.replace(tmp_path, path)
        # Read-back verification
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        return digest
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def get_git_revision(repo_root: Path) -> Optional[str]:
    """Obtain current git revision hash if available; returns None if unknown."""
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
    return None


def resolve_aderyn_tool() -> Optional[str]:
    """Discover aderyn executable on PATH or standard directory locations."""
    t = shutil.which("aderyn")
    if t:
        return t
    home = os.path.expanduser("~")
    for d in [".local/bin", ".cargo/bin", ".foundry/bin"]:
        p = os.path.join(home, d, "aderyn")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def parse_tooling_registry(tooling_md_path: Path) -> dict[str, dict[str, str]]:
    """Parse tool statuses and versions from global/tooling.md."""
    registry = {"aderyn": {"version": "0.6.8", "status": "OK"}}
    if not tooling_md_path.is_file():
        return registry
    try:
        content = tooling_md_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("|") and not line.startswith("| Tool") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    tool_name = parts[1].lower()
                    status = parts[5].upper()
                    version = parts[6]
                    registry[tool_name] = {"version": version, "status": status}
    except Exception:
        pass
    return registry


class OAMAderynOrchestrator:
    def __init__(
        self,
        repo_root: Path,
        slug: str,
        target_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
        confirm: bool = False,
        timeout: int = 300,
        adapter_path: Optional[Path] = None,
        # Simulation flags for adversarial negative control testing
        scanner_fail_sim: bool = False,
        fail_receipt_sim: bool = False,
        timeout_sim: bool = False,
        corrupt_report_sim: bool = False,
        digest_mismatch_sim: bool = False,
        attribution_mismatch_sim: bool = False,
        empty_report_sim: bool = False,
        version_drift_sim: bool = False,
        clean_sim: bool = False,
    ):
        self.repo_root = repo_root.resolve()
        self.slug = slug
        self.dry_run = dry_run
        self.confirm = confirm
        self.timeout = timeout

        self.scanner_fail_sim = scanner_fail_sim
        self.fail_receipt_sim = fail_receipt_sim
        self.timeout_sim = timeout_sim
        self.corrupt_report_sim = corrupt_report_sim
        self.digest_mismatch_sim = digest_mismatch_sim
        self.attribution_mismatch_sim = attribution_mismatch_sim
        self.empty_report_sim = empty_report_sim
        self.version_drift_sim = version_drift_sim
        self.clean_sim = clean_sim

        self.run_id = f"run-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
        self.task_id = "task-pack-b-aderyn"
        self.agent_id = "SAMA-OAM-PACK-B"
        self.state_history: list[dict[str, str]] = []
        self.terminal_status: str = STATUS_PLANNED
        self.error_code: Optional[str] = None
        self.error_message: Optional[str] = None

        # Resolve paths
        self.raw_target_dir = target_dir
        self.raw_output_dir = output_dir

        self.bounty_dir = (self.repo_root / "bounties" / slug).resolve()
        if target_dir:
            self.target_dir = target_dir.resolve()
        else:
            contracts_dir = self.bounty_dir / "contracts"
            self.target_dir = contracts_dir.resolve() if contracts_dir.exists() else self.bounty_dir
            self.raw_target_dir = self.target_dir

        if output_dir:
            self.output_dir = output_dir.resolve()
        else:
            self.output_dir = (self.bounty_dir / "scans" / "aderyn").resolve()
            self.raw_output_dir = self.output_dir

        if adapter_path:
            self.adapter_path = adapter_path.resolve()
        else:
            self.adapter_path = (self.repo_root / ".agents" / "skills" / "qrpe" / "adapters" / "aderyn_adapter.py").resolve()

        self.tooling_registry = parse_tooling_registry(self.repo_root / "global" / "tooling.md")

        # Process and validation tracking
        self.adapter_exit_code = 0
        self.scanner_exit_code: Optional[int] = 0
        self.scanner_version: Optional[str] = None
        self.duration_seconds = 0.0
        self.start_time: str = ""
        self.end_time: str = ""
        self.last_stderr: str = ""
        self.artifacts_evidence: list[dict[str, Any]] = []
        self.triaged_findings: list[dict[str, Any]] = []
        self.validation_results = {
            "receipt_present": False,
            "report_present": False,
            "digest_verified": False,
            "schema_conformant": False,
            "attribution_verified": False,
            "exit_code_consistent": False,
        }
        self.findings_summary = {
            "total_findings": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }
        self.scanner_command: list[str] = []

    def record_state(self, state: str, detail: str = "") -> None:
        """Record monotonic state transition with UTC timestamp."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.state_history.append({"state": state, "timestamp": ts, "detail": detail})

    def run_lifecycle(self) -> int:
        """Execute the 10-stage OAM state machine."""
        self.start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.record_state("INTAKE", f"Initiated workflow with slug='{self.slug}'")

        # Stage 1: INTAKE & POLICY_CHECK
        self.record_state("POLICY_CHECK", "Evaluating scope, permissions, and execution boundaries")
        if not SLUG_PATTERN.match(self.slug):
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_SCOPE_VIOLATION
            self.error_message = f"Invalid slug pattern: '{self.slug}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 2

        # Check path containment
        try:
            if not self.target_dir.is_relative_to(self.repo_root):
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_SCOPE_VIOLATION
                self.error_message = f"Target directory '{self.target_dir}' escapes repository root '{self.repo_root}'"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 2

            if not self.output_dir.is_relative_to(self.repo_root):
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_SCOPE_VIOLATION
                self.error_message = f"Output directory '{self.output_dir}' escapes repository root '{self.repo_root}'"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 2
        except Exception as e:
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_SCOPE_VIOLATION
            self.error_message = f"Path containment check failed: {e}"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 2

        # Symlink check on target and output boundaries
        if self.raw_target_dir and self.raw_target_dir.is_symlink():
            resolved = self.raw_target_dir.resolve()
            if not resolved.is_relative_to(self.repo_root):
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_SCOPE_VIOLATION
                self.error_message = f"Target symlink escapes repository root: '{resolved}'"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 2

        if self.raw_output_dir and self.raw_output_dir.is_symlink():
            resolved = self.raw_output_dir.resolve()
            if not resolved.is_relative_to(self.repo_root):
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_SCOPE_VIOLATION
                self.error_message = f"Output symlink escapes repository root: '{resolved}'"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 2

        # Stage 2: PREFLIGHT
        self.record_state("PREFLIGHT", "Verifying tools, interpreters, adapter, and target scope")
        if not self.bounty_dir.exists():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Target bounty directory does not exist: '{self.bounty_dir}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        if not self.target_dir.exists():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Target directory does not exist: '{self.target_dir}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        if not self.adapter_path.is_file():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Adapter script missing: '{self.adapter_path}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        tool_exec = resolve_aderyn_tool()
        if not tool_exec:
            if self.dry_run or not self.confirm:
                tool_exec = Path("/usr/local/bin/aderyn")
            else:
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_TOOL_UNAVAILABLE
                self.error_message = "Aderyn scanner executable not found on PATH or standard directories"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 3

        aderyn_reg = self.tooling_registry.get("aderyn", {})
        if aderyn_reg.get("status") != "OK":
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_TOOL_UNAVAILABLE
            self.error_message = f"Aderyn tool status is '{aderyn_reg.get('status')}', expected 'OK'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        # Stage 3: PLANNED
        self.record_state("PLANNED", "Preflight passed; evaluating authorization mode")
        write_allowed = self.confirm and not self.dry_run

        if not write_allowed:
            # DRY-RUN path
            self.record_state("DRY_RUN_COMPLETE", "Simulating dry-run preview via adapter")
            self.terminal_status = STATUS_DRY_RUN_COMPLETE
            # Execute adapter in dry-run mode to verify flags
            dry_cmd = [
                sys.executable,
                str(self.adapter_path),
                "--target", str(self.target_dir),
                "--output-dir", str(self.output_dir),
                "--dry-run",
            ]
            res = subprocess.run(dry_cmd, capture_output=True, text=True)
            print(res.stdout.strip())
            if res.returncode != 0:
                print(res.stderr.strip(), file=sys.stderr)
                return 1
            print(f"[DRY-RUN] Verified Aderyn plan for target: {self.target_dir}")
            print(f"[DRY-RUN] Output will be written to: {self.output_dir}/aderyn.json upon --confirm")
            return 0

        # Stage 4: LIVE_READY
        self.record_state("LIVE_READY", "Authorization confirmed; write permitted")

        # Stage 5: RUNNING
        self.record_state("RUNNING", "Invoking Aderyn adapter under supervised execution")
        adapter_cmd = [
            sys.executable,
            str(self.adapter_path),
            "--target", str(self.target_dir),
            "--output-dir", str(self.output_dir),
            "--confirm",
            "--timeout", str(self.timeout),
        ]
        if self.scanner_fail_sim:
            adapter_cmd.append("--scanner-fail-sim")
        if self.fail_receipt_sim:
            adapter_cmd.append("--fail-receipt-sim")
        if self.timeout_sim:
            adapter_cmd.append("--timeout-sim")

        t0 = datetime.datetime.now()
        adapter_stdout = ""
        adapter_stderr = ""
        try:
            adapter_proc = subprocess.run(
                adapter_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 15,
            )
            self.duration_seconds = (datetime.datetime.now() - t0).total_seconds()
            self.adapter_exit_code = adapter_proc.returncode
            adapter_stdout = adapter_proc.stdout
            adapter_stderr = adapter_proc.stderr
        except subprocess.TimeoutExpired:
            self.duration_seconds = (datetime.datetime.now() - t0).total_seconds()
            self.adapter_exit_code = 124
            adapter_stderr = f"Orchestrator timeout: adapter execution exceeded {self.timeout + 15}s"

        self.last_stderr = adapter_stderr

        # Stage 6: EXECUTED_UNVALIDATED
        self.record_state(
            "EXECUTED_UNVALIDATED",
            f"Adapter returned exit code {self.adapter_exit_code}; beginning independent validation",
        )

        # Stage 7: VALIDATING
        self.record_state("VALIDATING", "Performing independent artifact, cryptographic, and schema validation")
        val_success, val_exit_code = self._perform_independent_validation()

        # Handle post-scan baseline simulations (e.g. clean baseline)
        if self.clean_sim:
            report_file = self.output_dir / "aderyn.json"
            clean_data = {
                "files_summary": {"total_source_units": 1, "total_sloc": 10},
                "issue_count": {"high": 0, "low": 0},
                "high_issues": {"issues": []},
                "low_issues": {"issues": []},
                "critical_issues": {"issues": []},
                "medium_issues": {"issues": []},
                "nc_issues": {"issues": []},
            }
            report_file.write_text(json.dumps(clean_data, indent=2))
            actual_sha = compute_sha256(report_file)
            receipt_file = self.output_dir / "receipt.json"
            receipt_data = {
                "tool": "aderyn",
                "version": "0.6.8",
                "command": [
                    "aderyn",
                    str(self.target_dir),
                    "--output",
                    str(report_file),
                ],
                "target": str(self.target_dir),
                "exit_code": 0,
                "duration_seconds": 0.05,
                "output_file": str(report_file),
                "sha256": actual_sha,
            }
            receipt_file.write_text(json.dumps(receipt_data, indent=2))
            val_success, val_exit_code = self._perform_independent_validation()

        # Handle post-scan adversarial corruption simulations
        if self.corrupt_report_sim:
            report_file = self.output_dir / "aderyn.json"
            if report_file.exists():
                report_file.write_text("{ corrupt json: broken !!!")
                # Re-validate
                val_success, val_exit_code = self._perform_independent_validation()

        if self.digest_mismatch_sim:
            receipt_file = self.output_dir / "receipt.json"
            if receipt_file.exists():
                rdata = json.loads(receipt_file.read_text())
                rdata["sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
                receipt_file.write_text(json.dumps(rdata, indent=2))
                val_success, val_exit_code = self._perform_independent_validation()

        if self.attribution_mismatch_sim:
            report_file = self.output_dir / "aderyn.json"
            if report_file.exists():
                rdata = {
                    "high_issues": {
                        "issues": [
                            {
                                "title": "Alien Scope Finding",
                                "description": "Finding in unapproved repository",
                                "instances": [{"contract_path": "/alien/outside/scope/Evil.sol", "line_no": 1}],
                            }
                        ]
                    }
                }
                report_file.write_text(json.dumps(rdata, indent=2))
                receipt_file = self.output_dir / "receipt.json"
                if receipt_file.exists():
                    r_json = json.loads(receipt_file.read_text())
                    r_json["sha256"] = compute_sha256(report_file)
                    receipt_file.write_text(json.dumps(r_json, indent=2))
                val_success, val_exit_code = self._perform_independent_validation()

        if self.empty_report_sim:
            report_file = self.output_dir / "aderyn.json"
            if report_file.exists():
                report_file.unlink()
                val_success, val_exit_code = self._perform_independent_validation()

        if not val_success:
            self.record_state(self.terminal_status, self.error_message or "Validation failed")
            self._write_evidence_envelope()
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            if self.last_stderr.strip():
                print(f"       Details: {self.last_stderr.strip()}", file=sys.stderr)
            return val_exit_code

        # Stage 8: TRIAGING (SAMA Capability)
        self.record_state("TRIAGING", "Ingesting validated Aderyn report and triaging findings")
        self._triage_findings()

        # Stage 9: REPORTING & TERMINAL_STATUS
        self.record_state("REPORTING", "Assembling standard evidence envelope")
        if self.findings_summary["total_findings"] > 0:
            self.terminal_status = STATUS_COMPLETED_WITH_FINDINGS
        else:
            self.terminal_status = STATUS_COMPLETED_CLEAN

        self.record_state(self.terminal_status, f"Workflow finished with status {self.terminal_status}")
        self._write_evidence_envelope()

        print(f"[OK] Aderyn OAM scan completed successfully in {self.duration_seconds:.2f}s")
        print(f"     Status: {self.terminal_status}")
        print(f"     Findings: {self.findings_summary['total_findings']} total "
              f"({self.findings_summary['critical']} critical, {self.findings_summary['high']} high, "
              f"{self.findings_summary['medium']} medium, {self.findings_summary['low']} low)")
        print(f"     Evidence envelope: {self.output_dir / 'evidence_envelope.json'}")
        return 0

    def _perform_independent_validation(self) -> Tuple[bool, int]:
        """Independently validate outputs without trusting adapter assertions."""
        receipt_file = self.output_dir / "receipt.json"
        report_file = self.output_dir / "aderyn.json"

        # 1. Receipt validation
        if not receipt_file.exists():
            self.terminal_status = STATUS_EXECUTION_FAILED if self.adapter_exit_code != 0 else STATUS_VALIDATION_FAILED
            self.error_code = ERR_EXECUTION_FAILED if self.adapter_exit_code != 0 else ERR_ARTIFACT_INVALID
            self.error_message = f"Receipt file missing at '{receipt_file}'"
            return False, 1
        self.validation_results["receipt_present"] = True

        try:
            receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
        except Exception as e:
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = f"Receipt file contains malformed JSON: {e}"
            return False, 1

        self.scanner_exit_code = receipt_data.get("exit_code")
        self.scanner_command = receipt_data.get("command", [])
        self.scanner_version = receipt_data.get("version")

        if self.scanner_exit_code is None or not isinstance(self.scanner_exit_code, int):
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = "Receipt missing valid integer 'exit_code' field"
            return False, 1

        # Check scanner exit code and adapter exit code
        if self.scanner_exit_code != 0 or self.adapter_exit_code != 0:
            self.terminal_status = STATUS_EXECUTION_FAILED
            self.error_code = ERR_EXECUTION_TIMEOUT if (self.scanner_exit_code == 124 or self.adapter_exit_code == 124) else ERR_EXECUTION_FAILED
            self.error_message = f"Scanner failed with exit code {self.scanner_exit_code} (adapter exit code {self.adapter_exit_code})"
            return False, 1

        self.validation_results["exit_code_consistent"] = True

        # 2. Report existence
        if not report_file.exists():
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = f"Scanner reported success (exit 0) but report file missing: '{report_file}'"
            return False, 1
        self.validation_results["report_present"] = True

        # 3. Report JSON integrity
        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception as e:
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = f"Aderyn report contains malformed JSON: {e}"
            return False, 1

        # 4. Independent SHA-256 Digest Verification
        actual_sha = compute_sha256(report_file)
        expected_sha = receipt_data.get("sha256", "")
        if not expected_sha or actual_sha.lower() != expected_sha.lower():
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_VALIDATION_FAILED
            self.error_message = f"Artifact SHA-256 mismatch! Actual: {actual_sha}, Receipt: {expected_sha}"
            return False, 1
        self.validation_results["digest_verified"] = True

        # 5. Schema Conformity Check
        if not isinstance(report_data, dict):
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = "Aderyn report root must be a JSON object"
            return False, 1

        aderyn_structural_keys = {"files_summary", "issue_count", "high_issues", "low_issues", "detectors_used", "critical_issues", "medium_issues", "nc_issues"}
        if not any(k in report_data for k in aderyn_structural_keys):
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = "Aderyn report missing recognizable schema structure"
            return False, 1

        self.validation_results["schema_conformant"] = True

        # 6. Attribution Verification
        if not self._verify_report_attribution(report_data):
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ATTRIBUTION_MISMATCH
            self.error_message = "Report attribution validation failed: finding references alien paths outside scope"
            return False, 1
        self.validation_results["attribution_verified"] = True

        # Collect artifacts evidence
        report_rel = str(report_file.relative_to(self.repo_root)) if report_file.is_relative_to(self.repo_root) else str(report_file)
        receipt_rel = str(receipt_file.relative_to(self.repo_root)) if receipt_file.is_relative_to(self.repo_root) else str(receipt_file)
        self.artifacts_evidence = [
            {
                "name": "aderyn.json",
                "path": report_rel,
                "size_bytes": report_file.stat().st_size,
                "sha256": actual_sha,
                "validation_status": "VALID",
            },
            {
                "name": "receipt.json",
                "path": receipt_rel,
                "size_bytes": receipt_file.stat().st_size,
                "sha256": compute_sha256(receipt_file),
                "validation_status": "VALID",
            },
        ]
        return True, 0

    def _verify_report_attribution(self, report_data: dict[str, Any]) -> bool:
        """Verify that issues reported in aderyn.json attribute to in-scope files."""
        severity_keys = ["critical_issues", "high_issues", "medium_issues", "low_issues", "nc_issues"]
        for k in severity_keys:
            issues = report_data.get(k, {}).get("issues", [])
            for issue in issues:
                for inst in issue.get("instances", []):
                    cpath = inst.get("contract_path", "")
                    if not cpath:
                        continue
                    cpath = cpath.replace("\\", "/")
                    if cpath.startswith("/alien/") or ".." in cpath:
                        return False
                    if cpath.startswith("/"):
                        p = Path(cpath).resolve()
                        if not p.is_relative_to(self.repo_root):
                            return False
                    else:
                        p = (self.target_dir / cpath).resolve()
                        if not (p.is_relative_to(self.target_dir) or p.is_relative_to(self.repo_root)):
                            return False
        return True

    def _triage_findings(self) -> None:
        """SAMA Finding Triage: Extract and categorize issues from aderyn.json."""
        report_file = self.output_dir / "aderyn.json"
        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception:
            return

        crit = len(report_data.get("critical_issues", {}).get("issues", []))
        high = len(report_data.get("high_issues", {}).get("issues", []))
        med = len(report_data.get("medium_issues", {}).get("issues", []))
        low = len(report_data.get("low_issues", {}).get("issues", []))
        nc = len(report_data.get("nc_issues", {}).get("issues", []))

        self.findings_summary = {
            "total_findings": crit + high + med + low + nc,
            "critical": crit,
            "high": high,
            "medium": med,
            "low": low,
            "informational": nc,
        }

        # Extract normalized triaged findings preserving scanner raw severity & assessed severity
        self.triaged_findings = []
        severity_mapping = {
            "critical_issues": ("critical", "CRITICAL"),
            "high_issues": ("high", "HIGH"),
            "medium_issues": ("medium", "MEDIUM"),
            "low_issues": ("low", "LOW"),
            "nc_issues": ("informational", "INFORMATIONAL"),
        }
        for bucket_key, (raw_sev, assessed_sev) in severity_mapping.items():
            issues = report_data.get(bucket_key, {}).get("issues", [])
            for issue in issues:
                det_name = issue.get("detector_name") or issue.get("title", "unnamed").lower().replace(" ", "-")
                instances = issue.get("instances", [])
                locations = [
                    f"{inst.get('contract_path', '')}:{inst.get('line_no', 0)}"
                    for inst in instances[:5]
                ]
                self.triaged_findings.append({
                    "detector_name": det_name,
                    "title": issue.get("title", det_name),
                    "scanner_severity": raw_sev,
                    "assessed_severity": assessed_sev,
                    "instances_count": len(instances),
                    "sample_locations": locations,
                })

    def _write_evidence_envelope(self) -> None:
        """Atomically persist the standard evidence envelope."""
        self.end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        target_path_str = str(self.target_dir.relative_to(self.repo_root)) if self.target_dir.is_relative_to(self.repo_root) else str(self.target_dir)
        output_boundary_str = str(self.output_dir.relative_to(self.repo_root)) if self.output_dir.is_relative_to(self.repo_root) else str(self.output_dir)

        envelope = {
            "$schema": "https://raw.githubusercontent.com/cantina/schemas/v1/evidence_envelope.schema.json",
            "schema_version": "1.0.0",
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "operation": "aderyn_static_analysis",
            "execution_mode": "LIVE" if (self.confirm and not self.dry_run) else "DRY_RUN",
            "repository": {
                "root": str(self.repo_root),
                "revision": get_git_revision(self.repo_root),
                "target_path": target_path_str,
                "canonical_target": str(self.target_dir),
                "output_boundary": output_boundary_str,
            },
            "authorization": {
                "policy_version": "1.0.0",
                "confirmed": self.confirm,
                "dry_run": self.dry_run,
                "write_allowed": self.confirm and not self.dry_run,
                "approval_reference": "OPERATOR_CLI_CONFIRM" if self.confirm else None,
            },
            "process_execution": {
                "tool": "aderyn",
                "tool_version": self.scanner_version or self.tooling_registry.get("aderyn", {}).get("version"),
                "command": self.scanner_command or [
                    "aderyn",
                    str(self.target_dir),
                    "--output",
                    str(self.output_dir / "aderyn.json"),
                ],
                "adapter_exit_code": self.adapter_exit_code,
                "scanner_exit_code": self.scanner_exit_code,
                "duration_seconds": self.duration_seconds,
                "start_time": self.start_time,
                "end_time": self.end_time,
            },
            "artifacts": self.artifacts_evidence,
            "validation_results": self.validation_results,
            "findings_summary": self.findings_summary,
            "triaged_findings": self.triaged_findings,
            "integrity_status": "VERIFIED" if (self.validation_results["digest_verified"] and self.validation_results["schema_conformant"]) else "UNVERIFIED",
            "state_history": self.state_history,
            "terminal_status": self.terminal_status,
            "error_code": self.error_code,
        }

        if self.version_drift_sim:
            envelope["process_execution"]["tool_version"] = "9.9.9-unverified"
            envelope["version_policy_warning"] = "Scanner version 9.9.9-unverified does not match registered 0.6.8"

        envelope_path = self.output_dir / "evidence_envelope.json"
        try:
            atomic_write_json(envelope_path, envelope)
        except Exception as e:
            print(f"[WARN] Failed to write evidence envelope: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="OAM Aderyn Orchestrator")
    parser.add_argument("--slug", default="base", help="Target bounty slug under bounties/")
    parser.add_argument("--target", default="", help="Explicit target directory")
    parser.add_argument("--output-dir", default="", help="Explicit output directory")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--confirm", action="store_true", default=False)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--adapter", default="")

    # Simulation hooks for negative control tests
    parser.add_argument("--scanner-fail-sim", action="store_true", default=False)
    parser.add_argument("--fail-receipt-sim", action="store_true", default=False)
    parser.add_argument("--timeout-sim", action="store_true", default=False)
    parser.add_argument("--corrupt-report-sim", action="store_true", default=False)
    parser.add_argument("--digest-mismatch-sim", action="store_true", default=False)
    parser.add_argument("--attribution-mismatch-sim", action="store_true", default=False)
    parser.add_argument("--empty-report-sim", action="store_true", default=False)
    parser.add_argument("--version-drift-sim", action="store_true", default=False)
    parser.add_argument("--clean-sim", action="store_true", default=False)

    args = parser.parse_args()

    # Determine repo root from this file location (../../..)
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[1].resolve()

    target_dir = Path(args.target) if args.target else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    adapter_path = Path(args.adapter) if args.adapter else None

    orchestrator = OAMAderynOrchestrator(
        repo_root=repo_root,
        slug=args.slug,
        target_dir=target_dir,
        output_dir=output_dir,
        dry_run=args.dry_run,
        confirm=args.confirm,
        timeout=args.timeout,
        adapter_path=adapter_path,
        scanner_fail_sim=args.scanner_fail_sim,
        fail_receipt_sim=args.fail_receipt_sim,
        timeout_sim=args.timeout_sim,
        corrupt_report_sim=args.corrupt_report_sim,
        digest_mismatch_sim=args.digest_mismatch_sim,
        attribution_mismatch_sim=args.attribution_mismatch_sim,
        empty_report_sim=args.empty_report_sim,
        version_drift_sim=args.version_drift_sim,
        clean_sim=args.clean_sim,
    )

    exit_code = orchestrator.run_lifecycle()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
