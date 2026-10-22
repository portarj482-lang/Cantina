"""Canonical pipeline specialized for authorized Cantina audits."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.cantina_adapter import (
    CantinaBountyAdapter,
)
from universal_adaptive_engine.policies.execution_policy import (
    ExecutionPolicy,
)
from universal_adaptive_engine.workflows.base import WorkflowStage
from universal_adaptive_engine.workflows.canonical_pipeline import (
    CanonicalAdaptivePipeline,
)
from universal_adaptive_engine.workflows.cantina.analyst import (
    CantinaArchitectureAnalystWorkflow,
)
from universal_adaptive_engine.workflows.cantina.security_reviewer import (
    CantinaSecurityReviewerWorkflow,
)


class CantinaBountyPipeline(CanonicalAdaptivePipeline):
    """Canonical pipeline specialized for authorized Cantina audits."""

    def __init__(
        self,
        workspace_root: Path | str = "/home/nova/projects/cantina",
        *,
        execution_policy: ExecutionPolicy | None = None,
        trusted_scope_sha256: Optional[str] = None,
    ) -> None:
        root = Path(workspace_root).expanduser().resolve(strict=True)

        if not root.is_dir():
            raise NotADirectoryError(
                f"Workspace root is not a directory: {root}"
            )

        self.cantina_root = root
        self.execution_policy = execution_policy or ExecutionPolicy()
        self.execution_policy.validate()

        # Use the same resolved root for the adapter and pipeline.
        adapter = CantinaBountyAdapter(root, trusted_scope_sha256=trusted_scope_sha256)

        super().__init__(
            name="Cantina-Bounty-Adaptive-Pipeline",
            adapter=adapter,
            workspace_root=root,
        )

        self.override_stage(
            WorkflowStage.DISCOVERY,
            CantinaArchitectureAnalystWorkflow(adapter),
        )

        self.override_stage(
            WorkflowStage.AUTHORIZATION_CHECK,
            CantinaSecurityReviewerWorkflow(
                adapter,
                policy=self.execution_policy,
            ),
        )

        # Production deployment is intentionally not part of a bounty
        # audit. Verification and reporting remain required.
        self.skip_stage(
            WorkflowStage.DEPLOYMENT,
            "not applicable: bounty validation is performed in an "
            "authorized, isolated environment. This skip is not a "
            "successful deployment.",
        )
