"""Cantina Bounty Workspace Adapter implementing ArchitectureAdapter for Cantina bounties."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import (
    BaseArchitectureAdapter,
    AdapterResult,
)
from universal_adaptive_engine.models.enums import CapabilityStatus, EvidenceType, ConfidenceLevel
from universal_adaptive_engine.models.evidence import EvidenceRecord


class CantinaBountyAdapter(BaseArchitectureAdapter):
    """Adapter that maps canonical contracts to Cantina Bug Bounty conventions."""

    def __init__(
        self,
        workspace_root: Path | str = ".",
        trusted_scope_sha256: Optional[str] = None,
    ):
        super().__init__(name="cantina-bounty-adapter", version="1.0.0")
        self.workspace_root = Path(workspace_root).resolve()
        self.trusted_scope_sha256 = trusted_scope_sha256

    def discover(self) -> dict[str, Any]:
        """Discover Cantina workspace structure, active bounties, and memory files."""
        bounties_dir = self.workspace_root / "bounties"
        bounties = []
        if bounties_dir.exists() and bounties_dir.is_dir():
            bounties = [p.name for p in bounties_dir.iterdir() if p.is_dir() and not p.name.startswith(".")]

        memory_file = self.workspace_root / "MEMORY.md"
        instructions_file = self.workspace_root / "INSTRUCTIONS.md"
        workflows_file = self.workspace_root / "WORKFLOWS.md"
        global_dir = self.workspace_root / "global"

        active_bounty = None
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if "Active bounty:" in line or "Active Bounty:" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        active_bounty = parts[1].strip()

        # Scope verification check for active bounty
        scope_verification = None
        if active_bounty:
            bounty_dir = bounties_dir / active_bounty
            scope_file = bounty_dir / "scope.md"
            snapshot_file = bounty_dir / "snapshots" / "scope.sha256"
            if scope_file.exists():
                trusted_sha = self.trusted_scope_sha256
                if not trusted_sha and snapshot_file.exists():
                    try:
                        trusted_sha = snapshot_file.read_text(encoding="utf-8").strip().split()[0]
                    except OSError:
                        trusted_sha = None

                if trusted_sha:
                    from universal_adaptive_engine.policies.scope_verifier import verify_scope_file
                    v = verify_scope_file(scope_file, trusted_sha)
                    scope_verification = {
                        "verified": v.verified,
                        "computed_sha": v.computed_sha256,
                        "computed_sha256": v.computed_sha256,
                        "expected_sha256": v.expected_sha256,
                        "reason": v.reason,
                    }
                else:
                    computed_sha = hashlib.sha256(scope_file.read_bytes()).hexdigest()
                    scope_verification = {
                        "verified": False,
                        "computed_sha": computed_sha,
                        "computed_sha256": computed_sha,
                        "expected_sha256": "",
                        "reason": "Missing trusted SHA-256 digest or snapshot",
                    }
            else:
                scope_verification = {
                    "verified": False,
                    "computed_sha": "",
                    "computed_sha256": "",
                    "expected_sha256": "",
                    "reason": f"scope.md not found in {bounty_dir}",
                }

        capabilities = {
            "cantina.bounties": {
                "status": CapabilityStatus.VERIFIED.value if bounties else CapabilityStatus.PARTIAL.value,
                "count": len(bounties),
                "slugs": bounties,
            },
            "cantina.active_bounty": {
                "status": CapabilityStatus.VERIFIED.value if active_bounty else CapabilityStatus.UNKNOWN.value,
                "slug": active_bounty,
            },
            "cantina.rules": {
                "status": CapabilityStatus.VERIFIED.value if instructions_file.exists() else CapabilityStatus.UNKNOWN.value,
            },
            "cantina.workflows": {
                "status": CapabilityStatus.VERIFIED.value if workflows_file.exists() else CapabilityStatus.UNKNOWN.value,
            },
        }

        evidence = [
            EvidenceRecord(
                evidence_id="EVID-CANTINA-DISCOVERY",
                evidence_type=EvidenceType.OBSERVED,
                source_ref=str(self.workspace_root),
                acquisition_method="cantina_workspace_inspection",
                observed_result=f"Cantina bounties found: {len(bounties)}, active: {active_bounty}, memory_file={memory_file.exists()}",
                confidence=ConfidenceLevel.VERIFIED,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ).to_dict()
        ]

        return {
            "adapter": self.name,
            "version": self.version,
            "bounties": bounties,
            "active_bounty": active_bounty,
            "has_memory": memory_file.exists(),
            "has_instructions": instructions_file.exists(),
            "has_workflows": workflows_file.exists(),
            "capabilities": capabilities,
            "evidence": evidence,
            "scope_verification": scope_verification,
        }

    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Validate request against Cantina non-negotiable rules."""
        issues = []
        task_id = contract.get("task_id", "unknown")
        inputs = contract.get("inputs", [])

        # Rule 1: One bounty in focus and authorized scope
        target_bounty = None
        for inp in inputs:
            if isinstance(inp, dict) and "bounty" in inp:
                target_bounty = inp["bounty"]

        if target_bounty:
            bounty_path = self.workspace_root / "bounties" / target_bounty
            if not bounty_path.exists():
                issues.append(f"Target bounty '{target_bounty}' does not exist in bounties directory")

        # Rule 2: No live-funds action
        if "live_funds" in str(contract).lower() or "mainnet_tx" in str(contract).lower():
            issues.append("Non-negotiable rule violation: Live-funds or mainnet state-changing transactions are strictly forbidden.")

        return {
            "valid": len(issues) == 0,
            "task_id": task_id,
            "issues": issues,
            "recommendation": "PROCEED" if len(issues) == 0 else "REJECT_VIOLATION",
        }

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute Cantina bounty-specific operations."""
        task_id = task.get("task_id", "unknown")
        action = task.get("action", "verify_scope")
        inputs = task.get("inputs", [])
        first_input = inputs[0] if inputs else None
        bounty_slug = None
        if isinstance(first_input, str):
            bounty_slug = first_input
        elif isinstance(first_input, dict):
            bounty_slug = first_input.get("bounty")

        if not bounty_slug:
            # Fall back to discovery active bounty
            disc = self.discover()
            bounty_slug = disc.get("active_bounty") or (disc.get("bounties")[0] if disc.get("bounties") else None)

        if not bounty_slug:
            return AdapterResult(
                success=False,
                status="BLOCKED",
                errors=["No active bounty specified or discovered"],
            ).to_dict()

        bounty_dir = self.workspace_root / "bounties" / bounty_slug

        if action == "verify_scope":
            scope_file = bounty_dir / "scope.md"
            snapshot_file = bounty_dir / "snapshots" / "scope.sha256"
            if not scope_file.exists():
                return AdapterResult(
                    success=False,
                    status="MISSING_SCOPE",
                    errors=[f"scope.md not found at {scope_file}"],
                ).to_dict()

            content = scope_file.read_bytes()
            computed_sha = hashlib.sha256(content).hexdigest()
            recorded_sha = None
            if snapshot_file.exists():
                recorded_sha = snapshot_file.read_text(encoding="utf-8").strip().split()[0]

            matches = (computed_sha == recorded_sha) if recorded_sha else False
            evidence = [
                EvidenceRecord(
                    evidence_id=f"EVID-SCOPE-{task_id}",
                    evidence_type=EvidenceType.OBSERVED,
                    source_ref=str(scope_file),
                    artifact_path=str(scope_file),
                    sha256=computed_sha,
                    acquisition_method="file_hash_verification",
                    observed_result=f"Scope file SHA-256: {computed_sha}. Snapshot match: {matches}",
                    confidence=ConfidenceLevel.VERIFIED,
                ).to_dict()
            ]

            return AdapterResult(
                success=True,
                status="VERIFIED" if matches else "UNVERIFIED_SNAPSHOT",
                output={"bounty": bounty_slug, "computed_sha256": computed_sha, "snapshot_sha256": recorded_sha, "matches": matches},
                evidence=evidence,
            ).to_dict()

        return AdapterResult(
            success=False,
            status="UNSUPPORTED_ACTION",
            errors=[f"Unsupported Cantina action: {action}"],
        ).to_dict()

    def health_check(self) -> dict[str, Any]:
        """Verify Cantina workspace health."""
        memory_file = self.workspace_root / "MEMORY.md"
        instructions_file = self.workspace_root / "INSTRUCTIONS.md"
        healthy = memory_file.exists() and instructions_file.exists()
        return {
            "adapter": self.name,
            "status": "HEALTHY" if healthy else "DEGRADED",
            "memory_file": memory_file.exists(),
            "instructions_file": instructions_file.exists(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
