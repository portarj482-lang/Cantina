"""Canonical models for Universal Adaptive Intelligence Architecture."""
from universal_adaptive_engine.models.enums import (
    TaskState,
    RiskLevel,
    FindingStatus,
    ImpactLevel,
    ExploitabilityLevel,
    ConfidenceLevel,
    CandidateType,
    AdaptationDecision,
    EvidenceType,
    BlockerCategory,
    CapabilityStatus,
    ResultStatus,
    ResolutionStatus,
)
from universal_adaptive_engine.models.blocker import BlockerRecord
from universal_adaptive_engine.models.task import (
    TaskRecord,
    TaskTests,
    InvalidStateTransitionError,
    TaskValidationError,
)
from universal_adaptive_engine.models.finding import (
    FindingRecord,
    LocationRef,
    RegressionResult,
    FindingValidationError,
)
from universal_adaptive_engine.models.adaptation import (
    AdaptationRecord,
    CompatibilityMatrix,
    AdaptationValidationError,
)
from universal_adaptive_engine.models.evidence import (
    EvidenceRecord,
    EvidenceValidationError,
)
from universal_adaptive_engine.models.capability import (
    CapabilityRecord,
    CapabilityValidationError,
)
from universal_adaptive_engine.models.handoff import (
    HandoffRecord,
    HandoffValidationError,
)
from universal_adaptive_engine.models.target_context import (
    TargetContext,
    TargetResultStatus,
    TargetFinding,
    TargetContextResolver,
)

__all__ = [
    "TaskState",
    "RiskLevel",
    "FindingStatus",
    "ImpactLevel",
    "ExploitabilityLevel",
    "ConfidenceLevel",
    "CandidateType",
    "AdaptationDecision",
    "EvidenceType",
    "BlockerCategory",
    "CapabilityStatus",
    "ResultStatus",
    "ResolutionStatus",
    "BlockerRecord",
    "TaskRecord",
    "TaskTests",
    "InvalidStateTransitionError",
    "TaskValidationError",
    "FindingRecord",
    "LocationRef",
    "RegressionResult",
    "FindingValidationError",
    "AdaptationRecord",
    "CompatibilityMatrix",
    "AdaptationValidationError",
    "EvidenceRecord",
    "EvidenceValidationError",
    "CapabilityRecord",
    "CapabilityValidationError",
    "HandoffRecord",
    "HandoffValidationError",
    "TargetContext",
    "TargetResultStatus",
    "TargetFinding",
    "TargetContextResolver",
]

