---
name: semgrep-mesh
description: Pack B Governed Agentic Mesh for Semgrep static analysis under UAIA and the Glassbox Mirror Plane.
---

# Pack B — Governed Semgrep Meta-Agentic Mesh Skill

## Overview

This skill coordinates authorized Semgrep static-analysis workflows using a bounded specialist-agent mesh and the 8-stage Glassbox Mirror Plane under the Universal Adaptive Intelligence Architecture (UAIA). It guarantees reproducible analysis results, verifiable cryptographic evidence, explicit limitations, and a deterministic policy-governed final disposition (Gates G1–G8).

## Governing Invariants

1. **Authority is centralized; reasoning is distributed:** Specialist agents analyze, challenge, and recommend, but cannot grant themselves permissions or override mandatory gates. Proposer and evaluator roles are strictly separated (`proposer != evaluator`).
2. **Evidence is the synchronization mechanism:** Agents exchange versioned artifacts and typed task envelopes (`MeshTaskEnvelope`) backed by cryptographic SHA-256 digests rather than conversational assertions.
3. **Completion is an admitted state, not a successful process exit:** A successful Semgrep binary exit is only one execution receipt; admission requires deterministic passage through all eight acceptance gates.

## The Six Cooperating Planes

| Plane | Responsibility | Enforceable Output |
|---|---|---|
| **Intent and governance** | Interpret request, validate slug, enforce path containment, resolve authorization mode | `request.normalized.json` |
| **Agent mesh** | Delegate bounded research, configuration inspection, finding challenge, and coverage | Typed `MeshTaskEnvelope` messages |
| **Orchestration** | Schedule dependencies, manage timeouts, process containment, state machine transitions | Monotonic `state_history` |
| **Execution** | Run pinned adapter under isolated runtime, capture stdout, stderr, raw artifacts | `raw/stdout.log`, `raw/stderr.log`, `raw/semgrep.json` |
| **Glassbox verification** | Validate schema, provenance, SHA-256 digests, and finding source attribution | `validation/schema-report.json`, `verification-report.json` |
| **Evidence and audit** | Preserve run artifacts, audit manifests, admission ledger, sealed envelope | `manifest.json`, `evidence_envelope.json` |

## Specialist Agent Mesh

1. **Scope and Repository Agent (`scope-agent`):** `repository.scope.inspect` (Read-only). Resolves git revision, target boundary containment, scannable files, and exclusions -> produces `inputs.inventory.json`.
2. **Semgrep Configuration Agent (`semgrep-config-agent`):** `semgrep.config.inspect` (Proposal only). Inspects pinned rulesets, language support, exclusions, and computes configuration digest.
3. **Execution Coordinator (`execution-coordinator`):** `execution.run.broker` (Brokered access). Enforces execution grants (`write_allowed = confirm && !dry_run`), creates run directory, captures stdout/stderr, records execution duration and exit codes.
4. **Finding Verification Agent (`finding-verification-agent`):** `finding.verify.challenge` (Independent review). Challenges candidate findings against physical source code, lines, test fixtures, inline ignore pragmas (`nosec`, `semgrep-ignore`), assigns classifications (`candidate` -> `triaged` -> `independently_verified` / `rejected` / `inconclusive`).
5. **Coverage and Reconciliation Agent (`coverage-reconciliation-agent`):** `coverage.reconcile` (Read-only). Compares requested scope inventory with actual Semgrep scan coverage (`paths.scanned`), flags missing or excluded files, produces coverage ratio and reconciliation report.
6. **Governance and Admission Agent (`governance-admission-agent`):** `governance.admit` (No self-approval). Evaluates gates G1 through G8 and proposes disposition; final admission is adjudicated by `GovernanceGateAdjudicator`.

## Glassbox Mirror Plane 8 Stages & Synchronization Barriers

- **Stage 1 (Perception):** Ingest intent, resolve paths, validate slug containment -> `request.normalized.json`
- *Barrier A (Authorization):* Gate G1 & G2 check scope, permissions, path containment.
- **Stage 2 (Parsing):** Preflight adapter, Python, Semgrep tool, inventory files -> `inputs.inventory.json`
- **Stage 3 (Interpretation):** Bind ToolContract, verify config and compute digest -> `analysis.intermediate.json`
- *Barrier B (Reproducibility):* Gate G5 pins tool version, config digest, source revision.
- **Stage 4 (Planning):** Construct TaskContract, evaluate dry-run vs confirmed mode -> `execution.plan.json`
- **Stage 5 (Verification Execution):** Brokered execution, process timeouts, capture raw stdout/stderr/JSON.
- *Barrier C (Execution Integrity):* Gate G3 checks process exit codes and diagnostics.
- **Stage 6 (Context Modeling):** Independent read-back SHA-256 verification, schema check, finding attribution -> `provenance.manifest.json`
- *Barrier D (Evidence Integrity):* Gate G4 verifies artifacts, digests, and JSON conformances.
- **Stage 7 (Reconciliation):** Challenge findings against source lines, evaluate scan coverage -> `verification.report.json`, `reconciliation.report.json`
- *Barrier E (Semantic Reconciliation):* Gates G6 & G7 verify coverage and finding challenge results.
- **Stage 8 (Governance):** Evaluate Gate G8, adjudicate admission, seal evidence envelope -> `admission.decision.json`, `manifest.json`, `evidence_envelope.json`.
- *Barrier F (Governance Admission):* Mandatory passage of all gates before `ADMITTED` status.

## CLI Usage

```bash
# Dry-run preview (default, zero writes)
workflows/pack-b-static/workflow-semgrep.sh --slug <bounty-slug>

# Confirmed execution with evidence persistence
workflows/pack-b-static/workflow-semgrep.sh --slug <bounty-slug> --confirm

# Explicit target and configuration
workflows/pack-b-static/workflow-semgrep.sh --slug <bounty-slug> --target contracts/src --config auto --confirm
```

## Key Files

- Entrypoint: `workflows/pack-b-static/workflow-semgrep.sh`
- Orchestrator: `workflows/pack-b-static/semgrep_orchestrator.py`
- Canonical Contracts: `workflows/pack-b-static/mesh_contracts.py`
- Schemas: `workflows/pack-b-static/schemas/`
- Meta-Agent Prompt: `.agents/prompts/universal_adaptive_meta_agent.md`
- Architecture Specification: `workflows/pack-b-static/SEMGREP_MESH.md`
