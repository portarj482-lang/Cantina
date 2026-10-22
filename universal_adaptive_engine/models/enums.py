"""Canonical Enums for Universal Adaptive Intelligence Architecture."""
from enum import Enum


class TaskState(str, Enum):
    PROPOSED = "PROPOSED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    VERIFYING = "VERIFYING"
    COMPLETED_WITH_LIMITATIONS = "COMPLETED_WITH_LIMITATIONS"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    UNRESOLVED = "UNRESOLVED"
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class ImpactLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    UNKNOWN = "unknown"


class ExploitabilityLevel(str, Enum):
    DEMONSTRATED = "demonstrated"
    PLAUSIBLE = "plausible"
    THEORETICAL = "theoretical"
    UNVERIFIED = "unverified"
    REFUTED = "refuted"


class ConfidenceLevel(str, Enum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"
    REFUTED = "refuted"


class CandidateType(str, Enum):
    SKILL = "skill"
    AGENT = "agent"
    TOOL = "tool"
    DATASET = "dataset"
    PROMPT = "prompt"
    SERVICE = "service"
    PATTERN = "pattern"
    ADAPTER = "adapter"


class AdaptationDecision(str, Enum):
    ACCEPTED_FOR_STAGING = "ACCEPTED_FOR_STAGING"
    ACCEPTED_FOR_PRODUCTION = "ACCEPTED_FOR_PRODUCTION"
    NEEDS_ADAPTATION = "NEEDS_ADAPTATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"
    DEPRECATED = "DEPRECATED"
    ROLLED_BACK = "ROLLED_BACK"


class EvidenceType(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    HYPOTHESIS = "HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"
    REFUTED = "REFUTED"
    SUPERSEDED = "SUPERSEDED"


class BlockerCategory(str, Enum):
    MISSING_CONTEXT = "MISSING_CONTEXT"
    INVALID_INPUT = "INVALID_INPUT"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    POLICY_BLOCK = "POLICY_BLOCK"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    RESOURCE_LIMIT = "RESOURCE_LIMIT"
    ENVIRONMENT_FAILURE = "ENVIRONMENT_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    UNKNOWN = "UNKNOWN"


class CapabilityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    ASSUMED = "ASSUMED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ResultStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_VERIFIED = "NOT_VERIFIED"


class ResolutionStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID = "INVALID"

