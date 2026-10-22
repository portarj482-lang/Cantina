"""Data models for Universal Adaptive Reasoning Providers."""
from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ReasoningStatus(str, Enum):
    """Execution status of a reasoning request."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTH_FAILURE = "AUTHENTICATION_FAILED"
    TIMEOUT = "TIMEOUT"
    REFUSED = "REFUSED"
    REFUSAL = "REFUSED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_UNAVAILABLE"


class ReasoningPurpose(str, Enum):
    """Semantic purpose of the reasoning request."""
    INTAKE_INTERPRETATION = "intake_interpretation"
    PLANNING = "planning"
    DECOMPOSITION = "decomposition"
    ARCHITECTURE_ANALYSIS = "architecture_analysis"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    BLOCKER_DIAGNOSIS = "blocker_diagnosis"
    SECURITY_ASSISTANCE = "security_assistance"
    SECURITY_ANALYSIS = "security_assistance"
    TOOL_PROPOSAL = "tool_proposal"
    RECOVERY_RECOMMENDATION = "recovery_recommendation"
    COMPLETION_SUMMARY = "completion_summary"
    GENERIC = "generic"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities of a reasoning provider."""
    provider_name: str
    supported_models: tuple[str, ...]
    supports_reasoning_effort: bool = False
    supports_structured_outputs: bool = True
    supports_response_storage: bool = False
    supports_streaming: bool = False
    reasoning_efforts: tuple[str, ...] = ("low", "medium", "high")

    @property
    def supports_reasoning(self) -> bool:
        return self.supports_reasoning_effort

    @property
    def supports_structured_output(self) -> bool:
        return self.supports_structured_outputs

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "supported_models": list(self.supported_models),
            "supports_reasoning_effort": self.supports_reasoning_effort,
            "supports_structured_outputs": self.supports_structured_outputs,
            "supports_response_storage": self.supports_response_storage,
            "supports_streaming": self.supports_streaming,
            "reasoning_efforts": list(self.reasoning_efforts),
        }


@dataclass(frozen=True)
class ProviderHealth:
    """Health check outcome for a reasoning provider."""
    provider: str
    status: str  # "HEALTHY", "DEGRADED", "UNAVAILABLE"
    model: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class ReasoningRequest:
    """Input contract for a reasoning query."""
    instructions: str = ""
    task_id: str = field(default_factory=lambda: f"TASK-REASON-{uuid.uuid4().hex[:6]}")
    session_id: str = field(default_factory=lambda: f"SESS-{uuid.uuid4().hex[:6]}")
    purpose: ReasoningPurpose = ReasoningPurpose.GENERIC
    input_data: Any = ""
    target_context: Optional[dict[str, Any]] = None
    evidence_refs: list[str] = field(default_factory=list)
    output_schema: Optional[dict[str, Any]] = None
    resource_limits: dict[str, Any] = field(default_factory=dict)
    context_metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        instructions: str = "",
        prompt: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
        purpose: ReasoningPurpose = ReasoningPurpose.GENERIC,
        input_data: Any = "",
        target_context: Optional[dict[str, Any]] = None,
        evidence_refs: Optional[list[str]] = None,
        output_schema: Optional[dict[str, Any]] = None,
        structured_schema: Optional[dict[str, Any]] = None,
        context: Optional[dict[str, Any]] = None,
        system_instruction: Optional[str] = None,
        model_override: Optional[str] = None,
        resource_limits: Optional[dict[str, Any]] = None,
        context_metadata: Optional[dict[str, Any]] = None,
    ):
        self.instructions = instructions or prompt or ""
        self.task_id = task_id or f"TASK-REASON-{uuid.uuid4().hex[:6]}"
        self.session_id = session_id or f"SESS-{uuid.uuid4().hex[:6]}"
        self.purpose = purpose
        self.input_data = input_data if input_data != "" else (context if context is not None else "")
        self.target_context = target_context
        self.evidence_refs = evidence_refs or []
        self.output_schema = output_schema or structured_schema
        self.resource_limits = resource_limits or {}
        self.context_metadata = dict(context_metadata or {})
        if system_instruction:
            self.context_metadata["system_instruction"] = system_instruction
        if model_override:
            self.context_metadata["model_override"] = model_override

    def validate(self) -> None:
        if not self.instructions or not self.instructions.strip():
            raise ValueError("ReasoningRequest instructions must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "purpose": self.purpose.value if isinstance(self.purpose, ReasoningPurpose) else str(self.purpose),
            "instructions": self.instructions,
            "input_data": self.input_data,
            "target_context": self.target_context,
            "evidence_refs": self.evidence_refs,
            "output_schema": self.output_schema,
            "resource_limits": self.resource_limits,
            "context_metadata": self.context_metadata,
        }


@dataclass
class ReasoningResponse:
    """Output contract returned by a reasoning provider."""
    provider: str
    model: str
    status: ReasoningStatus
    output_text: str = ""
    structured_output: Optional[dict[str, Any]] = None
    request_id: str = field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:6]}")
    response_id: Optional[str] = None
    rationale_summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_success(self) -> bool:
        return self.status == ReasoningStatus.SUCCESS

    @property
    def content(self) -> str:
        return self.output_text

    @property
    def error_message(self) -> Optional[str]:
        return self.errors[0] if self.errors else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status.value,
            "output_text": self.output_text,
            "structured_output": self.structured_output,
            "request_id": self.request_id,
            "response_id": self.response_id,
            "rationale_summary": self.rationale_summary,
            "assumptions": self.assumptions,
            "evidence_refs": self.evidence_refs,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }
