"""Cantina-specific authorization and execution-policy review."""
from __future__ import annotations

from typing import Any

from universal_adaptive_engine.policies.execution_policy import (
    ExecutionPolicy,
)
from universal_adaptive_engine.workflows.agents.security_reviewer import (
    SecurityReviewerWorkflow,
)


class CantinaSecurityReviewerWorkflow(SecurityReviewerWorkflow):
    """Cantina-specific authorization and execution-policy review."""

    def __init__(self, adapter: Any, policy: ExecutionPolicy | None = None):
        super().__init__(adapter)
        self.execution_policy = policy or ExecutionPolicy()

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        self.execution_policy.validate()

        result = super().run_step(context)

        if not isinstance(result, dict):
            raise TypeError(
                "Security reviewer must return a dictionary."
            )

        result.setdefault("claims", [])
        result.setdefault("limitations", [])
        result.setdefault("security_concerns", [])

        result["claims"].append(
            "Configured execution policy prohibits broadcasting, "
            "private-key access, and live-funds access."
        )

        result["security_concerns"].append(
            "Runtime enforcement must be independently verified by "
            "sandbox, tool-dispatch, and network-policy tests."
        )

        # Deliberately do not append a synthetic passing test.
        return result
