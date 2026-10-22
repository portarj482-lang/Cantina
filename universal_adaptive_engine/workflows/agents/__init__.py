"""Specialist Agent Workflows for Universal Adaptive Intelligence Architecture."""
from universal_adaptive_engine.workflows.agents.orchestrator import OrchestratorWorkflow
from universal_adaptive_engine.workflows.agents.analyst import ArchitectureAnalystWorkflow
from universal_adaptive_engine.workflows.agents.investigator import RepositoryInvestigatorWorkflow
from universal_adaptive_engine.workflows.agents.compiler import DomainCompilerEngineerWorkflow
from universal_adaptive_engine.workflows.agents.security_researcher import DomainSecurityResearcherWorkflow
from universal_adaptive_engine.workflows.agents.security_reviewer import SecurityReviewerWorkflow
from universal_adaptive_engine.workflows.agents.engineer import ImplementationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.verifier import VerificationEngineerWorkflow
from universal_adaptive_engine.workflows.agents.challenger import IndependentChallengerWorkflow
from universal_adaptive_engine.workflows.agents.release import ReleaseEngineerWorkflow
from universal_adaptive_engine.workflows.agents.evaluator import EvaluatorWorkflow
from universal_adaptive_engine.workflows.agents.curator import KnowledgeCuratorWorkflow

__all__ = [
    "OrchestratorWorkflow",
    "ArchitectureAnalystWorkflow",
    "RepositoryInvestigatorWorkflow",
    "DomainCompilerEngineerWorkflow",
    "DomainSecurityResearcherWorkflow",
    "SecurityReviewerWorkflow",
    "ImplementationEngineerWorkflow",
    "VerificationEngineerWorkflow",
    "IndependentChallengerWorkflow",
    "ReleaseEngineerWorkflow",
    "EvaluatorWorkflow",
    "KnowledgeCuratorWorkflow",
]
