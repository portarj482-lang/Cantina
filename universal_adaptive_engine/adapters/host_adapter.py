"""Host Environment Adapter implementing ArchitectureAdapter for POSIX/Linux systems."""
from __future__ import annotations
import os
import platform
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from universal_adaptive_engine.adapters.protocol import (
    BaseArchitectureAdapter,
    AdapterResult,
)
from universal_adaptive_engine.models.enums import CapabilityStatus, EvidenceType, ConfidenceLevel
from universal_adaptive_engine.models.evidence import EvidenceRecord


class HostEnvironmentAdapter(BaseArchitectureAdapter):
    """Adapter that discovers and interacts with the host Linux / POSIX runtime."""

    def __init__(self, workspace_root: Path | str = "/home/nova/projects/cantina"):
        super().__init__(name="host-environment-adapter", version="1.0.0")
        self.workspace_root = Path(workspace_root).resolve()

    def discover(self) -> dict[str, Any]:
        """Discover actual host environment components and capabilities."""
        binaries_to_check = [
            "python3", "git", "bash", "grep", "find", "curl", "anvil", "forge",
            "solc", "node", "tsc", "cargo", "docker"
        ]
        discovered_tools = {}
        for b in binaries_to_check:
            loc = shutil.which(b)
            discovered_tools[b] = {
                "available": loc is not None,
                "path": loc,
            }

        git_status = "not_a_repo"
        git_commit = None
        if (self.workspace_root / ".git").exists():
            git_status = "git_repository"
            try:
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    git_commit = res.stdout.strip()
            except Exception:
                pass

        capabilities = {
            "filesystem.read": {
                "status": CapabilityStatus.VERIFIED.value,
                "path": str(self.workspace_root),
            },
            "filesystem.write": {
                "status": CapabilityStatus.VERIFIED.value if os.access(self.workspace_root, os.W_OK) else CapabilityStatus.BLOCKED.value,
                "path": str(self.workspace_root),
            },
            "python.runtime": {
                "status": CapabilityStatus.VERIFIED.value,
                "version": sys.version.split()[0],
                "executable": sys.executable,
            },
            "git.tracking": {
                "status": CapabilityStatus.VERIFIED.value if git_commit else CapabilityStatus.PARTIAL.value,
                "head_commit": git_commit,
            },
        }

        evidence = [
            EvidenceRecord(
                evidence_id="EVID-HOST-DISCOVERY",
                evidence_type=EvidenceType.OBSERVED,
                source_ref=f"host:{platform.node()}",
                acquisition_method="host_system_introspection",
                observed_result=f"Host OS: {platform.system()} {platform.release()}, Python: {sys.version.split()[0]}, Tools: {[k for k, v in discovered_tools.items() if v['available']]}",
                confidence=ConfidenceLevel.VERIFIED,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).to_dict()
        ]

        return {
            "adapter": self.name,
            "version": self.version,
            "workspace_root": str(self.workspace_root),
            "os": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "tools": discovered_tools,
            "git": {
                "status": git_status,
                "commit": git_commit,
            },
            "capabilities": capabilities,
            "evidence": evidence,
        }

    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Validate a canonical task or contract against host constraints."""
        issues = []
        task_id = contract.get("task_id", "unknown")
        permissions = contract.get("permissions_required", [])

        # Check permissions
        for perm in permissions:
            if perm == "network.outbound":
                issues.append("Outbound network access is restricted by policy guardrails.")
            elif perm == "filesystem.write_outside_workspace":
                issues.append("Writing outside workspace boundary is forbidden.")

        # Check path safety if inputs refer to paths
        for inp in contract.get("inputs", []):
            if isinstance(inp, str) and ("../" in inp or inp.startswith("/etc")):
                issues.append(f"Suspicious path detected in inputs: {inp}")

        return {
            "valid": len(issues) == 0,
            "task_id": task_id,
            "issues": issues,
            "recommendation": "PROCEED" if len(issues) == 0 else "REJECT_OR_ADAPT",
        }

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute authorized work and return structured evidence."""
        task_id = task.get("task_id", "unknown")
        action = task.get("action", "inspect")
        inputs = task.get("inputs", [])

        if action == "inspect_path":
            rel_path = inputs[0] if inputs else "."
            try:
                target = (self.workspace_root / rel_path).resolve()
            except Exception as e:
                return AdapterResult(
                    success=False,
                    status="INVALID_PATH",
                    errors=[str(e)],
                ).to_dict()

            if not target.is_relative_to(self.workspace_root):
                return AdapterResult(
                    success=False,
                    status="PERMISSION_DENIED",
                    errors=[f"Target path {rel_path} escapes workspace root {self.workspace_root}"],
                ).to_dict()

            exists = target.exists()
            is_dir = target.is_dir() if exists else False
            is_file = target.is_file() if exists else False
            size = target.stat().st_size if exists and is_file else 0

            evidence = [
                EvidenceRecord(
                    evidence_id=f"EVID-EXEC-{task_id}",
                    evidence_type=EvidenceType.OBSERVED,
                    source_ref=str(target),
                    acquisition_method="filesystem_stat",
                    observed_result=f"Path {rel_path}: exists={exists}, is_file={is_file}, is_dir={is_dir}, size_bytes={size}",
                    confidence=ConfidenceLevel.VERIFIED,
                ).to_dict()
            ]

            return AdapterResult(
                success=True,
                status="COMPLETED",
                output={"path": str(target), "exists": exists, "is_file": is_file, "is_dir": is_dir, "size_bytes": size},
                evidence=evidence,
            ).to_dict()

        elif action == "run_command":
            if isinstance(inputs, str):
                cmd = shlex.split(inputs)
            elif isinstance(inputs, list):
                if len(inputs) == 1 and isinstance(inputs[0], str) and " " in inputs[0]:
                    cmd = shlex.split(inputs[0])
                else:
                    cmd = [str(c) for c in inputs]
            else:
                cmd = [str(inputs)]
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                evidence = [
                    EvidenceRecord(
                        evidence_id=f"EVID-EXEC-{task_id}",
                        evidence_type=EvidenceType.OBSERVED,
                        source_ref=f"cmd:{' '.join(str(c) for c in cmd)}",
                        acquisition_method="subprocess_execution",
                        observed_result=f"Exit code {proc.returncode}, stdout lines: {len(proc.stdout.splitlines())}",
                        confidence=ConfidenceLevel.VERIFIED,
                    ).to_dict()
                ]
                return AdapterResult(
                    success=(proc.returncode == 0),
                    status="COMPLETED" if proc.returncode == 0 else "FAILED",
                    output={"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr},
                    evidence=evidence,
                    errors=[proc.stderr] if proc.returncode != 0 and proc.stderr else [],
                ).to_dict()
            except Exception as e:
                return AdapterResult(
                    success=False,
                    status="FAILED",
                    errors=[str(e)],
                ).to_dict()

        return AdapterResult(
            success=False,
            status="UNSUPPORTED_ACTION",
            errors=[f"Unsupported adapter action: {action}"],
        ).to_dict()

    def health_check(self) -> dict[str, Any]:
        """Report adapter health and capability readiness."""
        workspace_accessible = self.workspace_root.exists() and os.access(self.workspace_root, os.R_OK)
        write_accessible = os.access(self.workspace_root, os.W_OK)

        healthy = workspace_accessible and write_accessible
        return {
            "adapter": self.name,
            "status": "HEALTHY" if healthy else "UNHEALTHY",
            "workspace_accessible": workspace_accessible,
            "workspace_writable": write_accessible,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
