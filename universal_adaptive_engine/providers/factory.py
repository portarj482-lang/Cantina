"""Provider factory for Universal Adaptive Reasoning Providers."""
from __future__ import annotations
import os
from typing import Any, Optional

from universal_adaptive_engine.providers.protocol import ReasoningProvider
from universal_adaptive_engine.providers.config import OpenAIConfig
from universal_adaptive_engine.providers.openai_provider import OpenAIReasoningProvider


def get_reasoning_provider(
    provider_name: Optional[str] = None,
    config: Optional[OpenAIConfig] = None,
    **kwargs: Any,
) -> ReasoningProvider:
    """Retrieve an initialized reasoning provider instance."""
    name = (provider_name or os.environ.get("USAP_REASONING_PROVIDER", "openai")).lower().strip()

    if name == "openai":
        cfg = config or OpenAIConfig.from_env()
        return OpenAIReasoningProvider(config=cfg, **kwargs)

    raise ValueError(f"Unknown or unsupported reasoning provider: '{name}'. Supported: ['openai']")


def list_available_providers() -> list[str]:
    """Return list of supported reasoning providers."""
    return ["openai"]
