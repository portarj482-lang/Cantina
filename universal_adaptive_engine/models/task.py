"""Canonical Task Record model and state machine enforcement."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema

from universal_adaptive_engine.models.enums import TaskState, RiskLevel, BlockerCategory
from universal_adaptive_engine.models.blocker import BlockerRecord

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "task_record.schema.json"


class InvalidStateTransitionError(Exception):
    """Raised when an invalid task state transition is attempted."""
    pass


class TaskValidationError(Exception):
    """Raised when task data fails schema or invariant validation."""
    pass


ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.PROPOSED: {TaskState.READY, TaskState.CANCELLED, TaskState.BLOCKED},
    TaskState.READY: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.BLOCKED},
    TaskState.RUNNING: {
        TaskState.WAITING,
        TaskState.BLOCKED,
        TaskState.FAILED,
        TaskState.VERIFYING,
        TaskState.CANCELLED,
    },
    TaskState.WAITING: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.BLOCKED},
    TaskState.BLOCKED: {TaskState.READY, TaskState.RUNNING, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.VERIFYING: {
        TaskState.COMPLETED_VERIFIED,
        TaskState.COMPLETED_WITH_LIMITATIONS,
        TaskState.FAILED,
        TaskState.BLOCKED,
        TaskState.CANCELLED,
        TaskState.RUNNING,
    },
    TaskState.FAILED: {TaskState.READY, TaskState.CANCELLED},
    TaskState.COMPLETED_VERIFIED: set(),
    TaskState.COMPLETED_WITH_LIMITATIONS: set(),
    TaskState.CANCELLED: set(),
}


@dataclass
class TaskTests:
    passed: list[Any] = field(default_factory=list)
    failed: list[Any] = field(default_factory=list)
    skipped: list[Any] = field(default_factory=list)
    not_run: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[Any]]:
        return {
            "passed": list(self.passed),
            "failed": list(self.failed),
            "skipped": list(self.skipped),
            "not_run": list(self.not_run),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskTests:
        return cls(
            passed=list(data.get("passed", [])),
            failed=list(data.get("failed", [])),
            skipped=list(data.get("skipped", [])),
            not_run=list(data.get("not_run", [])),
        )


@dataclass
class TaskRecord:
    task_id: str
    goal: str
    status: TaskState = TaskState.PROPOSED
    owner: str = "orchestrator"
    assigned_role: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    inputs: list[Any] = field(default_factory=list)
    expected_artifacts: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    permissions_required: list[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    attempt_count: int = 0
    evidence_refs: list[str] = field(default_factory=list)
    blocker: Optional[BlockerRecord] = None
    tests: TaskTests = field(default_factory=TaskTests)
    limitations: list[str] = field(default_factory=list)
    next_action: str = "Discover prerequisites"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def can_transition_to(self, new_state: TaskState) -> bool:
        return new_state in ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_state: TaskState, reason: str = "") -> None:
        if not self.can_transition_to(new_state):
            raise InvalidStateTransitionError(
                f"Cannot transition task {self.task_id} from {self.status.value} to {new_state.value}. "
                f"Allowed transitions: {[s.value for s in ALLOWED_TRANSITIONS.get(self.status, set())]}"
            )

        # Enforce completion invariants
        if new_state == TaskState.COMPLETED_VERIFIED:
            if not self.acceptance_criteria:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_VERIFIED without defined acceptance criteria."
                )
            if self.tests.failed:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_VERIFIED with failing tests: {self.tests.failed}"
                )
            if not self.evidence_refs:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_VERIFIED without evidence references."
                )
        elif new_state == TaskState.COMPLETED_WITH_LIMITATIONS:
            if not self.evidence_refs:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_WITH_LIMITATIONS without evidence references."
                )
            if not self.limitations:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_WITH_LIMITATIONS without recorded limitations."
                )
            if self.tests.failed:
                raise TaskValidationError(
                    f"Cannot mark task {self.task_id} as COMPLETED_WITH_LIMITATIONS with unresolved failing tests: {self.tests.failed}"
                )

        if new_state == TaskState.RUNNING:
            self.attempt_count += 1
            if self.blocker is not None:
                self.blocker = None
        elif new_state == TaskState.READY:
            if self.blocker is not None:
                self.blocker = None

        self.status = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def set_blocked(self, blocker: BlockerRecord) -> None:
        if not self.can_transition_to(TaskState.BLOCKED):
            raise InvalidStateTransitionError(
                f"Cannot block task {self.task_id} from current state {self.status.value}"
            )
        self.blocker = blocker
        self.transition_to(TaskState.BLOCKED, reason=blocker.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status.value if isinstance(self.status, TaskState) else str(self.status),
            "owner": self.owner,
            "assigned_role": self.assigned_role,
            "dependencies": list(self.dependencies),
            "inputs": list(self.inputs),
            "expected_artifacts": list(self.expected_artifacts),
            "acceptance_criteria": list(self.acceptance_criteria),
            "permissions_required": list(self.permissions_required),
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else str(self.risk_level),
            "attempt_count": self.attempt_count,
            "evidence_refs": list(self.evidence_refs),
            "blocker": self.blocker.to_dict() if self.blocker else None,
            "tests": self.tests.to_dict(),
            "limitations": list(self.limitations),
            "next_action": self.next_action,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskRecord:
        raw_status = data.get("status", TaskState.PROPOSED.value)
        status = TaskState(raw_status)
        raw_risk = data.get("risk_level", RiskLevel.LOW.value)
        risk_level = RiskLevel(raw_risk)

        blocker = None
        if data.get("blocker"):
            blocker = BlockerRecord.from_dict(data["blocker"])

        tests = TaskTests.from_dict(data.get("tests", {}))

        return cls(
            task_id=str(data["task_id"]),
            goal=str(data["goal"]),
            status=status,
            owner=str(data.get("owner", "orchestrator")),
            assigned_role=data.get("assigned_role"),
            dependencies=list(data.get("dependencies", [])),
            inputs=list(data.get("inputs", [])),
            expected_artifacts=list(data.get("expected_artifacts", [])),
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            permissions_required=list(data.get("permissions_required", [])),
            risk_level=risk_level,
            attempt_count=int(data.get("attempt_count", 0)),
            evidence_refs=list(data.get("evidence_refs", [])),
            blocker=blocker,
            tests=tests,
            limitations=list(data.get("limitations", [])),
            next_action=str(data.get("next_action", "Discover prerequisites")),
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
        if not self.goal.strip():
            raise TaskValidationError("Task goal cannot be empty")
        if self.attempt_count < 0:
            raise TaskValidationError("Attempt count cannot be negative")
