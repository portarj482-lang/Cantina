---
name: universal-inherited-workflow
description: >-
  Defines the 14-stage universal workflow lifecycle and inheritable pipeline classes connecting all 12 specialist agents, structured handoffs, and verification gates.
---

# Universal Inherited Workflow Skill

## Overview

The Universal Inherited Workflow enforces the canonical 14-stage engineering lifecycle defined in the Universal Adaptive Intelligence Architecture blueprint. It is implemented as a suite of composable, inheritable Python classes under `universal_adaptive_engine.workflows`.

## 14-Stage Lifecycle and Specialist Agent Mapping

| Stage | Canonical Stage Enum | Default Specialist Agent | Responsibilities |
|---|---|---|---|
| 1 | `INTAKE` | `OrchestratorWorkflow` | Validate scope, establish non-negotiable boundaries and measurable goal |
| 2 | `DISCOVERY` | `ArchitectureAnalystWorkflow` | Run `adapter.discover()`, map components and canonical capabilities |
| 3 | `BASELINE` | `RepositoryInvestigatorWorkflow` | Inspect repository files, verify presence and baseline hashes |
| 4 | `DECOMPOSITION` | `OrchestratorWorkflow` | Break objective into bounded tasks with IDs, risk levels, and roles |
| 5 | `PLAN` | `OrchestratorWorkflow` | Order tasks by dependencies and define concrete acceptance criteria |
| 6 | `AUTHORIZATION_CHECK` | `SecurityReviewerWorkflow` | Verify path containment (`is_relative_to`), least privilege, secret policy |
| 7 | `IMPLEMENTATION` | `ImplementationEngineerWorkflow` | Execute bounded vertical slice code changes with clean diffs |
| 8 | `VERIFICATION` | `VerificationEngineerWorkflow` | Execute deterministic automated tests and capture evidence |
| 9 | `INDEPENDENT_REVIEW` | `IndependentChallengerWorkflow` | Adversarial review: negative controls, falsification, counterexamples |
| 10 | `STAGING` | `ReleaseEngineerWorkflow` | Validate staging admission criteria and verify rollback recipes |
| 11 | `APPROVAL` | `ReleaseEngineerWorkflow` | Enforce explicit change authorization before promotion |
| 12 | `DEPLOYMENT` | `ReleaseEngineerWorkflow` | Promote changes to deployment target (or mark skipped with reason) |
| 13 | `POST_DEPLOYMENT_VALIDATION` | `EvaluatorWorkflow` | Measure post-deployment metrics, regression rate (0 tolerance) |
| 14 | `COMPLETION_REPORT` | `OrchestratorWorkflow` | Finalize structured report distinguishing verified, partial, and blocked items |

## Machine-Validated Handoff Envelope (`HandoffRecord`)

Every agent workflow step returns a validated `HandoffRecord` matching Section 10 of the architecture specification:
- `task_id`: Unique identifier
- `agent_role`: Executing specialist persona
- `stage`: Current lifecycle stage
- `status`: `COMPLETED_VERIFIED | COMPLETED_WITH_LIMITATIONS | BLOCKED | FAILED | NOT_RUN`
- `summary`: Human- and machine-readable outcome summary
- `claims`: Factual claims produced by the agent
- `evidence_refs`: Supporting evidence record IDs (required for `COMPLETED_VERIFIED`)
- `tests`: Test results (`passed`, `failed`, `skipped`, `not_run`; no failures permitted in verified status)
- `artifacts`: Created or modified files
- `limitations`: Explicit omissions or constraints (required for `COMPLETED_WITH_LIMITATIONS`)
- `next_action`: Immediate handoff target or recovery step

## Inheritance and Specialization

Domain-specific pipelines inherit from `CanonicalAdaptivePipeline` and override specific stages with specialized subagent workflows:

```python
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.cantina_pipeline import (
    CantinaArchitectureAnalystWorkflow,
    CantinaSecurityReviewerWorkflow,
)
from universal_adaptive_engine.workflows.base import WorkflowStage

class MyCustomPipeline(CanonicalAdaptivePipeline):
    def __init__(self, workspace_root):
        super().__init__(name="My-Custom-Pipeline", workspace_root=workspace_root)
        # Override stages
        self.override_stage(WorkflowStage.DISCOVERY, CantinaArchitectureAnalystWorkflow(self.adapter))
        # Skip stages with explicit reason
        self.skip_stage(WorkflowStage.DEPLOYMENT, "Audit-only workflow; deployment not applicable")
```

