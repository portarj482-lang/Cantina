"""Central execution policy independent of agent output."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionMode(str, Enum):
    FORK_ONLY = "fork_only"
    READ_ONLY = "read_only"


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    mode: ExecutionMode = ExecutionMode.FORK_ONLY
    allow_broadcast: bool = False
    allow_private_key_access: bool = False
    allow_live_funds: bool = False

    def validate(self) -> None:
        if self.allow_broadcast:
            raise ValueError("Transaction broadcasting is prohibited.")

        if self.allow_private_key_access:
            raise ValueError("Private-key access is prohibited.")

        if self.allow_live_funds:
            raise ValueError("Live-funds access is prohibited.")

    def authorize_capability(self, capability: str) -> None:
        """Call before granting any capability to an agent or tool."""
        self.validate()

        denied = {
            "broadcast",
            "forge_broadcast",
            "cast_send",
            "private_key_read",
            "private_key_export",
            "live_funds",
        }

        if capability.strip().lower() in denied:
            raise PermissionError(
                f"Execution policy denies capability: {capability}"
            )
