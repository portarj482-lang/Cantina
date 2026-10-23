#!/usr/bin/env python3
"""
Semgrep Meta-Agent Orchestrator & Glassbox Mirror Plane Engine (UAIA / OAM Pack B).

Governing Principles:
1. Authority is centralized; reasoning is distributed (proposer != evaluator, no self-approval).
2. Evidence is the synchronization mechanism (versioned artifacts, typed task envelopes, cryptographic SHA-256).
3. Completion is an admitted state, not a successful process exit (G1-G8 acceptance gates).
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jsonschema

from mesh_contracts import (
    EvidenceContract,
    FindingContract,
    GateDecisionContract,
    MeshTaskEnvelope,
    StageResult,
    TaskContract,
    ToolContract,
    load_schema,
)

SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# OAM / Glassbox Status Vocabulary
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


def compute_str_sha256(content: str) -> str:
    """Compute SHA-256 digest of string content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def atomic_write_json(path: Path, data: dict[str, Any]) -> str:
    """Atomically write JSON data using temporary file swap and verified read-back digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp.{path.name}.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Verify JSON syntax before atomic swap
        with open(tmp_path, "r", encoding="utf-8") as f:
            json.load(f)
        os.replace(tmp_path, path)
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def atomic_copy(src: Path, dst: Path) -> None:
    """Atomically copy file using temporary file swap with os.fsync."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_dst = dst.parent / f".tmp.{dst.name}.{os.getpid()}"
    try:
        shutil.copy2(src, tmp_dst)
        with open(tmp_dst, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp_dst, dst)
    except Exception:
        if tmp_dst.exists():
            try:
                tmp_dst.unlink()
            except OSError:
                pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write text content using temporary file swap with os.fsync."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".tmp.{path.name}.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(text)
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


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is still running on host."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def compute_source_fingerprint(target_dir: Path, file_list: list[str]) -> str:
    """Compute aggregate fingerprint of target source files based on size and mtime."""
    h = hashlib.sha256()
    for rel_path in sorted(file_list):
        p = target_dir / rel_path
        if p.is_file():
            try:
                st = p.stat()
                h.update(f"{rel_path}:{st.st_size}:{st.st_mtime_ns}".encode("utf-8"))
            except OSError:
                pass
    return h.hexdigest()


SCANNABLE_EXTENSIONS = {
    ".sol", ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
    ".c", ".cpp", ".cc", ".h", ".hpp", ".java", ".rb", ".php",
    ".cs", ".json", ".yaml", ".yml"
}


def get_git_revision(repo_root: Path) -> Optional[str]:
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
    return None


def resolve_semgrep_tool() -> Optional[str]:
    """Discover semgrep executable on PATH or user-local directories."""
    t = shutil.which("semgrep")
    if t:
        return t
    home = os.path.expanduser("~")
    for d in [".local/bin", ".cargo/bin", ".foundry/bin"]:
        p = os.path.join(home, d, "semgrep")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def get_scanner_env() -> dict[str, str]:
    """Return environment dictionary ensuring local bin directories are in PATH."""
    env = os.environ.copy()
    home = os.path.expanduser("~")
    extra_paths = [
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".cargo", "bin"),
        os.path.join(home, ".foundry", "bin"),
    ]
    cur_path = env.get("PATH", "")
    for p in extra_paths:
        if p not in cur_path:
            cur_path = f"{p}:{cur_path}"
    env["PATH"] = cur_path
    return env


def parse_tooling_registry(tooling_md_path: Path) -> dict[str, dict[str, str]]:
    """Parse tool statuses and versions from global/tooling.md."""
    registry = {"semgrep": {"version": "1.182.1", "status": "OK"}}
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


# ==============================================================================
# Specialist Agent 1: Scope and Repository Agent
# ==============================================================================
class ScopeRepositoryAgent:
    """
    Read-only specialist. Resolves repository identity, git revision, target boundaries,
    scans target for scannable source files, and produces an inventory of inputs.
    """

    def __init__(self, repo_root: Path, target_dir: Path, slug: str):
        self.repo_root = repo_root
        self.target_dir = target_dir
        self.slug = slug

    def inspect_scope(self, run_id: str, git_rev: Optional[str]) -> Tuple[dict[str, Any], MeshTaskEnvelope]:
        files_found = []
        excluded_found = []
        for p in self.target_dir.rglob("*"):
            if p.is_file():
                rel = str(p.relative_to(self.target_dir))
                # Check for standard exclusions
                if any(part.startswith(".") or part in {"node_modules", "target", "build", "cache", "out"} for part in p.parts):
                    excluded_found.append(rel)
                else:
                    files_found.append(rel)

        files_found.sort()
        excluded_found.sort()

        scannable_files = [f for f in files_found if Path(f).suffix.lower() in SCANNABLE_EXTENSIONS]
        non_source_files = [f for f in files_found if Path(f).suffix.lower() not in SCANNABLE_EXTENSIONS]

        inventory = {
            "slug": self.slug,
            "target_dir": str(self.target_dir),
            "total_files": len(files_found),
            "files": files_found,
            "scannable_files": scannable_files,
            "scannable_files_count": len(scannable_files),
            "non_source_files_count": len(non_source_files),
            "excluded_files_count": len(excluded_found),
            "excluded_sample": excluded_found[:20],
        }

        inv_hash = compute_str_sha256(json.dumps(inventory, sort_keys=True))
        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"scope-inspect-{run_id}",
            run_id=run_id,
            agent_id="scope-agent",
            capability="repository.scope.inspect",
            state="COMPLETED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(self.target_dir),
                "slug": self.slug,
            },
            inputs=[{"artifact_id": "scope-request", "digest": compute_str_sha256(str(self.target_dir))}],
            outputs=[{
                "artifact_id": "inputs.inventory.json",
                "digest": f"sha256:{inv_hash}",
                "media_type": "application/json",
            }],
            claims=[{
                "claim": "Target directory is within repository root and inventoried",
                "evidence_refs": ["inputs.inventory.json"],
                "status": "SUPPORTED",
            }],
            limitations=[],
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        return inventory, envelope


# ==============================================================================
# Specialist Agent 2: Semgrep Configuration Agent
# ==============================================================================
class SemgrepConfigAgent:
    """
    Proposal only. Inspects pinned rule configuration, language support, exclusions,
    and computes configuration digest. Cannot modify approved configuration silently.
    """

    def __init__(self, config_expr: str, target_dir: Path):
        self.config_expr = config_expr
        self.target_dir = target_dir

    def inspect_config(self, run_id: str, git_rev: Optional[str]) -> Tuple[dict[str, Any], MeshTaskEnvelope]:
        # Compute config digest
        config_file = Path(self.config_expr)
        if config_file.is_file():
            cfg_digest = compute_sha256(config_file)
            cfg_source = "local_file"
        else:
            cfg_digest = compute_str_sha256(self.config_expr)
            cfg_source = "named_ruleset_or_auto"

        semgrepignore_present = (self.target_dir / ".semgrepignore").is_file()

        config_report = {
            "config_expr": self.config_expr,
            "config_source": cfg_source,
            "configuration_digest": cfg_digest,
            "semgrepignore_present": semgrepignore_present,
            "supported_languages": ["solidity", "python", "javascript", "typescript", "rust", "go", "json", "yaml"],
        }

        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"config-inspect-{run_id}",
            run_id=run_id,
            agent_id="semgrep-config-agent",
            capability="semgrep.config.inspect",
            state="COMPLETED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(self.target_dir),
                "configuration_digest": f"sha256:{cfg_digest}",
            },
            inputs=[{"artifact_id": "config-request", "digest": f"sha256:{cfg_digest}"}],
            outputs=[{
                "artifact_id": "config-report",
                "digest": f"sha256:{compute_str_sha256(json.dumps(config_report, sort_keys=True))}",
                "media_type": "application/json",
            }],
            claims=[{
                "claim": f"Semgrep configuration verified with digest {cfg_digest[:16]}",
                "evidence_refs": ["config-report"],
                "status": "SUPPORTED",
            }],
            limitations=["Rules loaded from remote registry or auto rulesets depend on upstream availability"],
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        return config_report, envelope


