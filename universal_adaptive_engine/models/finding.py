"""Canonical Finding Record model and validation."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.enums import (
    FindingStatus,
    ImpactLevel,
    ExploitabilityLevel,
    ConfidenceLevel,
)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "finding_record.schema.json"


class FindingValidationError(Exception):
    """Raised when finding record validation fails."""
    pass


@dataclass
class LocationRef:
    path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    symbol: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocationRef:
        return cls(
            path=str(data["path"]),
            start_line=data.get("start_line"),
            end_line=data.get("end_line"),
            symbol=data.get("symbol"),
        )


@dataclass
class RegressionResult:
    test_id: str
    outcome: str
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "outcome": self.outcome,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegressionResult:
        return cls(
            test_id=str(data["test_id"]),
            outcome=str(data["outcome"]),
            details=str(data.get("details", "")),
        )


@dataclass
class FindingRecord:
    finding_id: str
    title: str
    status: FindingStatus = FindingStatus.CANDIDATE
    source_refs: list[str] = field(default_factory=list)
    affected_versions: list[str] = field(default_factory=list)
    locations: list[LocationRef] = field(default_factory=list)
    original_labels: list[str] = field(default_factory=list)
    derived_labels: list[str] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    security_property: Optional[str] = None
    root_cause: Optional[str] = None
    impact: ImpactLevel = ImpactLevel.UNKNOWN
    exploitability: ExploitabilityLevel = ExploitabilityLevel.UNVERIFIED
    reproduction_refs: list[str] = field(default_factory=list)
    counterevidence_refs: list[str] = field(default_factory=list)
    fix_refs: list[str] = field(default_factory=list)
    regression_results: list[RegressionResult] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    unresolved_assumptions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "status": self.status.value if isinstance(self.status, FindingStatus) else str(self.status),
            "source_refs": list(self.source_refs),
            "affected_versions": list(self.affected_versions),
            "locations": [loc.to_dict() for loc in self.locations],
            "original_labels": list(self.original_labels),
            "derived_labels": list(self.derived_labels),
            "preconditions": list(self.preconditions),
            "security_property": self.security_property,
            "root_cause": self.root_cause,
            "impact": self.impact.value if isinstance(self.impact, ImpactLevel) else str(self.impact),
            "exploitability": self.exploitability.value if isinstance(self.exploitability, ExploitabilityLevel) else str(self.exploitability),
            "reproduction_refs": list(self.reproduction_refs),
            "counterevidence_refs": list(self.counterevidence_refs),
            "fix_refs": list(self.fix_refs),
            "regression_results": [reg.to_dict() for reg in self.regression_results],
            "confidence": self.confidence.value if isinstance(self.confidence, ConfidenceLevel) else str(self.confidence),
            "unresolved_assumptions": list(self.unresolved_assumptions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FindingRecord:
        status = FindingStatus(data.get("status", FindingStatus.CANDIDATE.value))
        impact = ImpactLevel(data.get("impact", ImpactLevel.UNKNOWN.value))
        exploitability = ExploitabilityLevel(data.get("exploitability", ExploitabilityLevel.UNVERIFIED.value))
        confidence = ConfidenceLevel(data.get("confidence", ConfidenceLevel.UNVERIFIED.value))

        locations = [
            LocationRef.from_dict(loc) if isinstance(loc, dict) else LocationRef(str(loc))
            for loc in data.get("locations", [])
        ]
        regression_results = [
            RegressionResult.from_dict(reg) for reg in data.get("regression_results", [])
        ]

        return cls(
            finding_id=str(data["finding_id"]),
            title=str(data["title"]),
            status=status,
            source_refs=list(data.get("source_refs", [])),
            affected_versions=list(data.get("affected_versions", [])),
            locations=locations,
            original_labels=list(data.get("original_labels", [])),
            derived_labels=list(data.get("derived_labels", [])),
            preconditions=list(data.get("preconditions", [])),
            security_property=data.get("security_property"),
            root_cause=data.get("root_cause"),
            impact=impact,
            exploitability=exploitability,
            reproduction_refs=list(data.get("reproduction_refs", [])),
            counterevidence_refs=list(data.get("counterevidence_refs", [])),
            fix_refs=list(data.get("fix_refs", [])),
            regression_results=regression_results,
            confidence=confidence,
            unresolved_assumptions=list(data.get("unresolved_assumptions", [])),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=str(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )

    def validate(self) -> None:
        """Validate against JSON schema and invariant rules."""
        data = self.to_dict()
        if SCHEMA_PATH.exists():
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema = json.load(f)
            jsonschema.validate(instance=data, schema=schema)
        else:
            raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

        # Invariant checks
        if not self.title.strip():
            raise FindingValidationError("Finding title cannot be empty")
        # Exploitability cannot be demonstrated without reproduction references
        if self.exploitability == ExploitabilityLevel.DEMONSTRATED and not self.reproduction_refs:
            raise FindingValidationError(
                f"Finding {self.finding_id} claims demonstrated exploitability without reproduction references"
            )
        # Status cannot be SUPPORTED or ACCEPTED without non-empty source refs and non-refuted confidence
        if self.status in (FindingStatus.SUPPORTED, FindingStatus.ACCEPTED):
            if not self.source_refs:
                raise FindingValidationError(
                    f"Finding {self.finding_id} cannot be marked {self.status.value} without source references"
                )
            if self.confidence in (ConfidenceLevel.REFUTED, ConfidenceLevel.UNVERIFIED):
                raise FindingValidationError(
                    f"Finding {self.finding_id} marked {self.status.value} has contradictory confidence: {self.confidence.value}"
                )
        # Status cannot be REFUTED with verified confidence or without counterevidence
        if self.status == FindingStatus.REFUTED:
            if self.confidence in (ConfidenceLevel.VERIFIED, ConfidenceLevel.HIGH):
                raise FindingValidationError(
                    f"Finding {self.finding_id} marked REFUTED cannot have verified/high confidence"
                )
            if not self.counterevidence_refs:
                raise FindingValidationError(
                    f"Finding {self.finding_id} cannot be marked REFUTED without counterevidence references"
                )
