#!/usr/bin/env python3
"""
Canonical Contracts and Model Definitions for the Slither Refractor Mesh.
Provides typed dataclasses and JSON Schema validators for:
1. TaskContract
2. ToolContract
3. EvidenceContract
4. FindingContract
5. GateDecisionContract
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonschema

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(schema_name: str) -> dict[str, Any]:
    """Load JSON schema from the schemas directory."""
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


@dataclass
class TaskContract:
    schema_version: str
    task_id: str
    objective: str
    target_scope: dict[str, Any]
    prerequisites: list[str]
    permissions: dict[str, Any]
    budget: dict[str, Any]
    acceptance_criteria: list[str]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("task_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class ToolContract:
    schema_version: str
    tool_id: str
    name: str
    version: str
    description: str
    capabilities: list[str]
    effects: dict[str, Any]
    restrictions: dict[str, Any]
    verification_status: str
    input_schema: Optional[dict[str, Any]] = None
    output_schema: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.input_schema is None:
            d.pop("input_schema", None)
        if self.output_schema is None:
            d.pop("output_schema", None)
        return d

    def validate(self) -> None:
        schema = load_schema("tool_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class EvidenceContract:
    schema_version: str
    evidence_id: str
    evidence_type: str
    source: str
    revision: str
    digest: dict[str, str]
    acquisition_method: str
    timestamp: str
    provenance: dict[str, Any]
    state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("evidence_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class FindingContract:
    schema_version: str
    finding_id: str
    source_revision: str
    detector: dict[str, Any]
    classification: str
    verification: str
    evidence_refs: list[str] = field(default_factory=list)
    counterevidence_refs: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[dict[str, Any]] = None
    severity: Optional[dict[str, Any]] = None
    exploitability_hypothesis: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Drop None optional values
        return {k: v for k, v in d.items() if v is not None}

    def validate(self) -> None:
        schema = load_schema("finding_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class GateDecisionContract:
    schema_version: str
    gate_id: str
    gate_name: str
    required_checks: list[str]
    passed_checks: list[str]
    failed_checks: list[str]
    decision: str
    rationale: str
    proposer: str
    evaluator: str
    audit_reference: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("gate_decision_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class StageResult:
    stage_number: int
    stage_name: str
    schema_version: str
    input_evidence_refs: list[str]
    processing_method: str
    tool_versions: dict[str, str]
    output_artifacts: list[str]
    content_digests: dict[str, str]
    validation_status: str
    diagnostics: list[str]
    assumptions: list[str]
    uncertainty: list[str]
    unresolved_obligations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