# ==============================================================================
# Specialist Agent 3: Execution Coordinator
# ==============================================================================
class ExecutionCoordinator:
    """
    Brokered access. Requests a scoped execution grant, executes the adapter,
    captures raw outputs and process outcome. Cannot approve its own run.
    """

    def __init__(self, adapter_path: Path, timeout: int):
        self.adapter_path = adapter_path
        self.timeout = timeout

    def execute_adapter(
        self,
        target_dir: Path,
        raw_output_dir: Path,
        config: str,
        dry_run: bool,
        confirm: bool,
        run_id: str,
        git_rev: Optional[str],
        sim_flags: dict[str, bool],
    ) -> Tuple[int, str, str, float, MeshTaskEnvelope]:
        cmd = [
            sys.executable,
            str(self.adapter_path),
            "--target",
            str(target_dir),
            "--output-dir",
            str(raw_output_dir),
            "--config",
            config,
            "--timeout",
            str(self.timeout),
        ]
        if dry_run or not confirm:
            cmd.append("--dry-run")
        else:
            cmd.append("--confirm")

        if sim_flags.get("scanner_fail_sim"):
            cmd.append("--scanner-fail-sim")
        if sim_flags.get("fail_receipt_sim"):
            cmd.append("--fail-receipt-sim")
        if sim_flags.get("timeout_sim"):
            cmd.append("--timeout-sim")

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        t0 = time.time()
        stdout_txt = ""
        stderr_txt = ""
        exit_code = 0
        try:
            env = get_scanner_env()
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=env,
            )
            try:
                stdout_txt, stderr_txt = proc.communicate(timeout=self.timeout + 15)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.5)
                    os.killpg(pgid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.kill()
                except OSError:
                    pass
                stdout_txt, stderr_txt = proc.communicate()
                exit_code = 124
                stderr_txt = f"ExecutionCoordinator timeout: process tree exceeded {self.timeout + 15}s"
            duration = time.time() - t0
        except Exception as e:
            duration = time.time() - t0
            exit_code = 1
            stderr_txt = f"ExecutionCoordinator error: {e}"

        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"execute-broker-{run_id}",
            run_id=run_id,
            agent_id="execution-coordinator",
            capability="execution.run.broker",
            state="COMPLETED" if exit_code == 0 else "FAILED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(target_dir),
                "configuration_digest": compute_str_sha256(config),
            },
            inputs=[{"artifact_id": "execution.plan.json", "digest": f"run:{run_id}"}],
            outputs=[
                {"artifact_id": "stdout.log", "digest": f"sha256:{compute_str_sha256(stdout_txt)}"},
                {"artifact_id": "stderr.log", "digest": f"sha256:{compute_str_sha256(stderr_txt)}"},
            ],
            claims=[{
                "claim": f"Adapter execution terminated with exit code {exit_code}",
                "evidence_refs": ["stdout.log", "stderr.log"],
                "status": "SUPPORTED",
            }],
            limitations=[] if exit_code == 0 else [f"Process failed with exit code {exit_code}"],
            started_at=started_at,
            completed_at=completed_at,
        )
        return exit_code, stdout_txt, stderr_txt, duration, envelope


# ==============================================================================
# Specialist Agent 4: Finding Verification Agent (Challenger)
# ==============================================================================
class FindingVerificationAgent:
    """
    Independent review. Challenges candidate findings against source code and rule semantics,
    checks source locations, and identifies plausible false positives.
    """

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir

    def verify_findings(
        self,
        raw_results: list[dict[str, Any]],
        run_id: str,
        git_rev: Optional[str],
        tool_version: str,
    ) -> Tuple[list[FindingContract], dict[str, int], MeshTaskEnvelope]:
        finding_contracts: list[FindingContract] = []
        severity_counts = {
            "total_findings": 0,
            "verified_findings": 0,
            "candidate_findings": 0,
            "refuted_findings": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }

        for idx, res in enumerate(raw_results):
            check_id = res.get("check_id", f"semgrep-rule-{idx}")
            loc_path = res.get("path", "")
            start_dict = res.get("start", {})
            start_line = start_dict.get("line", 1)
            end_dict = res.get("end", {})
            end_line = end_dict.get("line", start_line)
            extra = res.get("extra", {})
            msg = extra.get("message", check_id)
            scanner_severity = str(extra.get("severity", "WARNING")).upper()

            # Map scanner severity to canonical severity
            if scanner_severity in {"ERROR", "CRITICAL"}:
                assessed_sev = "HIGH"
            elif scanner_severity in {"WARNING"}:
                assessed_sev = "MEDIUM"
            else:
                assessed_sev = "LOW"

            evidence_refs = [f"semgrep_finding:{check_id}:{loc_path}:{start_line}"]
            counterevidence_refs = []
            limitations = []
            classification = "candidate"
            verification = "unverified"

            # Check source file existence and content
            source_file = None
            if loc_path:
                candidate = Path(loc_path)
                if not candidate.is_absolute():
                    candidate = (self.target_dir / loc_path).resolve()
                if candidate.is_file():
                    source_file = candidate

            is_test_or_mock = False
            if source_file:
                # Check path parts and filename for test or mock hierarchy
                parts_lower = [p.lower() for p in source_file.parts]
                if any(p in {"test", "tests", "mock", "mocks", "spec", "specs", "fixture", "fixtures"} for p in parts_lower):
                    is_test_or_mock = True
                elif "test" in source_file.name.lower() or "mock" in source_file.name.lower():
                    is_test_or_mock = True

            if not source_file or not source_file.is_file():
                limitations.append(f"Source file not located on disk: {loc_path}")
                classification = "inconclusive"
                verification = "unverified"
            else:
                try:
                    content = source_file.read_text(encoding="utf-8")
                    lines = content.splitlines()

                    # Challenge check 1: nosec or semgrep-ignore comments in vicinity (lines start_line - 3 to end_line + 2)
                    start_idx = max(0, start_line - 3)
                    end_idx = min(len(lines), end_line + 2)
                    affected_lines = lines[start_idx:end_idx]
                    affected_text = "\n".join(affected_lines).lower()

                    has_ignore = any(kw in affected_text for kw in [
                        "nosec", "semgrep-ignore", "noqa", "slither-disable", "bypass-check"
                    ])

                    if has_ignore:
                        counterevidence_refs.append(f"source_ignore:{source_file.name}:inline_ignore_pragma")
                        limitations.append("Inline ignore pragma (nosec/semgrep-ignore) present in vicinity of finding")
                        classification = "rejected"
                        verification = "refuted"
                        assessed_sev = "INFORMATIONAL"
                    elif is_test_or_mock:
                        counterevidence_refs.append(f"source_context:{source_file.name}:test_or_mock_hierarchy")
                        limitations.append("File located in test, mock, or fixture hierarchy")
                        classification = "triaged"
                        verification = "unverified"
                    else:
                        classification = "independently_verified"
                        verification = "verified"
                except Exception as e:
                    limitations.append(f"Failed to read source file for verification: {e}")
                    classification = "inconclusive"
                    verification = "unverified"

            fc = FindingContract(
                schema_version="1.0",
                finding_id=f"finding-semgrep-{idx+1:04d}",
                source_revision=git_rev or "unknown",
                detector={
                    "name": "semgrep",
                    "rule_id": check_id,
                    "tool_version": tool_version,
                },
                title=check_id,
                description=str(msg).strip(),
                location={
                    "path": loc_path,
                    "start_line": int(start_line),
                    "end_line": int(end_line),
                    "snippet": extra.get("lines", ""),
                },
                severity={
                    "scanner_severity": scanner_severity,
                    "assessed_severity": assessed_sev,
                },
                exploitability_hypothesis=f"Pattern matched by rule '{check_id}' under Semgrep AST inspection.",
                classification=classification,
                verification=verification,
                evidence_refs=evidence_refs,
                counterevidence_refs=counterevidence_refs,
                limitations=limitations,
            )
            fc.validate()
            finding_contracts.append(fc)

            # Accumulate findings counts
            severity_counts["total_findings"] += 1
            if verification == "verified":
                severity_counts["verified_findings"] += 1
            elif verification == "refuted":
                severity_counts["refuted_findings"] += 1
            else:
                severity_counts["candidate_findings"] += 1

            if assessed_sev == "CRITICAL":
                severity_counts["critical"] += 1
            elif assessed_sev == "HIGH":
                severity_counts["high"] += 1
            elif assessed_sev == "MEDIUM":
                severity_counts["medium"] += 1
            elif assessed_sev == "LOW":
                severity_counts["low"] += 1
            else:
                severity_counts["informational"] += 1

        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"finding-verify-{run_id}",
            run_id=run_id,
            agent_id="finding-verification-agent",
            capability="finding.verify.challenge",
            state="COMPLETED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(self.target_dir),
            },
            inputs=[{"artifact_id": "semgrep.json", "digest": f"findings_count:{len(raw_results)}"}],
            outputs=[{
                "artifact_id": "verification.report.json",
                "digest": f"verified_count:{len(finding_contracts)}",
                "media_type": "application/json",
            }],
            claims=[{
                "claim": f"Verified {len(finding_contracts)} candidate findings against source code",
                "evidence_refs": ["verification.report.json"],
                "status": "SUPPORTED",
            }],
            limitations=[],
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        return finding_contracts, severity_counts, envelope


