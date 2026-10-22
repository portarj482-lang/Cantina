"""Canonical 14-Stage Universal Adaptive Pipeline."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter
from universal_adaptive_engine.workflows.base import (
    AgentPipeline,
    WorkflowStage,
)
from universal_adaptive_engine.workflows.agents.orchestrator import OrchestratorWorkflow
from universal_adaptive_engine.workflows.agents.analyst import ArchitectureAnalystWorkflow
from universal_adaptive_engine.workflows.agents.investigator import RepositoryInvestigatorWorkflow
from universal_adaptive_engine.workflows.agents.security_reviewer import SecurityReviewerWorkflow
from universal_adaptive_engine.workflows.agents.engineer import ImplementationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.verifier import VerificationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.challenger import IndependentChallengerWorkflow
from universal_adaptive_engine.workflows.agents.release import ReleaseEngineerWorkflow
from universal_adaptive_engine.workflows.agents.evaluator import EvaluatorWorkflow


class CanonicalAdaptivePipeline(AgentPipeline):
    """The canonical 14-stage engineering lifecycle pipeline.

    Connects:
    INTAKE -> DISCOVERY -> BASELINE -> DECOMPOSITION -> PLAN ->
    AUTHORIZATION_CHECK -> IMPLEMENTATION -> VERIFICATION ->
    INDEPENDENT_REVIEW -> STAGING -> APPROVAL -> DEPLOYMENT ->
    POST_DEPLOYMENT_VALIDATION -> COMPLETION_REPORT

    All specialist agents are wired to their respective stages and share the host adapter.
    This class can be inherited to specialize stages for specific platforms (e.g. Cantina, EVM, CI/CD).
    """

    def __init__(
        self,
        name: str = "Canonical-Universal-Adaptive-Pipeline",
        adapter: Optional[ArchitectureAdapter] = None,
        workspace_root: Path | str = "/home/nova/projects/cantina",
    ):
        super().__init__(name=name, adapter=adapter)
        self.workspace_root = Path(workspace_root).resolve()
        self._setup_canonical_stages()

    def _setup_canonical_stages(self) -> None:
        """Configure default 14-stage lifecycle with specialist agent workflows."""
        # 1. INTAKE
        self.add_stage(WorkflowStage.INTAKE, OrchestratorWorkflow(self.adapter))

        # 2. DISCOVERY
        self.add_stage(WorkflowStage.DISCOVERY, ArchitectureAnalystWorkflow(self.adapter))

        # 3. BASELINE
        self.add_stage(WorkflowStage.BASELINE, RepositoryInvestigatorWorkflow(self.adapter))

        # 4. DECOMPOSITION
        self.add_stage(WorkflowStage.DECOMPOSITION, OrchestratorWorkflow(self.adapter))

        # 5. PLAN
        self.add_stage(WorkflowStage.PLAN, OrchestratorWorkflow(self.adapter))

        # 6. AUTHORIZATION_CHECK
        self.add_stage(WorkflowStage.AUTHORIZATION_CHECK, SecurityReviewerWorkflow(self.adapter))

        # 7. IMPLEMENTATION
        self.add_stage(WorkflowStage.IMPLEMENTATION, ImplementationEngineerWorkflow(self.adapter))

        # 8. VERIFICATION
        self.add_stage(WorkflowStage.VERIFICATION, VerificationEngineerWorkflow(self.adapter))

        # 9. INDEPENDENT_REVIEW
        self.add_stage(WorkflowStage.INDEPENDENT_REVIEW, IndependentChallengerWorkflow(self.adapter))

        # 10. STAGING
        self.add_stage(WorkflowStage.STAGING, ReleaseEngineerWorkflow(self.adapter))

        # 11. APPROVAL
        self.add_stage(WorkflowStage.APPROVAL, ReleaseEngineerWorkflow(self.adapter))

        # 12. DEPLOYMENT
        self.add_stage(WorkflowStage.DEPLOYMENT, ReleaseEngineerWorkflow(self.adapter))

        # 13. POST_DEPLOYMENT_VALIDATION
        self.add_stage(WorkflowStage.POST_DEPLOYMENT_VALIDATION, EvaluatorWorkflow(self.adapter))

        # 14. COMPLETION_REPORT
        self.add_stage(WorkflowStage.COMPLETION_REPORT, OrchestratorWorkflow(self.adapter))
