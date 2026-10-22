"""Scope-gated Architecture Analyst for Cantina workspaces."""
from __future__ import annotations

from typing import Any

from universal_adaptive_engine.adapters.cantina_adapter import (
    CantinaBountyAdapter,
)
from universal_adaptive_engine.workflows.agents.analyst import (
    ArchitectureAnalystWorkflow,
)


class CantinaArchitectureAnalystWorkflow(
    ArchitectureAnalystWorkflow
):
    """Scope-gated architecture analyst for Cantina workspaces."""

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(self.adapter, CantinaBountyAdapter):
            raise RuntimeError(
                "Cantina analyst requires CantinaBountyAdapter."
            )

        discovery = self.adapter.discover()
        verification = discovery.get("scope_verification")

        if not isinstance(verification, dict):
            return {
                "status": "BLOCKED",
                "claims": [],
                "limitations": [
                    "Scope verification evidence is missing."
                ],
                "security_concerns": [
                    "Protected analysis was not started."
                ],
            }

        if verification.get("verified") is not True:
            return {
                "status": "BLOCKED",
                "claims": [],
                "limitations": [
                    "Cantina scope verification failed."
                ],
                "security_concerns": [
                    "Protected analysis was not started."
                ],
            }

        # Pass the already verified snapshot or its immutable identifier
        # to the parent workflow, if the parent supports that contract.
        # The adapter must guarantee that subsequent reads use the
        # exact verified snapshot.
        computed_digest = verification.get("computed_sha256") or verification.get("computed_sha") or ""
        guarded_context = {
            **context,
            "cantina_scope_verified": True,
            "cantina_scope_sha256": computed_digest,
        }

        result = super().run_step(guarded_context)

        if not isinstance(result, dict):
            raise TypeError(
                "Architecture analyst must return a dictionary."
            )

        result.setdefault("claims", [])
        result.setdefault("limitations", [])
        result.setdefault("security_concerns", [])

        result["claims"].append(
            "Scope digest matched the configured trusted snapshot."
        )

        return result