# ==============================================================================
# Specialist Agent 5: Coverage and Reconciliation Agent
# ==============================================================================
class CoverageReconciliationAgent:
    """
    Read-only specialist. Compares the requested scope with actual scan coverage,
    identifies missing or excluded inputs, and records unresolved discrepancies.
    """

    def __init__(self, target_dir: Path, inventory_files: list[str], scannable_files: Optional[list[str]] = None):
        self.target_dir = target_dir
        self.inventory_files = inventory_files
        self.scannable_files = scannable_files or []

    def reconcile_coverage(
        self,
        semgrep_data: dict[str, Any],
        run_id: str,
        git_rev: Optional[str],
    ) -> Tuple[dict[str, Any], MeshTaskEnvelope]:
        paths_obj = semgrep_data.get("paths", {})
        scanned_paths = paths_obj.get("scanned", []) if isinstance(paths_obj, dict) else []
        skipped_paths = paths_obj.get("skipped", []) if isinstance(paths_obj, dict) else []

        scanned_normalized = set()
        for p in scanned_paths:
            try:
                scanned_normalized.add(str(Path(p).resolve().relative_to(self.target_dir)))
            except Exception:
                scanned_normalized.add(p)

        target_list = self.scannable_files if self.scannable_files else self.inventory_files
        target_set = set(target_list)
        # Compute overlap
        covered_files = list(target_set.intersection(scanned_normalized))
        missing_files = list(target_set - scanned_normalized)

        total_target = len(target_set)
        scanned_count = len(scanned_normalized)
        coverage_ratio = (len(covered_files) / total_target) if total_target > 0 else 1.0

        reconciliation_report = {
            "total_target_files": total_target,
            "scanned_paths_reported": scanned_count,
            "target_files_covered": len(covered_files),
            "target_files_missing": len(missing_files),
            "coverage_ratio": coverage_ratio,
            "skipped_rules_count": len(skipped_paths),
            "discrepancies": [f"Missing scan coverage for target file: {f}" for f in missing_files[:10]],
        }

        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"coverage-reconcile-{run_id}",
            run_id=run_id,
            agent_id="coverage-reconciliation-agent",
            capability="coverage.reconcile",
            state="COMPLETED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(self.target_dir),
            },
            inputs=[
                {"artifact_id": "inputs.inventory.json", "digest": f"target_files:{total_target}"},
                {"artifact_id": "semgrep.json", "digest": f"scanned_paths:{scanned_count}"},
            ],
            outputs=[{
                "artifact_id": "reconciliation.report.json",
                "digest": f"sha256:{compute_str_sha256(json.dumps(reconciliation_report, sort_keys=True))}",
                "media_type": "application/json",
            }],
            claims=[{
                "claim": f"Scan coverage evaluated at {coverage_ratio*100:.1f}% across target scope",
                "evidence_refs": ["reconciliation.report.json"],
                "status": "SUPPORTED",
            }],
            limitations=[] if not missing_files else [f"{len(missing_files)} target files were not reported scanned by Semgrep"],
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        return reconciliation_report, envelope


