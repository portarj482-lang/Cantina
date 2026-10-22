"""Universal End-to-End Operation Pipelines and Specialized Invariant Workflows.

Provides specialized inherited pipelines connecting domain invariant oracles,
target sub-oracles, and attestation agents to the Universal Adaptive Architecture:
- Fault Dispute System (G4, INV-DISPUTE-01)
- DelayedWETH Solvency & Timelock (G5, INV-DELAYED-WETH-02)
- Base Multiproof TEE Attestation (G6, INV-MULTIPROOF-03)
- Linux RPC Administration & Governance (G3, G2, G1)
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter
from universal_adaptive_engine.workflows.base import AgentPipeline
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.cantina_pipeline import CantinaBountyPipeline
from universal_adaptive_engine.workflows.operations.dispute_pipeline import (
    DisputeSystemPipeline,
    DisputeAnalystWorkflow,
    DisputeSecurityReviewerWorkflow,
    DisputeProveVerifierWorkflow,
    DisputeFinalizeChallengerWorkflow,
)
from universal_adaptive_engine.workflows.operations.delayed_weth_pipeline import (
    DelayedWETHSolvencyPipeline,
    DelayedWETHAnalystWorkflow,
    DelayedWETHSecurityReviewerWorkflow,
    WETHSolvencyVerifierWorkflow,
    DelayBypassChallengerWorkflow,
)
from universal_adaptive_engine.workflows.operations.multiproof_tee_pipeline import (
    MultiproofTEEPipeline,
    MultiproofTEEAnalystWorkflow,
    MultiproofTEESecurityReviewerWorkflow,
    TEERegisterVerifierWorkflow,
    AttestationChallengerWorkflow,
)
from universal_adaptive_engine.workflows.operations.rpc_governance_pipeline import (
    RPCGovernancePipeline,
    RPCGovernancePlanWorkflow,
    RPCGovernanceAnalystWorkflow,
    RPCAuditSecurityWorkflow,
    RPCDaemonVerifierWorkflow,
    RPCChallengerWorkflow,
    RPCCleanupEvaluatorWorkflow,
)

OPERATIONS_REGISTRY = {
    "canonical": CanonicalAdaptivePipeline,
    "cantina": CantinaBountyPipeline,
    "dispute": DisputeSystemPipeline,
    "fault-dispute": DisputeSystemPipeline,
    "fault_dispute": DisputeSystemPipeline,
    "delayed-weth": DelayedWETHSolvencyPipeline,
    "delayed_weth": DelayedWETHSolvencyPipeline,
    "weth": DelayedWETHSolvencyPipeline,
    "multiproof-tee": MultiproofTEEPipeline,
    "multiproof_tee": MultiproofTEEPipeline,
    "tee": MultiproofTEEPipeline,
    "rpc-governance": RPCGovernancePipeline,
    "rpc_governance": RPCGovernancePipeline,
    "rpc": RPCGovernancePipeline,
}


def list_available_operations() -> list[str]:
    """Return the list of canonical operation pipeline names."""
    return [
        "canonical",
        "cantina",
        "dispute",
        "delayed-weth",
        "multiproof-tee",
        "rpc-governance",
    ]


def get_operation_pipeline(
    name: str,
    adapter: Optional[ArchitectureAdapter] = None,
    workspace_root: Path | str = "/home/nova/projects/cantina",
) -> AgentPipeline:
    """Factory creating a specialized end-to-end operation pipeline by name.

    Supported names:
    - 'dispute': Fault Dispute System (INV-DISPUTE-01)
    - 'delayed-weth': DelayedWETH Solvency (INV-DELAYED-WETH-02)
    - 'multiproof-tee': Multiproof TEE Attestation (INV-MULTIPROOF-03)
    - 'rpc-governance': Linux RPC Discovery & Governance Playbook
    - 'cantina': Cantina Bug Bounty general pipeline
    - 'canonical': Generic 14-stage universal adaptive pipeline
    """
    key = name.lower().strip().replace(" ", "-")
    pipeline_cls = OPERATIONS_REGISTRY.get(key)
    if not pipeline_cls:
        valid_keys = ", ".join(list_available_operations())
        raise ValueError(f"Unknown operation pipeline '{name}'. Supported operations: {valid_keys}")

    if pipeline_cls is CanonicalAdaptivePipeline:
        return CanonicalAdaptivePipeline(adapter=adapter, workspace_root=workspace_root)
    elif pipeline_cls is CantinaBountyPipeline:
        return CantinaBountyPipeline(workspace_root=workspace_root)
    else:
        return pipeline_cls(adapter=adapter, workspace_root=workspace_root)


__all__ = [
    "OPERATIONS_REGISTRY",
    "list_available_operations",
    "get_operation_pipeline",
    "DisputeSystemPipeline",
    "DisputeAnalystWorkflow",
    "DisputeSecurityReviewerWorkflow",
    "DisputeProveVerifierWorkflow",
    "DisputeFinalizeChallengerWorkflow",
    "DelayedWETHSolvencyPipeline",
    "DelayedWETHAnalystWorkflow",
    "DelayedWETHSecurityReviewerWorkflow",
    "WETHSolvencyVerifierWorkflow",
    "DelayBypassChallengerWorkflow",
    "MultiproofTEEPipeline",
    "MultiproofTEEAnalystWorkflow",
    "MultiproofTEESecurityReviewerWorkflow",
    "TEERegisterVerifierWorkflow",
    "AttestationChallengerWorkflow",
    "RPCGovernancePipeline",
    "RPCGovernancePlanWorkflow",
    "RPCGovernanceAnalystWorkflow",
    "RPCAuditSecurityWorkflow",
    "RPCDaemonVerifierWorkflow",
    "RPCChallengerWorkflow",
    "RPCCleanupEvaluatorWorkflow",
]
