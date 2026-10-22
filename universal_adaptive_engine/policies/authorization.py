"""Typed authorization and lifecycle state models for canonical pipeline controllers."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StageStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class StageOutcome:
    stage: str
    status: StageStatus
    reason: str = ""
    evidence_refs: tuple[str, ...] = ()


@dataclass
class PipelineRun:
    run_id: str
    authorized: bool = False
    scope_digest: str | None = None
    stage_outcomes: list[StageOutcome] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
