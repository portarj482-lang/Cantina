"""Architecture Adapter Protocol and Base Adapter Definitions."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass
class AdapterResult:
    success: bool
    status: str
    output: Any = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "output": self.output,
            "evidence": list(self.evidence),
            "errors": list(self.errors),
            "timestamp": self.timestamp,
        }


@runtime_checkable
class ArchitectureAdapter(Protocol):
    """Protocol defining the adapter contract for host-native integration."""

    def discover(self) -> dict[str, Any]:
        """Return observed components, capabilities, constraints, and evidence."""
        ...

    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Validate a canonical request against host-native interfaces."""
        ...

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        """Execute only authorized work and return structured evidence."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Report adapter availability and health without hiding failures."""
        ...


class BaseArchitectureAdapter(ABC):
    """Abstract base class providing common adapter utility and safety wrappers."""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version

    @abstractmethod
    def discover(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def validate_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        pass

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        pass
