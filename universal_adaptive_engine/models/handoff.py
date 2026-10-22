"""Canonical Machine-Validated Agent Handoff Record model."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.task import TaskTests

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "handoff_record.schema.json"


class HandoffValidationError(Exception):
    """Raised when a handoff record fails schema or invariant validation."""
    pass


VALID_HANDOFF_STATUSES = {
    "COMPLETED_VERIFIED",
    "COMPLETED_WITH_LIMITATIONS",
    "BLOCKED",
    "FAILED",
    "NOT_RUN",
    "IN_PROGRESS",
}


@dataclass
class HandoffRecord:
    task_id: str
    agent_role: str
    status: str
    summary: str
    stage: Optional[str] = None
    claims: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    files_inspected: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    commands_run: list[dict[str, Any]] = field(default_factory=list)
    tests: TaskTests = field(default_factory=TaskTests)
    artifacts: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    security_concerns: list[str] = field(default_factory=list)
    next_action: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_role": self.agent_role,
            "stage": self.stage,
            "status": self.status,
            "summary": self.summary,
            "claims": list(self.claims),
            "evidence_refs": list(self.evidence_refs),
            "files_inspected": list(self.files_inspected),
            "files_changed": list(self.files_changed),
            "commands_run": [dict(c) for c in self.commands_run],
            "tests": self.tests.to_dict(),
            "artifacts": list(self.artifacts),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "security_concerns": list(self.security_concerns),
            "next_action": self.next_action,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HandoffRecord:
        tests_data = data.get("tests", {})
        if isinstance(tests_data, TaskTests):
            tests = tests_data
        elif isinstance(tests_data, dict):
            tests = TaskTests.from_dict(tests_data)
        else:
            tests = TaskTests()

        return cls(
            task_id=str(data["task_id"]),
            agent_role=str(data["agent_role"]),
            status=str(data["status"]),
            summary=str(data["summary"]),
            stage=data.get("stage"),
            claims=list(data.get("claims", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
            files_inspected=list(data.get("files_inspected", [])),
            files_changed=list(data.get("files_changed", [])),
            commands_run=list(data.get("commands_run", [])),
            tests=tests,
            artifacts=list(data.get("artifacts", [])),
            assumptions=list(data.get("assumptions", [])),
            limitations=list(data.get("limitations", [])),
            security_concerns=list(data.get("security_concerns", [])),
            next_action=str(data.get("next_action", "")),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
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
        if self.status not in VALID_HANDOFF_STATUSES:
            raise HandoffValidationError(f"Invalid status {self.status}; must be one of {VALID_HANDOFF_STATUSES}")

        if not self.summary.strip():
            raise HandoffValidationError("Handoff summary cannot be empty")

        if self.status == "COMPLETED_VERIFIED":
            if self.tests.failed:
                raise HandoffValidationError(
                    f"COMPLETED_VERIFIED cannot have failed tests: {self.tests.failed}"
                )
            if not self.evidence_refs:
                raise HandoffValidationError(
                    "COMPLETED_VERIFIED requires at least one evidence reference"
                )

        elif self.status == "COMPLETED_WITH_LIMITATIONS":
            if self.tests.failed:
                raise HandoffValidationError(
                    f"COMPLETED_WITH_LIMITATIONS cannot have unresolved failed tests: {self.tests.failed}"
                )
            if not self.limitations:
                raise HandoffValidationError(
                    "COMPLETED_WITH_LIMITATIONS requires at least one recorded limitation"
                )
            if not self.evidence_refs:
                raise HandoffValidationError(
                    "COMPLETED_WITH_LIMITATIONS requires at least one evidence reference"
                )

        elif self.status == "BLOCKED":
            if not (self.next_action or self.limitations or self.summary):
                raise HandoffValidationError("BLOCKED handoff must describe blocker in summary or next_action")
