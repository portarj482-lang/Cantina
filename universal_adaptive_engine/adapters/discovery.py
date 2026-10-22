"""Target Discovery and Architecture Classification Adapters."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import BaseArchitectureAdapter, AdapterResult
from universal_adaptive_engine.models.target_context import TargetContext, TargetContextResolver


class TargetDiscoveryAdapter(BaseArchitectureAdapter):
    """Discovers target repository layout, runtime architecture, and authorized scope."""

    def __init__(
        self,
        workspace_root: Path | str = ".",
        target_root: Optional[Path | str] = None,
    ):
        super().__init__(name="target-discovery-adapter", version="1.0.0")
        self.workspace_root = Path(workspace_root).resolve()
        if target_root:
            tr = Path(target_root)
            self.target_root = (self.workspace_root / tr).resolve() if not tr.is_absolute() else tr.resolve()
        else:
            self.target_root = None

    def discover(self, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Perform architecture-aware discovery and return normalized TargetContext."""
        ctx = dict(context or {})
        if self.target_root and "target_root" not in ctx:
            ctx["target_root"] = str(self.target_root)
        if "workspace_root" not in ctx:
            ctx["workspace_root"] = str(self.workspace_root)

        target = TargetContextResolver.resolve(ctx, self.workspace_root)

        evidence = [{
            "evidence_id": f"EVID-DISCOVER-{target.target_id}",
            "architecture": target.architecture,
            "target_root": str(target.target_root),
            "manifests": [str(m) for m in target.manifests],
            "capabilities": list(target.capabilities),
            "is_valid": target.is_valid,
        }]

        return {
            "target_context": target,
            "is_valid": target.is_valid,
            "architecture": target.architecture,
            "capabilities": list(target.capabilities),
            "evidence": evidence,
        }

    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        target = contract.get("target_context")
        if not target or not isinstance(target, TargetContext):
            return {"valid": False, "reason": "Missing or invalid TargetContext"}
        if not target.is_valid:
            return {"valid": False, "reason": f"Target root does not exist: {target.target_root}"}
        return {"valid": True, "reason": "Target validated"}

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        disc = self.discover(task)
        return AdapterResult(
            success=disc["is_valid"],
            status="COMPLETED_VERIFIED" if disc["is_valid"] else "BLOCKED",
            output=disc,
            evidence=disc["evidence"],
        ).to_dict()

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "version": self.version,
            "status": "HEALTHY",
            "workspace_root": str(self.workspace_root),
        }
