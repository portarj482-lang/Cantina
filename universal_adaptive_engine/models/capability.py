"""Canonical Capability Record model and validation."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.enums import CapabilityStatus

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "capability_record.schema.json"


class CapabilityValidationError(Exception):
    """Raised when capability record validation fails."""
    pass


@dataclass
class CapabilityRecord:
    capability_id: str
    display_name: str
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    implementation_ref: Optional[str] = None
    interface_ref: Optional[str] = None
    owner: Optional[str] = None
    permissions_required: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    last_verified_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "display_name": self.display_name,
            "status": self.status.value if isinstance(self.status, CapabilityStatus) else str(self.status),
            "implementation_ref": self.implementation_ref,
            "interface_ref": self.interface_ref,
            "owner": self.owner,
            "permissions_required": list(self.permissions_required),
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "dependencies": list(self.dependencies),
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
            "last_verified_at": self.last_verified_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityRecord:
        status = CapabilityStatus(data.get("status", CapabilityStatus.UNKNOWN.value))
        return cls(
            capability_id=str(data["capability_id"]),
            display_name=str(data["display_name"]),
            status=status,
            implementation_ref=data.get("implementation_ref"),
            interface_ref=data.get("interface_ref"),
            owner=data.get("owner"),
            permissions_required=list(data.get("permissions_required", [])),
            inputs=list(data.get("inputs", [])),
            outputs=list(data.get("outputs", [])),
            dependencies=list(data.get("dependencies", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
            limitations=list(data.get("limitations", [])),
            last_verified_at=data.get("last_verified_at"),
        )

    def validate(self) -> None:
        """Validate against JSON schema and verification consistency."""
        data = self.to_dict()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        else:
            raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

        if self.status == CapabilityStatus.VERIFIED and not self.evidence_refs:
            raise CapabilityValidationError(
                f"Capability {self.capability_id} cannot be marked VERIFIED without evidence references"
            )
