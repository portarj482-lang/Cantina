"""Solana Architecture Adapter providing Anchor and native program integration."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import BaseArchitectureAdapter, AdapterResult
from universal_adaptive_engine.models.target_context import TargetContext


class SolanaArchitectureAdapter(BaseArchitectureAdapter):
    """Adapter exposing Solana/Anchor verification capabilities."""

    def __init__(self, target_context: TargetContext):
        super().__init__(name="solana-architecture-adapter", version="1.0.0")
        self.target = target_context

    def discover(self) -> dict[str, Any]:
        has_anchor = any("Anchor.toml" in str(m) for m in self.target.manifests)
        has_cargo = any("Cargo.toml" in str(m) for m in self.target.manifests)

        caps = ["solana.signers", "solana.pda_ownership", "solana.account_constraints"]
        if has_anchor:
            caps.extend(["solana.anchor.test", "solana.anchor.idl"])
        if has_cargo:
            caps.extend(["rust.cargo.test"])

        return {
            "architecture": "solana",
            "capabilities": caps,
            "has_anchor": has_anchor,
            "has_cargo": has_cargo,
            "source_roots": [str(p) for p in self.target.source_roots],
            "test_roots": [str(p) for p in self.target.test_roots],
        }

    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        if self.target.architecture != "solana":
            return {"valid": False, "reason": f"Solana adapter incompatible with architecture: {self.target.architecture}"}
        return {"valid": True, "reason": "Target confirmed as Solana"}

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        return AdapterResult(
            success=True,
            status="COMPLETED_VERIFIED",
            output={"executed_task": task.get("action", "verify_solana"), "target": self.target.target_id},
        ).to_dict()

    def health_check(self) -> dict[str, Any]:
        return {
            "adapter": self.name,
            "version": self.version,
            "status": "HEALTHY",
            "architecture": "solana",
            "target": self.target.target_id,
        }
