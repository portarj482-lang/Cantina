"""Configuration management for OpenAI and Reasoning Providers."""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


def load_dotenv_dict(env_path: Optional[Path] = None) -> dict[str, str]:
    """Parse key-value pairs from a .env file without external dependencies."""
    candidates = []
    if env_path is not None:
        candidates.append(env_path)
    else:
        candidates.append(Path.cwd() / ".env")
        candidates.append(Path(__file__).resolve().parent.parent.parent / ".env")

    env_vars: dict[str, str] = {}
    for cand in candidates:
        if cand.is_file():
            try:
                for line in cand.read_text(encoding="utf-8").splitlines():
                    clean = line.strip()
                    if not clean or clean.startswith("#") or "=" not in clean:
                        continue
                    key, val = clean.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key and key not in env_vars:
                        env_vars[key] = val
            except Exception:
                pass
            break
    return env_vars


REASONING_MODELS = frozenset([
    "o1", "o1-mini", "o1-preview", "o3", "o3-mini", "o3-preview"
])

SUPPORTED_REASONING_EFFORTS = frozenset(["low", "medium", "high"])


def redact_api_key(key: Optional[str]) -> str:
    """Safely redact API key for logging and string representation."""
    if not key:
        return "<UNSET>"
    clean = key.strip()
    if len(clean) <= 12:
        return "[REDACTED]"
    prefix = clean[:7]
    suffix = clean[-4:]
    return f"{prefix}...[REDACTED]...{suffix}"


@dataclass
class OpenAIConfig:
    """Typed, validated configuration for OpenAI Reasoning Provider."""
    api_key: Optional[str] = field(default=None, repr=False)
    model: str = "o3-mini"
    reasoning_effort: Optional[str] = "high"
    timeout_seconds: float = 60.0
    max_retries: int = 2
    max_output_tokens: Optional[int] = None
    store_responses: bool = False
    base_url: str = "https://api.openai.com/v1"
    fallback_provider: str = "none"
    api_mode: str = "responses"  # "responses" or "chat_completions"
    audit_file: Optional[str] = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate configuration settings against model capabilities."""
        if not self.model or not self.model.strip():
            raise ValueError("OPENAI_MODEL must be specified and non-empty")

        if self.timeout_seconds <= 0:
            raise ValueError(f"OPENAI_TIMEOUT_SECONDS must be positive, got {self.timeout_seconds}")

        if self.max_retries < 0:
            raise ValueError(f"OPENAI_MAX_RETRIES cannot be negative, got {self.max_retries}")

        # Validate reasoning effort against model capabilities
        if self.reasoning_effort is not None:
            norm_effort = self.reasoning_effort.lower().strip()
            if norm_effort not in SUPPORTED_REASONING_EFFORTS:
                raise ValueError(
                    f"Invalid OPENAI_REASONING_EFFORT '{self.reasoning_effort}'. "
                    f"Must be one of {sorted(SUPPORTED_REASONING_EFFORTS)}"
                )
            # Check if model supports reasoning effort
            is_reasoning_model = any(self.model.startswith(m) for m in REASONING_MODELS)
            if not is_reasoning_model:
                raise ValueError(
                    f"OPENAI_REASONING_EFFORT is only supported on reasoning models ({sorted(REASONING_MODELS)}), "
                    f"not on '{self.model}'"
                )
            self.reasoning_effort = norm_effort

        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError(f"OPENAI_MAX_OUTPUT_TOKENS must be positive, got {self.max_output_tokens}")

    @classmethod
    def from_env(cls, env: Optional[dict[str, str]] = None) -> OpenAIConfig:
        """Construct configuration from environment variables, .env file, or custom dict."""
        if env is not None:
            source = env
        else:
            dotenv_vars = load_dotenv_dict()
            # os.environ values take precedence over .env file values
            source = {**dotenv_vars, **os.environ}

        api_key = source.get("OPENAI_API_KEY", "").strip() or None
        model = source.get("OPENAI_MODEL", "o3-mini").strip() or "o3-mini"

        raw_effort = source.get("OPENAI_REASONING_EFFORT")
        reasoning_effort = raw_effort.strip() if raw_effort and raw_effort.strip() else None
        # If model is not a reasoning model and effort was default, drop effort cleanly
        if reasoning_effort and not any(model.startswith(m) for m in REASONING_MODELS):
            reasoning_effort = None

        timeout_str = source.get("OPENAI_TIMEOUT_SECONDS", "60").strip()
        try:
            timeout_seconds = float(timeout_str)
        except ValueError:
            timeout_seconds = 60.0

        retries_str = source.get("OPENAI_MAX_RETRIES", "2").strip()
        try:
            max_retries = int(retries_str)
        except ValueError:
            max_retries = 2

        raw_max_tokens = source.get("OPENAI_MAX_OUTPUT_TOKENS", "").strip()
        max_output_tokens = int(raw_max_tokens) if raw_max_tokens and raw_max_tokens.isdigit() else None

        raw_store = source.get("OPENAI_STORE_RESPONSES", "false").strip().lower()
        store_responses = raw_store in ("true", "1", "yes")

        base_url = source.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        fallback = source.get("USAP_OPENAI_FALLBACK_PROVIDER", "none").strip()
        api_mode = source.get("OPENAI_API_MODE", "responses").strip().lower()
        audit_file = source.get("USAP_GATEWAY_AUDIT_FILE", None)

        return cls(
            api_key=api_key,
            model=model,
            reasoning_effort=reasoning_effort,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
            store_responses=store_responses,
            base_url=base_url,
            fallback_provider=fallback,
            api_mode=api_mode,
            audit_file=audit_file,
        )

    def to_safe_dict(self) -> dict[str, Any]:
        """Return safe representation of configuration without leaking API keys."""
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "max_output_tokens": self.max_output_tokens,
            "store_responses": self.store_responses,
            "base_url": self.base_url,
            "fallback_provider": self.fallback_provider,
            "api_mode": self.api_mode,
            "api_key_configured": bool(self.api_key),
            "api_key_redacted": redact_api_key(self.api_key),
        }
