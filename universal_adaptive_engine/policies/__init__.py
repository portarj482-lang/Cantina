"""Policies package for deterministic authorization, scope verification, and execution safety."""
from __future__ import annotations

from universal_adaptive_engine.policies.scope_verifier import (
    ScopeVerification,
    verify_scope_file,
)
from universal_adaptive_engine.policies.execution_policy import (
    ExecutionMode,
    ExecutionPolicy,
)
from universal_adaptive_engine.policies.authorization import (
    StageStatus,
    StageOutcome,
    PipelineRun,
)

__all__ = [
    "ScopeVerification",
    "verify_scope_file",
    "ExecutionMode",
    "ExecutionPolicy",
    "StageStatus",
    "StageOutcome",
    "PipelineRun",
]