## Universal Domain Operation Pipelines

The system provides concrete, end-to-end operation pipelines connecting domain invariant oracles, target sub-oracles, and attestation agents:

| Operation Pipeline | Governing Oracle | Invariant / Focus | Target Sub-Oracles & Sub-Surface Agents | Target Contracts / Modules |
|---|---|---|---|---|
| `DisputeSystemPipeline` (`dispute`) | G4 (Dispute Invariant Oracle) | `INV-DISPUTE-01` (Withdrawal Finalization Monotonicity) | `dispute-prove-agent`, `dispute-finalize-agent`, `game-resolution-agent`, `blacklist-maturity-agent`, `delay-bypass-agent` | `OptimismPortal2.sol`, `DisputeGameFactory.sol`, `AnchorStateRegistry.sol` |
| `DelayedWETHSolvencyPipeline` (`delayed-weth`) | G5 (DelayedWETH Invariant Oracle) | `INV-DELAYED-WETH-02` (Sub-Account Solvency & Timelock) | `weth-unlock-agent`, `weth-withdraw-agent`, `weth-solvency-agent`, `delay-bypass-agent` | `DelayedWETH.sol`, `WETH98.sol` |
| `MultiproofTEEPipeline` (`multiproof-tee`) | G6 (Multiproof TEE Invariant Oracle) | `INV-MULTIPROOF-03` (Signer Authenticity & Attestation Gating) | `tee-register-agent`, `tee-validity-agent`, `attestation-timestamp-agent`, `inverse-hint-integrity-agent`, `signer-lifecycle-agent` | `TEEProverRegistry.sol`, `hints.rs`, `NitroValidator` |
| `RPCGovernancePipeline` (`rpc-governance`) | G3 (RPC Admin Oracle) & G2 / G1 | Linux Ubuntu RPC discovery, daemon binding, and non-destructive audit | `purpose-agent`, `scope-agent`, `audit-agent`, `rpcbind-agent`, `rpcinfo-agent`, `rpcclient-agent`, `network-security-agent`, `firewall-agent`, `cleanup-agent` | `ubuntu-rpc`, `bounties/<slug>/scope.md`, `port 111` |

Every operation pipeline inherits the 14-stage lifecycle from `CanonicalAdaptivePipeline`, specializes `DISCOVERY`, `AUTHORIZATION_CHECK`, `VERIFICATION`, and `INDEPENDENT_REVIEW`, enforces adversarial negative controls, and marks production `DEPLOYMENT` as skipped with explicit audit rationale.

## CLI Execution

Run pipelines and agent workflows directly:
```bash
# 1. Execute domain operation pipelines
python3 universal_adaptive_engine/cli.py operation --name dispute
python3 universal_adaptive_engine/cli.py operation --name delayed-weth
python3 universal_adaptive_engine/cli.py operation --name multiproof-tee
python3 universal_adaptive_engine/cli.py operation --name rpc-governance

# 2. Execute via pipeline flavor
python3 universal_adaptive_engine/cli.py pipeline --flavor dispute --goal "Verify withdrawal finalization"
python3 universal_adaptive_engine/cli.py pipeline --flavor delayed-weth --goal "Verify WETH balance solvency"
python3 universal_adaptive_engine/cli.py pipeline --flavor multiproof-tee --goal "Audit TEE attestation transcripts"
python3 universal_adaptive_engine/cli.py pipeline --flavor rpc-governance --goal "Audit portmapper daemon and services"
python3 universal_adaptive_engine/cli.py pipeline --flavor cantina --goal "Verify bounty scope integrity"
python3 universal_adaptive_engine/cli.py pipeline --flavor canonical --goal "Run standard engineering lifecycle"

# 3. Execute a single specialist agent step
python3 universal_adaptive_engine/cli.py agent-workflow --agent analyst --goal "Map host capabilities"
```
