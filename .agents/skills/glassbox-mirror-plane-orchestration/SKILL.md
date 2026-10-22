---
id: skill-glassbox-mirror-plane-orchestration
name: Glassbox Mirror Plane Orchestration
description: >
  Eight-stage, evidence-grounded processing workflow for bounded
  security analysis, invariant verification, and auditable decisions.
---

# Glassbox Mirror Plane Orchestration

## Stage 1 — Perception Filtering
Normalize authorized inputs while preserving source evidence and
security-relevant syntax.

## Stage 2 — Parsing and Tokenization
Produce typed tokens or syntax structures with source mappings,
parser diagnostics, and version metadata.

## Stage 3 — Preceptive Feature Interpretation
Extract documented structural features and validate intermediate
representations against their contracts.

## Stage 4 — Thinking and Planning
Construct candidate analyses, dependency graphs, and verification plans.
Mark hypotheses separately from established facts.

## Stage 5 — Reasoning and Verification
Evaluate invariants, symbolic constraints, and proof obligations.
Record solver results, assumptions, and evidence references.

## Stage 6 — Context and Scope Modeling
Pin analysis to authorized repository state and task boundaries.
Reject unsupported scope expansion and stale evidence.

## Stage 7 — Awareness and Semantic Interpretation
Reconcile findings, identify contradictions, and preserve uncertainty.
Do not treat agent consensus as authoritative evidence.

## Stage 8 — Meta-Governance and Executive Authorization
Evaluate mandatory gates, policy compliance, and evidence completeness.
Authorize only permitted outcomes and produce an auditable result.

## Cross-Stage Requirements

- Autonomous Specialist Workflows: Specialists (Perception, Preceptive, Thinking,
  Reasoning, Context, Awareness, Governance) retain their internal logic and autonomy.
- Synchronization Barriers: Reconcile outputs, exchange approved state, pause,
  validate invariants, and resume independent workflows.
- Execution Containment: Sandboxed runtime boundaries deny network, unauthorized writes,
  and unauthorized subprocesses by default.
- Sandbox Lifecycle: The execution sandbox boundary is continuous. When advancing to
  the next epoch, the predecessor environment is locked, sealed, and pushed to the
  archive while the successor active sandbox inherits monotonic state.
- Validate all stage inputs and outputs against versioned schemas.
- Preserve provenance and canonical content digests.
- Enforce capabilities outside individual agent logic.
- Apply bounded retries, cancellation, and resource limits.
- Reject failed mandatory gates (fail-closed auditor veto).
- Keep unverified findings explicitly labeled.
- Persist only policy-approved structured audit records.
- Report limitations and unresolved issues in the final result.