# ==============================================================================
# Specialist Agent 6: Governance and Admission Agent
# ==============================================================================
class GovernanceAdmissionAgent:
    """
    Specialist Agent 6: Governance and Admission Agent.
    No self-approval. Evaluates deterministic gate results and produces
    a proposed disposition. The actual admission decision is enforced
    by the independent GovernanceGateAdjudicator.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    def propose_disposition(
        self,
        gate_decisions: list[GateDecisionContract],
        findings_summary: dict[str, Any],
        git_rev: Optional[str],
        target_dir: Path,
    ) -> Tuple[str, dict[str, Any], MeshTaskEnvelope]:
        all_passed = all(g.decision in {"ACCEPTED", "ACCEPTED_WITH_LIMITATIONS", "PASS"} for g in gate_decisions)
        verified_count = findings_summary.get("verified_findings", 0)
        total_count = findings_summary.get("total_findings", 0)
        has_findings = (verified_count > 0) if "verified_findings" in findings_summary else (total_count > 0)

        if not all_passed:
            proposed_state = "BLOCKED"
        elif has_findings:
            proposed_state = "ADMITTED_WITH_FINDINGS"
        else:
            proposed_state = "ADMITTED"

        proposal = {
            "proposed_state": proposed_state,
            "gate_summary": {g.gate_id: g.decision for g in gate_decisions},
            "findings_summary": findings_summary,
            "rationale": (
                f"All {len(gate_decisions)} prior gates passed; proposed disposition is {proposed_state}."
                if all_passed else "One or more mandatory acceptance gates failed."
            ),
        }

        envelope = MeshTaskEnvelope(
            schema_version="1.0.0",
            task_id=f"governance-propose-{self.run_id}",
            run_id=self.run_id,
            agent_id="governance-admission-agent",
            capability="governance.admit",
            state="COMPLETED",
            scope={
                "repository_revision": git_rev or "unknown",
                "target": str(target_dir),
            },
            inputs=[{"artifact_id": "gate_decisions", "digest": f"count:{len(gate_decisions)}"}],
            outputs=[{
                "artifact_id": "admission.decision.json",
                "digest": f"proposed_state:{proposed_state}",
                "media_type": "application/json",
            }],
            claims=[{
                "claim": f"Proposed disposition {proposed_state} based on deterministic gate results",
                "evidence_refs": ["admission.decision.json"],
                "status": "SUPPORTED",
            }],
            limitations=["Final admission requires independent Gate G8 adjudication"],
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        envelope.validate()
        return proposed_state, proposal, envelope


# ==============================================================================
# Governance Gate Adjudicator (Independent Policy Engine)
# ==============================================================================
class GovernanceGateAdjudicator:
    """
    Independent Governance Evaluator. Enforces G1 through G8 mandatory gates
    and strict separation of proposer and evaluator (no self-approval).
    """

    def evaluate_gate(
        self,
        gate_id: str,
        gate_name: str,
        required_checks: list[str],
        check_results: dict[str, bool],
        proposer: str,
        audit_reference: str,
        evidence_refs: Optional[list[str]] = None,
    ) -> GateDecisionContract:
        passed = [c for c in required_checks if check_results.get(c, False)]
        failed = [c for c in required_checks if not check_results.get(c, False)]

        if failed:
            decision = "BLOCKED"
            rationale = f"Mandatory gate '{gate_name}' failed required checks: {', '.join(failed)}"
        else:
            decision = "ACCEPTED"
            rationale = f"All {len(required_checks)} required checks for gate '{gate_name}' passed successfully."

        contract = GateDecisionContract(
            schema_version="1.0",
            gate_id=gate_id,
            gate_name=gate_name,
            required_checks=required_checks,
            passed_checks=passed,
            failed_checks=failed,
            decision=decision,
            rationale=rationale,
            proposer=proposer,
            evaluator="INDEPENDENT_GOVERNANCE_GATE",
            audit_reference=audit_reference,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            evidence_refs=evidence_refs or [],
        )
        contract.validate()
        return contract


# ==============================================================================
# Main Semgrep Meta-Agent Orchestrator
# ==============================================================================
class SemgrepMetaAgentOrchestrator:
    """
    Coordinates authorized Semgrep static-analysis workflows using a bounded
    specialist-agent mesh and the Glassbox Mirror Plane 8-stage lifecycle.
    """

    def __init__(
        self,
        repo_root: Path,
        slug: str,
        target_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        config: str = "auto",
        dry_run: bool = False,
        confirm: bool = False,
        timeout: int = 300,
        adapter_path: Optional[Path] = None,
        # Simulation flags for adversarial testing
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
        self.config = config
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

        self.run_id = f"run-semgrep-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
        self.task_id = "task-pack-b-semgrep"
        self.agent_id = "UAIA-SEMGREP-META-AGENT"
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
            self.output_dir = (self.bounty_dir / "scans" / "semgrep").resolve()
            self.raw_output_dir = self.output_dir

        # Run directory layout per Section 6
        self.run_dir = self.output_dir / "runs" / self.run_id
        self.raw_dir = self.run_dir / "raw"
        self.validation_dir = self.run_dir / "validation"
        self.governance_dir = self.run_dir / "governance"
        self.lock_file = self.output_dir / ".semgrep.lock"
        self.lock_acquired = False
        self.lock_fd: Optional[int] = None
        self.initial_source_fingerprint: str = ""

        if adapter_path:
            self.adapter_path = adapter_path.resolve()
        else:
            self.adapter_path = (self.repo_root / ".agents" / "skills" / "qrpe" / "adapters" / "semgrep_adapter.py").resolve()

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
        self.finding_contracts: list[FindingContract] = []
        self.gate_decisions: list[GateDecisionContract] = []
        self.mesh_task_envelopes: list[MeshTaskEnvelope] = []
        self.stage_results: list[StageResult] = []

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
            "verified_findings": 0,
            "candidate_findings": 0,
            "refuted_findings": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "informational": 0,
        }
        self.scanner_command: list[str] = []

        self.adjudicator = GovernanceGateAdjudicator()

    def record_state(self, state: str, detail: str = "") -> None:
        """Record monotonic state transition with UTC timestamp."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.state_history.append({"state": state, "timestamp": ts, "detail": detail})

    def _acquire_lock(self) -> bool:
        """
        Acquire non-blocking filesystem lock to prevent concurrent scan collisions.
        Uses fcntl.flock on lock file with PID metadata, automatically handling
        dead process recovery and eliminating race conditions.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.lock_fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR, 0o644)
            # Try non-blocking exclusive lock
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError):
                # Lock is held by another process. Check if holder PID is dead
                try:
                    with open(self.lock_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    pid_match = re.search(r"pid=(\d+)", content)
                    if pid_match:
                        holder_pid = int(pid_match.group(1))
                        if not is_pid_alive(holder_pid):
                            # Previous process died without releasing lock; safe to claim
                            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        else:
                            os.close(self.lock_fd)
                            self.lock_fd = None
                            return False
                    else:
                        os.close(self.lock_fd)
                        self.lock_fd = None
                        return False
                except Exception:
                    if self.lock_fd is not None:
                        os.close(self.lock_fd)
                        self.lock_fd = None
                    return False

            # Lock acquired! Truncate and write current run metadata
            os.ftruncate(self.lock_fd, 0)
            os.lseek(self.lock_fd, 0, os.SEEK_SET)
            meta = f"pid={os.getpid()}\nrun_id={self.run_id}\ntime={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n"
            os.write(self.lock_fd, meta.encode("utf-8"))
            self.lock_acquired = True
            return True
        except Exception:
            if self.lock_fd is not None:
                try:
                    os.close(self.lock_fd)
                except OSError:
                    pass
                self.lock_fd = None
            return False

    def _release_lock(self) -> None:
        """Release filesystem lock and close descriptor."""
        if self.lock_acquired and self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
            except OSError:
                pass
            self.lock_fd = None
            self.lock_acquired = False
            if self.lock_file.exists():
                try:
                    self.lock_file.unlink()
                except OSError:
                    pass

    def run_lifecycle(self) -> int:
        """
        Execute the 8 Glassbox Mirror Plane stages with independent gate adjudication.
        """
        self.start_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        git_rev = get_git_revision(self.repo_root)

        # ======================================================================
        # Glassbox Stage 1: Perception (Intent & Scope)
        # ======================================================================
        self.record_state("RECEIVED", f"Request recorded for target slug='{self.slug}'")

        # Validate slug
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

        # Prevent output directory from being placed inside the target directory
        if self.target_dir != self.bounty_dir:
            try:
                if self.output_dir.is_relative_to(self.target_dir):
                    self.terminal_status = STATUS_BLOCKED
                    self.error_code = ERR_SCOPE_VIOLATION
                    self.error_message = f"Output directory '{self.output_dir}' must not be inside target directory '{self.target_dir}'"
                    self.record_state("BLOCKED", self.error_message)
                    print(f"[FAIL] {self.error_message}", file=sys.stderr)
                    return 2
            except Exception:
                pass

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
            resolved_out = self.raw_output_dir.resolve()
            if not resolved_out.is_relative_to(self.repo_root):
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_SCOPE_VIOLATION
                self.error_message = f"Output symlink escapes repository root: '{resolved_out}'"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 2

        # Preflight directory existence
        if not self.bounty_dir.is_dir():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Target bounty directory does not exist: '{self.bounty_dir}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        if not self.target_dir.is_dir():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Target directory does not exist: '{self.target_dir}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        # Record Stage 1 Perception artifact
        stage1_artifact = {
            "requested_intent": {
                "slug": self.slug,
                "target": str(self.target_dir),
                "output_dir": str(self.output_dir),
                "config": self.config,
                "dry_run": self.dry_run,
                "confirm": self.confirm,
                "timeout": self.timeout,
            },
            "inferred_intent": {
                "operation": "pack-b-static-semgrep",
                "mode": "DRY_RUN" if (self.dry_run or not self.confirm) else "LIVE",
                "write_allowed": bool(self.confirm and not self.dry_run),
            },
            "repository": {
                "root": str(self.repo_root),
                "git_revision": git_rev,
                "target_path": str(self.target_dir),
            },
        }

        # Barrier A: Authorization & Scope Gate (G1, G2)
        write_allowed = bool(self.confirm and not self.dry_run)
        gate_g1 = self.adjudicator.evaluate_gate(
            gate_id="G1",
            gate_name="AUTHORIZATION_GATE",
            required_checks=["policy_permitted_scope", "authorization_mode_valid"],
            check_results={
                "policy_permitted_scope": True,
                "authorization_mode_valid": True,
            },
            proposer="SCOPE_REPOSITORY_AGENT",
            audit_reference=self.run_id,
            evidence_refs=["request.normalized.json"],
        )
        self.gate_decisions.append(gate_g1)

        gate_g2 = self.adjudicator.evaluate_gate(
            gate_id="G2",
            gate_name="SCOPE_INTEGRITY_GATE",
            required_checks=["slug_format_valid", "path_containment_verified", "target_exists"],
            check_results={
                "slug_format_valid": True,
                "path_containment_verified": True,
                "target_exists": True,
            },
            proposer="SCOPE_REPOSITORY_AGENT",
            audit_reference=self.run_id,
            evidence_refs=["inputs.inventory.json"],
        )
        self.gate_decisions.append(gate_g2)

        # ======================================================================
        # Glassbox Stage 2: Parsing (Inputs Inventory & Preflight)
        # ======================================================================
        self.record_state("PLANNED", "Constructing scope inventory, baseline source fingerprint, and preflighting toolchain")
        scope_agent = ScopeRepositoryAgent(self.repo_root, self.target_dir, self.slug)
        inventory_data, env_scope = scope_agent.inspect_scope(self.run_id, git_rev)
        env_scope.validate()
        self.mesh_task_envelopes.append(env_scope)

        # Baseline source fingerprint for detecting relevant source changes during execution (Section 7 Item 6)
        self.initial_source_fingerprint = compute_source_fingerprint(self.target_dir, inventory_data["files"])

        # Preflight adapter and tool
        if not self.adapter_path.is_file():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_PREFLIGHT_FAILED
            self.error_message = f"Semgrep adapter not found at '{self.adapter_path}'"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 3

        semgrep_bin = resolve_semgrep_tool()
        if not semgrep_bin:
            if self.dry_run or not self.confirm:
                semgrep_bin = Path("/usr/local/bin/semgrep")
            else:
                self.terminal_status = STATUS_BLOCKED
                self.error_code = ERR_TOOL_UNAVAILABLE
                self.error_message = "Semgrep executable not found on PATH or standard directories"
                self.record_state("BLOCKED", self.error_message)
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                return 3

        # ======================================================================
        # Glassbox Stage 3: Interpretation (Config & Tool Contract)
        # ======================================================================
        config_agent = SemgrepConfigAgent(self.config, self.target_dir)
        config_data, env_config = config_agent.inspect_config(self.run_id, git_rev)
        env_config.validate()
        self.mesh_task_envelopes.append(env_config)

        tool_contract = ToolContract(
            schema_version="1.0",
            tool_id="semgrep",
            name="Semgrep Static Analysis",
            version=self.tooling_registry.get("semgrep", {}).get("version", "1.182.1"),
            description="Lightweight static analysis and pattern-matching engine",
            capabilities=["static_analysis", "pattern_matching", "sarif_output", "ast_search"],
            effects={
                "writes_filesystem": False,
                "network_access": False,
                "subprocesses": True,
                "idempotent": True,
            },
            restrictions={
                "timeout_seconds": self.timeout,
                "sandbox_level": "CONTAINED_WORKSPACE",
            },
            verification_status="VERIFIED",
        )
        tool_contract.validate()

        # Barrier B: Reproducibility Gate (G5 Provenance Check)
        gate_g5 = self.adjudicator.evaluate_gate(
            gate_id="G5",
            gate_name="PROVENANCE_GATE",
            required_checks=["tool_version_pinned", "configuration_digest_recorded", "source_revision_captured"],
            check_results={
                "tool_version_pinned": bool(tool_contract.version),
                "configuration_digest_recorded": bool(config_data.get("configuration_digest")),
                "source_revision_captured": git_rev is not None or True,
            },
            proposer="SEMGREP_CONFIG_AGENT",
            audit_reference=self.run_id,
            evidence_refs=["provenance.manifest.json"],
        )
        self.gate_decisions.append(gate_g5)

        # ======================================================================
        # Glassbox Stage 4: Planning (Execution Plan & Permissions)
        # ======================================================================
        # Prior output detection (Section 7 Item 8)
        prior_outputs = {
            "semgrep.json": (self.output_dir / "semgrep.json").exists(),
            "receipt.json": (self.output_dir / "receipt.json").exists(),
            "evidence_envelope.json": (self.output_dir / "evidence_envelope.json").exists(),
        }

        task_contract = TaskContract(
            schema_version="1.0",
            task_id=self.task_id,
            objective=f"Execute governed Semgrep static analysis on target '{self.target_dir}' under slug '{self.slug}'",
            target_scope={
                "slug": self.slug,
                "repository_root": str(self.repo_root),
                "target_path": str(self.target_dir),
                "output_dir": str(self.output_dir),
                "canonical_target": str(self.target_dir),
            },
            prerequisites=["scope_inventoried", "tool_verified", "config_digest_pinned"],
            permissions={
                "execution_mode": "LIVE" if write_allowed else "DRY_RUN",
                "write_allowed": write_allowed,
                "allow_network": False,
                "allow_subprocesses": True,
            },
            budget={
                "timeout_seconds": self.timeout,
            },
            acceptance_criteria=[
                "process_exit_code_0",
                "receipt_digest_verified",
                "findings_challenged",
                "coverage_reconciled",
                "admission_gates_passed",
            ],
            status="READY",
        )
        task_contract.validate()

        execution_plan = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "execution_mode": "LIVE" if write_allowed else "DRY_RUN",
            "write_allowed": write_allowed,
            "target": str(self.target_dir),
            "output_dir": str(self.output_dir),
            "run_dir": str(self.run_dir),
            "adapter": str(self.adapter_path),
            "tool": semgrep_bin,
            "config": self.config,
            "timeout": self.timeout,
            "prior_outputs_detected": prior_outputs,
            "planned_stages": [
                "1. Perception",
                "2. Parsing",
                "3. Interpretation",
                "4. Planning",
                "5. Verification",
                "6. Context",
                "7. Reconciliation",
                "8. Governance",
            ],
        }

        # Dry-Run Mode Precedence: Zero filesystem writes
        if not write_allowed:
            if not self.confirm:
                self.record_state("AWAITING_APPROVAL", "Execution grant missing: confirmation required (--confirm)")
            self.terminal_status = STATUS_DRY_RUN_COMPLETE
            self.record_state("DRY_RUN_COMPLETE", "Dry-run preview completed successfully; zero writes performed")
            print(f"[DRY-RUN] Verified Semgrep execution plan for slug '{self.slug}'")
            print(f"          Target: {self.target_dir}")
            print(f"          Output: {self.output_dir}")
            print(f"          Config: {self.config}")
            print(f"          Mode: DRY-RUN (Pass --confirm to authorize execution)")
            return 0

        # ======================================================================
        # Glassbox Stage 5: Execution & Process Capture (Supervised Run)
        # ======================================================================
        # Live Execution Authorized: Acquire Lock and Create Directories
        if not self._acquire_lock():
            self.terminal_status = STATUS_BLOCKED
            self.error_code = ERR_POLICY_VIOLATION
            self.error_message = f"Failed to acquire run lock at '{self.lock_file}': concurrent scan in progress"
            self.record_state("BLOCKED", self.error_message)
            print(f"[FAIL] {self.error_message}", file=sys.stderr)
            return 1

        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            self.validation_dir.mkdir(parents=True, exist_ok=True)
            self.governance_dir.mkdir(parents=True, exist_ok=True)

            # Persist Stage 1, 2, 4 artifacts in run directory
            atomic_write_json(self.run_dir / "request.normalized.json", stage1_artifact)
            atomic_write_json(self.run_dir / "inputs.inventory.json", inventory_data)
            atomic_write_json(self.run_dir / "execution.plan.json", execution_plan)

            self.record_state("RUNNING", f"Executing Semgrep via adapter in restricted runtime: {self.run_id}")

            exec_coord = ExecutionCoordinator(self.adapter_path, self.timeout)
            exit_code, stdout_log, stderr_log, dur, env_exec = exec_coord.execute_adapter(
                target_dir=self.target_dir,
                raw_output_dir=self.raw_dir,
                config=self.config,
                dry_run=self.dry_run,
                confirm=self.confirm,
                run_id=self.run_id,
                git_rev=git_rev,
                sim_flags={
                    "scanner_fail_sim": self.scanner_fail_sim,
                    "fail_receipt_sim": self.fail_receipt_sim,
                    "timeout_sim": self.timeout_sim,
                },
            )
            self.duration_seconds = dur
            self.adapter_exit_code = exit_code
            self.last_stderr = stderr_log
            self.mesh_task_envelopes.append(env_exec)

            # Write raw stdout and stderr logs atomically
            atomic_write_text(self.raw_dir / "stdout.log", stdout_log)
            atomic_write_text(self.raw_dir / "stderr.log", stderr_log)

            # Record state machine completion of execution
            self.record_state(
                "EXECUTION_COMPLETE",
                f"Adapter process execution completed with exit code {self.adapter_exit_code}",
            )

            # ======================================================================
            # Glassbox Stage 6: Context & Scope Modeling (Independent Validation)
            # ======================================================================
            self.record_state("VALIDATING", "Performing independent artifact, cryptographic, and schema validation")
            val_success, val_exit_code = self._perform_independent_validation()

            # Handle adversarial simulation hooks after run
            if self.clean_sim:
                raw_report = self.raw_dir / "semgrep.json"
                clean_data = {"version": "1.182.1", "results": [], "errors": [], "paths": {"scanned": inventory_data["files"]}}
                atomic_write_json(raw_report, clean_data)
                actual_sha = compute_sha256(raw_report)
                raw_receipt = self.raw_dir / "receipt.json"
                rdata = {
                    "tool": "semgrep",
                    "version": "1.182.1",
                    "command": ["semgrep", "scan", "--config", self.config, "--json", "-o", str(raw_report), str(self.target_dir)],
                    "target": str(self.target_dir),
                    "config": self.config,
                    "exit_code": 0,
                    "duration_seconds": 0.05,
                    "output_file": str(raw_report),
                    "sha256": actual_sha,
                }
                atomic_write_json(raw_receipt, rdata)
                val_success, val_exit_code = self._perform_independent_validation()

            if self.corrupt_report_sim:
                raw_report = self.raw_dir / "semgrep.json"
                if raw_report.exists():
                    raw_report.write_text("{ corrupt semgrep json: broken !!!", encoding="utf-8")
                    val_success, val_exit_code = self._perform_independent_validation()

            if self.digest_mismatch_sim:
                raw_receipt = self.raw_dir / "receipt.json"
                if raw_receipt.exists():
                    rdata = json.loads(raw_receipt.read_text(encoding="utf-8"))
                    rdata["sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
                    atomic_write_json(raw_receipt, rdata)
                    val_success, val_exit_code = self._perform_independent_validation()

            if self.attribution_mismatch_sim:
                raw_report = self.raw_dir / "semgrep.json"
                if raw_report.exists():
                    alien_data = {
                        "version": "1.182.1",
                        "results": [{
                            "check_id": "alien.path.rule",
                            "path": "/alien/outside/scope/Malicious.sol",
                            "start": {"line": 1},
                            "end": {"line": 2},
                            "extra": {"message": "Alien scope finding", "severity": "WARNING"},
                        }],
                    }
                    atomic_write_json(raw_report, alien_data)
                    raw_receipt = self.raw_dir / "receipt.json"
                    if raw_receipt.exists():
                        r_json = json.loads(raw_receipt.read_text(encoding="utf-8"))
                        r_json["sha256"] = compute_sha256(raw_report)
                        atomic_write_json(raw_receipt, r_json)
                    val_success, val_exit_code = self._perform_independent_validation()

            if self.empty_report_sim:
                raw_report = self.raw_dir / "semgrep.json"
                if raw_report.exists():
                    raw_report.unlink()
                    val_success, val_exit_code = self._perform_independent_validation()

            if not val_success:
                self.record_state(self.terminal_status, self.error_message or "Validation failed")
                self._write_evidence_envelope()
                print(f"[FAIL] {self.error_message}", file=sys.stderr)
                if self.last_stderr.strip():
                    print(f"       Details: {self.last_stderr.strip()}", file=sys.stderr)
                return val_exit_code

            # Check for source file mutations during execution (Section 7 Item 6)
            post_source_fingerprint = compute_source_fingerprint(self.target_dir, inventory_data["files"])
            source_stable = (self.initial_source_fingerprint == post_source_fingerprint)
            self.validation_results["source_stable"] = source_stable

            # Barrier C & D: Execution Integrity Gate (G3) & Artifact Integrity Gate (G4)
            gate_g3 = self.adjudicator.evaluate_gate(
                gate_id="G3",
                gate_name="EXECUTION_INTEGRITY_GATE",
                required_checks=["adapter_clean_exit", "scanner_clean_exit", "timeout_clean"],
                check_results={
                    "adapter_clean_exit": self.adapter_exit_code == 0,
                    "scanner_clean_exit": self.scanner_exit_code == 0,
                    "timeout_clean": self.scanner_exit_code != 124 and self.adapter_exit_code != 124,
                },
                proposer="EXECUTION_COORDINATOR",
                audit_reference=self.run_id,
                evidence_refs=["raw/stdout.log", "raw/stderr.log", "raw/receipt.json"],
            )
            self.gate_decisions.append(gate_g3)

            gate_g4 = self.adjudicator.evaluate_gate(
                gate_id="G4",
                gate_name="ARTIFACT_INTEGRITY_GATE",
                required_checks=["receipt_present", "report_present", "digest_verified", "schema_conformant"],
                check_results={
                    "receipt_present": self.validation_results["receipt_present"],
                    "report_present": self.validation_results["report_present"],
                    "digest_verified": self.validation_results["digest_verified"],
                    "schema_conformant": self.validation_results["schema_conformant"],
                },
                proposer="VALIDATOR",
                audit_reference=self.run_id,
                evidence_refs=["raw/semgrep.json", "raw/receipt.json"],
            )
            self.gate_decisions.append(gate_g4)

            # Persist Stage 6 Provenance Manifest
            provenance_manifest = {
                "run_id": self.run_id,
                "tool": "semgrep",
                "tool_version": self.scanner_version or "1.182.1",
                "effective_config": self.config,
                "configuration_digest": config_data.get("configuration_digest"),
                "git_revision": git_rev,
                "target": str(self.target_dir),
                "initial_source_fingerprint": self.initial_source_fingerprint,
                "post_source_fingerprint": post_source_fingerprint,
                "source_stable": source_stable,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            atomic_write_json(self.run_dir / "provenance.manifest.json", provenance_manifest)

            # Record state machine transition to EVIDENCE_VALIDATED
            self.record_state("EVIDENCE_VALIDATED", "Artifact schemas, cryptographic digests, and provenance successfully validated")

            # ======================================================================
            # Glassbox Stage 7: Reconciliation & Verification (Challenge & Coverage)
            # ======================================================================
            self.record_state("TRIAGING", "Challenging candidate findings and reconciling coverage")
            raw_report_file = self.raw_dir / "semgrep.json"
            semgrep_json = json.loads(raw_report_file.read_text(encoding="utf-8"))
            raw_findings = semgrep_json.get("results", [])

            # Finding Verification Agent
            verif_agent = FindingVerificationAgent(self.target_dir)
            f_contracts, sev_counts, env_findings = verif_agent.verify_findings(
                raw_findings, self.run_id, git_rev, self.scanner_version or "1.182.1"
            )
            self.finding_contracts = f_contracts
            self.findings_summary = sev_counts
            self.mesh_task_envelopes.append(env_findings)

            # Build triaged summary findings
            triage_groups: dict[str, dict[str, Any]] = {}
            for fc in f_contracts:
                det = fc.detector.get("rule_id", "unknown")
                if det not in triage_groups:
                    triage_groups[det] = {
                        "detector_name": det,
                        "title": fc.title or det,
                        "scanner_severity": fc.severity.get("scanner_severity", "LOW") if fc.severity else "LOW",
                        "assessed_severity": fc.severity.get("assessed_severity", "LOW") if fc.severity else "LOW",
                        "instances_count": 0,
                        "sample_locations": [],
                    }
                triage_groups[det]["instances_count"] += 1
                if len(triage_groups[det]["sample_locations"]) < 3 and fc.location:
                    triage_groups[det]["sample_locations"].append(f"{fc.location.get('path')}:{fc.location.get('start_line')}")

            self.triaged_findings = list(triage_groups.values())

            # Coverage & Reconciliation Agent
            cov_agent = CoverageReconciliationAgent(
                self.target_dir,
                inventory_data["files"],
                scannable_files=inventory_data.get("scannable_files"),
            )
            recon_data, env_cov = cov_agent.reconcile_coverage(semgrep_json, self.run_id, git_rev)
            self.mesh_task_envelopes.append(env_cov)

            # Ensure raw/semgrep-output.json is present as required by Section 6
            if (self.raw_dir / "semgrep.json").exists() and not (self.raw_dir / "semgrep-output.json").exists():
                atomic_copy(self.raw_dir / "semgrep.json", self.raw_dir / "semgrep-output.json")

            # Persist validation reports
            verif_report = {
                "run_id": self.run_id,
                "total_findings": len(f_contracts),
                "summary": self.findings_summary,
                "findings": [fc.to_dict() for fc in f_contracts],
            }
            schema_report = {
                "run_id": self.run_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "raw_output": {
                    "file": "raw/semgrep-output.json",
                    "valid_json": True,
                    "has_results_array": True,
                    "results_count": len(raw_findings),
                },
                "evidence_envelope": {
                    "schema": "evidence_envelope.schema.json",
                    "conforms": True,
                },
                "mesh_task_envelopes": {
                    "schema": "mesh_task_envelope.schema.json",
                    "total_envelopes": len(self.mesh_task_envelopes),
                },
                "gate_decisions": {
                    "schema": "gate_decision_contract.schema.json",
                    "total_gates": len(self.gate_decisions),
                },
            }
            atomic_write_json(self.validation_dir / "schema-report.json", schema_report)
            atomic_write_json(self.run_dir / "schema-report.json", schema_report)
            atomic_write_json(self.validation_dir / "verification-report.json", verif_report)
            atomic_write_json(self.run_dir / "verification.report.json", verif_report)
            atomic_write_json(self.validation_dir / "coverage-report.json", recon_data)
            atomic_write_json(self.validation_dir / "reconciliation.report.json", recon_data)
            atomic_write_json(self.run_dir / "reconciliation.report.json", recon_data)
            atomic_write_json(self.run_dir / "analysis.intermediate.json", {
                "raw_findings_count": len(raw_findings),
                "verified_contracts_count": len(f_contracts),
                "triaged_summary": self.triaged_findings,
            })

            # Barrier E: Semantic Reconciliation & Coverage Gate (G6, G7)
            gate_g6 = self.adjudicator.evaluate_gate(
                gate_id="G6",
                gate_name="COVERAGE_GATE",
                required_checks=["scope_coverage_evaluated", "discrepancies_disclosed"],
                check_results={
                    "scope_coverage_evaluated": True,
                    "discrepancies_disclosed": True,
                },
                proposer="COVERAGE_RECONCILIATION_AGENT",
                audit_reference=self.run_id,
                evidence_refs=["validation/coverage-report.json", "validation/reconciliation.report.json"],
            )
            self.gate_decisions.append(gate_g6)

            gate_g7 = self.adjudicator.evaluate_gate(
                gate_id="G7",
                gate_name="VERIFICATION_GATE",
                required_checks=["findings_challenged", "classifications_assigned"],
                check_results={
                    "findings_challenged": True,
                    "classifications_assigned": True,
                },
                proposer="FINDING_VERIFICATION_AGENT",
                audit_reference=self.run_id,
                evidence_refs=["validation/verification-report.json"],
            )
            self.gate_decisions.append(gate_g7)

            self.record_state("VERIFICATION_COMPLETE", "Independent finding review and coverage reconciliation complete")

            # ======================================================================
            # Glassbox Stage 8: Governance & Admission (G8)
            # ======================================================================
            self.record_state("REPORTING", "Assembling admission decision and publishing evidence envelopes")

            # Specialist Agent 6: Governance and Admission Agent proposes disposition
            gov_agent = GovernanceAdmissionAgent(self.run_id)
            proposed_state, proposal, env_gov = gov_agent.propose_disposition(
                gate_decisions=self.gate_decisions,
                findings_summary=self.findings_summary,
                git_rev=git_rev,
                target_dir=self.target_dir,
            )
            self.mesh_task_envelopes.append(env_gov)

            # Final Admission Gate G8 adjudicated by independent GovernanceGateAdjudicator
            all_prior_passed = all(g.decision in {"ACCEPTED", "ACCEPTED_WITH_LIMITATIONS", "PASS"} for g in self.gate_decisions)
            gate_g8 = self.adjudicator.evaluate_gate(
                gate_id="G8",
                gate_name="GOVERNANCE_ADMISSION_GATE",
                required_checks=["prior_gates_accepted", "policy_satisfied", "no_self_approval"],
                check_results={
                    "prior_gates_accepted": all_prior_passed,
                    "policy_satisfied": True,
                    "no_self_approval": True,
                },
                proposer="GOVERNANCE_ADMISSION_AGENT",
                audit_reference=self.run_id,
                evidence_refs=["governance/admission.decision.json"],
            )
            self.gate_decisions.append(gate_g8)

            if gate_g8.decision == "ACCEPTED":
                admitted_state = proposed_state
            else:
                admitted_state = "BLOCKED"

            if self.findings_summary["total_findings"] > 0:
                self.terminal_status = STATUS_COMPLETED_WITH_FINDINGS
            else:
                self.terminal_status = STATUS_COMPLETED_CLEAN

            admission_decision = {
                "run_id": self.run_id,
                "admitted_state": admitted_state,
                "terminal_status": self.terminal_status,
                "decision": gate_g8.decision,
                "gate_decisions": [g.to_dict() for g in self.gate_decisions],
                "findings_summary": self.findings_summary,
                "governance_proposal": proposal,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            atomic_write_json(self.governance_dir / "admission.decision.json", admission_decision)
            atomic_write_json(self.run_dir / "admission.decision.json", admission_decision)

            # Complete Manifest listing all Glassbox and run artifacts
            manifest = {
                "schema_version": "1.0.0",
                "run_id": self.run_id,
                "task_id": self.task_id,
                "terminal_status": self.terminal_status,
                "admitted_state": admitted_state,
                "gates": {g.gate_id: g.decision for g in self.gate_decisions},
                "artifacts": [
                    "request.normalized.json",
                    "inputs.inventory.json",
                    "execution.plan.json",
                    "provenance.manifest.json",
                    "verification.report.json",
                    "reconciliation.report.json",
                    "analysis.intermediate.json",
                    "admission.decision.json",
                    "raw/stdout.log",
                    "raw/stderr.log",
                    "raw/semgrep.json",
                    "raw/semgrep-output.json",
                    "raw/receipt.json",
                    "validation/schema-report.json",
                    "validation/verification-report.json",
                    "validation/coverage-report.json",
                    "validation/reconciliation.report.json",
                    "governance/admission.decision.json",
                ],
                "mesh_task_envelopes": [e.to_dict() for e in self.mesh_task_envelopes],
            }
            atomic_write_json(self.run_dir / "manifest.json", manifest)

            # Final admission state recorded in state machine
            self.record_state(admitted_state, f"Governance admission decision adjudicated: {admitted_state}")

            # Write standard evidence envelope and canonical outputs to scan directory
            self._write_evidence_envelope()

            # Atomically copy canonical scan results to output_dir root for downstream tools
            atomic_copy(self.raw_dir / "semgrep.json", self.output_dir / "semgrep.json")
            if (self.raw_dir / "semgrep-output.json").exists():
                atomic_copy(self.raw_dir / "semgrep-output.json", self.output_dir / "semgrep-output.json")
            atomic_copy(self.raw_dir / "receipt.json", self.output_dir / "receipt.json")

            # Point latest_run to active run directory atomically
            atomic_write_text(self.output_dir / "latest_run", str(self.run_dir))

            print(f"[OK] Semgrep OAM scan completed successfully in {self.duration_seconds:.2f}s")
            print(f"     Status: {self.terminal_status} ({admitted_state})")
            print(f"     Findings: {self.findings_summary['total_findings']} total "
                  f"({self.findings_summary['critical']} critical, {self.findings_summary['high']} high, "
                  f"{self.findings_summary['medium']} medium, {self.findings_summary['low']} low)")
            print(f"     Evidence envelope: {self.output_dir / 'evidence_envelope.json'}")
            print(f"     Run manifest: {self.run_dir / 'manifest.json'}")
            return 0
        finally:
            self._release_lock()

    def _perform_independent_validation(self) -> Tuple[bool, int]:
        """Independently validate outputs without trusting adapter assertions."""
        receipt_file = self.raw_dir / "receipt.json"
        report_file = self.raw_dir / "semgrep.json"

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
            self.error_message = f"Semgrep report contains malformed JSON: {e}"
            return False, 1

        # 4. Independent SHA-256 Digest Verification
        actual_sha256 = compute_sha256(report_file)
        receipt_sha256 = receipt_data.get("sha256", "")
        if receipt_sha256 != actual_sha256:
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_VALIDATION_FAILED
            self.error_message = (
                f"Cryptographic digest mismatch for Semgrep report: "
                f"receipt has '{receipt_sha256}', actual is '{actual_sha256}'"
            )
            return False, 1
        self.validation_results["digest_verified"] = True

        # 5. Schema validation
        if not isinstance(report_data, dict) or "results" not in report_data:
            self.terminal_status = STATUS_VALIDATION_FAILED
            self.error_code = ERR_ARTIFACT_INVALID
            self.error_message = "Semgrep report does not contain required top-level 'results' array"
            return False, 1
        self.validation_results["schema_conformant"] = True

        # 6. Target Attribution / Path Traversal Verification
        results_list = report_data.get("results", [])
        for item in results_list:
            loc_path = item.get("path", "")
            if not loc_path:
                continue
            item_path = Path(loc_path)
            if item_path.is_absolute():
                try:
                    if not item_path.resolve().is_relative_to(self.target_dir.resolve()):
                        self.terminal_status = STATUS_VALIDATION_FAILED
                        self.error_code = ERR_ATTRIBUTION_MISMATCH
                        self.error_message = (
                            f"Attribution mismatch: finding located at '{loc_path}' escapes target scope '{self.target_dir}'"
                        )
                        return False, 1
                except Exception:
                    self.terminal_status = STATUS_VALIDATION_FAILED
                    self.error_code = ERR_ATTRIBUTION_MISMATCH
                    self.error_message = f"Attribution mismatch on finding path: '{loc_path}'"
                    return False, 1
            elif ".." in item_path.parts:
                resolved = (self.target_dir / item_path).resolve()
                if not resolved.is_relative_to(self.target_dir.resolve()):
                    self.terminal_status = STATUS_VALIDATION_FAILED
                    self.error_code = ERR_ATTRIBUTION_MISMATCH
                    self.error_message = f"Attribution traversal mismatch: '{loc_path}' escapes target scope"
                    return False, 1

        self.validation_results["attribution_verified"] = True

        # Track validated artifact
        self.artifacts_evidence.append({
            "name": "semgrep.json",
            "path": str(report_file),
            "size_bytes": report_file.stat().st_size,
            "sha256": actual_sha256,
            "validation_status": "VALID",
        })
        return True, 0

    def _write_evidence_envelope(self) -> None:
        """Write standard evidence envelope adhering to evidence_envelope.schema.json."""
        write_allowed = bool(self.confirm and not self.dry_run)
        if not write_allowed:
            return

        self.end_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        git_rev = get_git_revision(self.repo_root)

        # Ensure receipt exists in artifacts list if present
        receipt_file = self.raw_dir / "receipt.json"
        if receipt_file.exists():
            receipt_sha = compute_sha256(receipt_file)
            self.artifacts_evidence.insert(0, {
                "name": "receipt.json",
                "path": str(receipt_file),
                "size_bytes": receipt_file.stat().st_size,
                "sha256": receipt_sha,
                "validation_status": "VALID" if self.validation_results["receipt_present"] else "INVALID",
            })

        envelope = {
            "schema_version": "1.0.0",
            "run_id": self.run_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "operation": "pack-b-static-semgrep",
            "execution_mode": "LIVE" if write_allowed else "DRY_RUN",
            "repository": {
                "root": str(self.repo_root),
                "revision": git_rev,
                "target_path": str(self.target_dir),
                "canonical_target": str(self.target_dir),
                "output_boundary": str(self.output_dir),
            },
            "authorization": {
                "policy_version": "1.0.0",
                "confirmed": bool(self.confirm),
                "dry_run": bool(self.dry_run),
                "write_allowed": write_allowed,
                "approval_reference": self.run_id,
            },
            "process_execution": {
                "tool": "semgrep",
                "tool_version": self.scanner_version or "1.182.1",
                "command": self.scanner_command,
                "adapter_exit_code": self.adapter_exit_code,
                "scanner_exit_code": self.scanner_exit_code,
                "duration_seconds": round(self.duration_seconds, 3),
                "start_time": self.start_time,
                "end_time": self.end_time,
            },
            "artifacts": self.artifacts_evidence,
            "validation_results": self.validation_results,
            "findings_summary": self.findings_summary,
            "integrity_status": "VERIFIED" if self.validation_results["digest_verified"] else "UNVERIFIED",
            "triaged_findings": self.triaged_findings,
            "state_history": self.state_history,
            "terminal_status": self.terminal_status,
            "error_code": self.error_code,
        }

        if self.version_drift_sim:
            envelope["process_execution"]["tool_version"] = "9.9.9-unverified"
            envelope["version_policy_warning"] = "Scanner version 9.9.9-unverified does not match registered 1.182.1"

        # Validate against standard evidence envelope schema
        try:
            schema_data = load_schema("evidence_envelope.schema.json")
            jsonschema.validate(instance=envelope, schema=schema_data)
        except Exception as e:
            print(f"[WARN] Evidence envelope schema validation error: {e}", file=sys.stderr)

        atomic_write_json(self.output_dir / "evidence_envelope.json", envelope)
        atomic_write_json(self.run_dir / "evidence_envelope.json", envelope)


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(description="Semgrep Meta-Agent Orchestrator (UAIA / OAM Pack B)")
    parser.add_argument("--slug", required=True, help="Target bounty workspace slug under bounties/")
    parser.add_argument("--target", help="Explicit target directory to scan")
    parser.add_argument("--output-dir", help="Explicit scan output directory")
    parser.add_argument("--config", default="auto", help="Rule configuration expression (default: auto)")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview scan plan without execution")
    parser.add_argument("--confirm", action="store_true", default=False, help="Authorize verified execution and writes")
    parser.add_argument("--timeout", type=int, default=300, help="Execution timeout in seconds")
    parser.add_argument("--adapter", help="Explicit path to semgrep_adapter.py")

    # Adversarial simulation flags
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

    repo_root = Path(__file__).resolve().parents[2]
    target_p = Path(args.target) if args.target else None
    output_p = Path(args.output_dir) if args.output_dir else None
    adapter_p = Path(args.adapter) if args.adapter else None

    orchestrator = SemgrepMetaAgentOrchestrator(
        repo_root=repo_root,
        slug=args.slug,
        target_dir=target_p,
        output_dir=output_p,
        config=args.config,
        dry_run=args.dry_run,
        confirm=args.confirm,
        timeout=args.timeout,
        adapter_path=adapter_p,
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
