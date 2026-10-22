"""Canonical Adaptation Record model and admission policy validation."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.enums import CandidateType, AdaptationDecision

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "adaptation_record.schema.json"


class AdaptationValidationError(Exception):
    """Raised when adaptation decision record fails validation or admission policy."""
    pass


@dataclass
class CompatibilityMatrix:
    contracts: str = "not_checked"  # "compatible", "incompatible", "not_checked", "needs_adapter"
    dependencies: str = "not_checked"  # "compatible", "incompatible", "not_checked", "missing_dependency"
    security: str = "not_checked"  # "passed", "failed", "not_checked", "sandbox_required"
    regressions: str = "not_checked"  # "none_observed", "degraded", "not_checked"

    def to_dict(self) -> dict[str, str]:
        return {
            "contracts": self.contracts,
            "dependencies": self.dependencies,
            "security": self.security,
            "regressions": self.regressions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompatibilityMatrix:
        return cls(
            contracts=str(data.get("contracts", "not_checked")),
            dependencies=str(data.get("dependencies", "not_checked")),
            security=str(data.get("security", "not_checked")),
            regressions=str(data.get("regressions", "not_checked")),
        )


@dataclass
class AdaptationRecord:
    candidate_id: str
    candidate_type: CandidateType
    license: str
    intended_capability: str
    rationale: str
    compatibility: CompatibilityMatrix = field(default_factory=CompatibilityMatrix)
    source_ref: Optional[str] = None
    version: Optional[str] = None
    checksum: Optional[str] = None
    baseline_ref: Optional[str] = None
    candidate_evaluation_ref: Optional[str] = None
    protected_core_changed: bool = False
    shared_contracts_changed: bool = False
    approval_required: bool = True
    approval_ref: Optional[str] = None
    decision: AdaptationDecision = AdaptationDecision.NEEDS_ADAPTATION
    rollback_ref: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type.value if isinstance(self.candidate_type, CandidateType) else str(self.candidate_type),
            "source_ref": self.source_ref,
            "version": self.version,
            "checksum": self.checksum,
            "license": self.license,
            "intended_capability": self.intended_capability,
            "compatibility": self.compatibility.to_dict(),
            "baseline_ref": self.baseline_ref,
            "candidate_evaluation_ref": self.candidate_evaluation_ref,
            "protected_core_changed": self.protected_core_changed,
            "shared_contracts_changed": self.shared_contracts_changed,
            "approval_required": self.approval_required,
            "approval_ref": self.approval_ref,
            "decision": self.decision.value if isinstance(self.decision, AdaptationDecision) else str(self.decision),
            "rationale": self.rationale,
            "rollback_ref": self.rollback_ref,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptationRecord:
        candidate_type = CandidateType(data["candidate_type"])
        decision = AdaptationDecision(data.get("decision", AdaptationDecision.NEEDS_ADAPTATION.value))
        compatibility = CompatibilityMatrix.from_dict(data.get("compatibility", {}))

        return cls(
            candidate_id=str(data["candidate_id"]),
            candidate_type=candidate_type,
            source_ref=data.get("source_ref"),
            version=data.get("version"),
            checksum=data.get("checksum"),
            license=str(data["license"]),
            intended_capability=str(data["intended_capability"]),
            compatibility=compatibility,
            baseline_ref=data.get("baseline_ref"),
            candidate_evaluation_ref=data.get("candidate_evaluation_ref"),
            protected_core_changed=bool(data.get("protected_core_changed", False)),
            shared_contracts_changed=bool(data.get("shared_contracts_changed", False)),
            approval_required=bool(data.get("approval_required", True)),
            approval_ref=data.get("approval_ref"),
            decision=decision,
            rationale=str(data["rationale"]),
            rollback_ref=data.get("rollback_ref"),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=str(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )

    def validate(self) -> None:
        """Validate against JSON schema and admission control invariants."""
        data = self.to_dict()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        else:
            raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

        # Admission control rules
        if self.decision == AdaptationDecision.ACCEPTED_FOR_PRODUCTION:
            if not self.rollback_ref:
                raise AdaptationValidationError(
                    f"Production admission of candidate {self.candidate_id} requires a verified rollback reference"
                )
            if self.approval_required and not self.approval_ref:
                raise AdaptationValidationError(
                    f"Production admission of candidate {self.candidate_id} requires an explicit approval reference"
                )
            if self.compatibility.security != "passed":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot enter production with unpassed security check: {self.compatibility.security}"
                )
            if self.compatibility.contracts != "compatible":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot enter production with incompatible contracts: {self.compatibility.contracts}"
                )
            if self.compatibility.dependencies != "compatible":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot enter production with incompatible dependencies: {self.compatibility.dependencies}"
                )
            if self.compatibility.regressions == "degraded":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot enter production with observed regression degradation"
                )
            if not self.baseline_ref and not self.candidate_evaluation_ref:
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot enter production without baseline or evaluation reference"
                )

        if self.decision in (AdaptationDecision.ACCEPTED_FOR_PRODUCTION, AdaptationDecision.ACCEPTED_FOR_STAGING):
            if self.compatibility.security == "failed":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot be accepted with failed security check"
                )
            if self.compatibility.contracts == "incompatible":
                raise AdaptationValidationError(
                    f"Candidate {self.candidate_id} cannot be accepted with incompatible contracts"
                )

        if self.protected_core_changed and not self.approval_ref:
            raise AdaptationValidationError(
                f"Candidate {self.candidate_id} modifies protected core policy and requires explicit external approval"
            )
