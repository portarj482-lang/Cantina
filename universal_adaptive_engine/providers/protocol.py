"""Protocol definition for Universal Adaptive Reasoning Providers."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable

from universal_adaptive_engine.providers.models import (
    ReasoningRequest,
    ReasoningResponse,
    ProviderCapabilities,
    ProviderHealth,
)


@runtime_checkable
class ReasoningProvider(Protocol):
    """Protocol that all reasoning providers must implement."""

    provider_name: str

    def health_check(self) -> ProviderHealth:
        """Perform a health check and verify provider responsiveness."""
        ...

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Execute a text-based or task-level reasoning query."""
        ...

    def reason_structured(
        self,
        request: ReasoningRequest,
        schema: dict[str, Any],
    ) -> ReasoningResponse:
        """Execute a structured reasoning query conforming to a JSON schema."""
        ...

    def get_capabilities(self) -> ProviderCapabilities:
        """Return the declared capabilities of this provider."""
        ...
