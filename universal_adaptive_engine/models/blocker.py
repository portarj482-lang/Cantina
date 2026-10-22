"""Blocker Record and taxonomy recovery definitions."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Optional
from universal_adaptive_engine.models.enums import BlockerCategory


@dataclass
class BlockerRecord:
    category: BlockerCategory
    message: str
    recoverable: bool
    diagnosis: str = ""
    recovery_action: str = ""
    stop_condition: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value if isinstance(self.category, BlockerCategory) else str(self.category),
            "message": self.message,
            "recoverable": self.recoverable,
            "diagnosis": self.diagnosis,
            "recovery_action": self.recovery_action,
            "stop_condition": self.stop_condition,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockerRecord:
        category = BlockerCategory(data["category"])
        return cls(
            category=category,
            message=str(data["message"]),
            recoverable=bool(data["recoverable"]),
            diagnosis=str(data.get("diagnosis", "")),
            recovery_action=str(data.get("recovery_action", "")),
            stop_condition=str(data.get("stop_condition", "")),
        )

    @classmethod
    def create_diagnosed(
        cls,
        category: BlockerCategory,
        message: str,
        diagnosis: str,
        recovery_action: str,
        stop_condition: str,
        recoverable: bool = True
    ) -> BlockerRecord:
        return cls(
            category=category,
            message=message,
            recoverable=recoverable,
            diagnosis=diagnosis,
            recovery_action=recovery_action,
            stop_condition=stop_condition,
        )
