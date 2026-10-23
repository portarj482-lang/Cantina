#!/usr/bin/env python3
"""
Canonical Contracts and Model Definitions for Medusa Dynamic Property Fuzzing Agent.
Implements typed dataclasses and JSON Schema validators for:
1. TaskContract
2. FindingContract
3. CampaignManifest
4. EvidenceEnvelope
5. GateDecisionContract
6. AuditEvent
7. StageResult
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import jsonschema

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(schema_name: str) -> dict[str, Any]:
    """Load JSON schema from the local schemas directory."""
    schema_path = SCHEMAS_DIR / schema_name
    if not schema_path.is_file():
        raise FileNotFoundError(f"Schema not found at {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


@dataclass
class TaskContract:
    task_id: str
    goal: str
    status: str
    owner: str
    dependencies: list[str]
    inputs: dict[str, Any]
    permissions_required: list[str]
    acceptance_criteria: list[str]
    expected_artifacts: list[str]
    attempt_count: int
    evidence_refs: list[str]
    blocker: Optional[str]
    tests: list[str]
    limitations: list[str]
    next_action: Optional[str]
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("task_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class FindingContract:
    finding_id: str
    title: str
    status: str
    source_refs: list[str]
    affected_versions: list[str]
    locations: list[dict[str, Any]]
    security_property: str
    preconditions: list[str]
    root_cause: str
    impact: str
    exploitability: str
    reproduction_refs: list[str]
    counterevidence_refs: list[str]
    fix_refs: list[str]
    regression_results: list[str]
    confidence: str
    unresolved_assumptions: list[str]
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("finding_contract.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class CampaignManifest:
    run_id: str
    repository_revision: str
    target: str
    medusa_version: str
    compiler_version: str
    configuration_digest: str
    binary_digest: Optional[str]
    seed: Optional[int]
    resource_limits: dict[str, Any]
    start_time: str
    end_time: str
    process_exit_status: int
    campaign_outcome: str
    property_results: list[dict[str, Any]]
    artifact_refs: list[str]
    verification_status: str
    limitations: list[str]
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("campaign_manifest.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class EvidenceEnvelope:
    envelope_id: str
    slug: str
    run_id: str
    status: str
    evidence_type: str
    manifest: dict[str, Any]
    digests: dict[str, str]
    provenance: dict[str, Any]
    timestamp: str
    workflow: str = "pack-c-dynamic"
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("evidence_envelope.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class GateDecisionContract:
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
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("gate_decision.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class AuditEvent:
    event_id: str
    event_type: str
    run_id: str
    stage: str
    actor: str
    action: str
    status: str
    details: dict[str, Any]
    timestamp: str
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        schema = load_schema("audit_event.schema.json")
        jsonschema.validate(instance=self.to_dict(), schema=schema)


@dataclass
class StageResult:
    stage_number: int
    stage_name: str
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
    schema_version: str = "2.0.0"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
