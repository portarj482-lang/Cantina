# Slither Refractor Mesh: Contract-Driven Meta-Agent Architecture

## Pack B Static Analysis & Glassbox Evidence Plane (UOOMA / UAIA v2.0.0)

**Document Version:** 1.0.0  
**Specification:** Contract-Driven Meta-Agent Mesh for Slither  
**Evidence Plane:** Glassbox Mirror Plane (8 Stages)  
**Control Plane:** Independent Runtime Governance & Gate Adjudication  
**CLI Wrappers:** `workflows/pack-b-static/workflow-slither.sh`, `scripts/run_slither_scan.sh`  
**Execution Engine:** `workflows/pack-b-static/slither_orchestrator.py`  
**Adapter:** `.agents/skills/qrpe/adapters/slither_adapter.py`  
**Contracts Module:** `workflows/pack-b-static/mesh_contracts.py`  

---

## 1. Architectural Overview: Refractor Mesh

The Slither Refractor Mesh transforms static analysis from a descriptive Bash wrapper into a high-fidelity, contract-governed, multi-agent execution pipeline. The architecture strictly separates three planes of responsibility:

```
+---------------------------------------------------------------------------------+
|                               1. COGNITIVE PLANE                                |
|        (Proposes plans, hypotheses, triage models, verification strategies)     |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                          2. GLASSBOX EVIDENCE PLANE                             |
|  (Stage 1-8 Execution, Primary Evidence, Source Digests, Provenance, Uncertainty)|
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       3. GOVERNANCE & CONTROL PLANE                             |
|  (Authorization, Gate Decisions, Separation of Proposer & Evaluator, Veto Gate) |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       4. TRUSTED EXECUTION CONTROLLER                           |
|       (Slither Adapter, Sandboxed Execution, Resource Limits, Atomic Swap)      |
+---------------------------------------------------------------------------------+
```

### Invariant: Agents Never Grant Themselves Authority
Cognitive agents (Orchestrator, Triage Specialist, Challenger) may propose hypotheses, plans, and finding assessments; the independent control plane (`GovernanceGateAdjudicator`) authorizes execution, evaluates mandatory gates, and admits results. Proposer and evaluator identities are strictly separated (`proposer != evaluator`).

---

## 2. Five Canonical Contracts

All handoffs between components and agents use versioned, schema-validated contracts:

| Contract | Schema File | Purpose & Enforced Fields |
|---|---|---|
| `TaskContract` | `task_contract.schema.json` | Scope (`slug`, `repository_root`, `target_path`, `output_dir`), prerequisites, permissions (`execution_mode`, `write_allowed`), budget (`timeout_seconds`), acceptance criteria, monotonic state. |
| `ToolContract` | `tool_contract.schema.json` | Tool identity (`slither`), version (`0.11.6`), capability tags, effects (`writes_filesystem: false`, `network_access: false`, `subprocesses: true`, `idempotent: true`), restrictions, verification status. |
| `EvidenceContract` | `evidence_contract.schema.json` | Physical source, git revision, cryptographic digest (`sha256`), acquisition method (`slither_static_analysis`), timestamp, provenance (`tool`, `tool_version`, `run_id`), state (`OBSERVED`, `DERIVED`, etc.). |
| `FindingContract` | `finding_contract.schema.json` | Detector original output vs mesh verification: `rule_id`, detector version, location, severity, exploitability hypothesis, classification (`candidate` -> `triaged` -> `reproduced` / `independently_verified` / `rejected` / `inconclusive`), verification level (`unverified` / `verified` / `refuted`), `evidence_refs`, `counterevidence_refs`, `limitations`. |
| `GateDecisionContract` | `gate_decision_contract.schema.json` | Mandatory gates (`gate_id`, `gate_name`), required checks, passed checks, failed checks, decision (`ACCEPTED`, `BLOCKED`, `REJECTED`), rationale, `proposer`, `evaluator` (`INDEPENDENT_GOVERNANCE_GATE`), audit reference. |

---

## 3. Glassbox Mirror Plane 8-Stage Execution Lifecycle

Every execution transitions monotonically through eight explicit Glassbox stages:

```
[1. Perception Filtering] --------> Discover repository root, revision, validate slug & path containment
          |
          v
[2. Parsing & Tokenization] ------> Preflight verify adapter, Python interpreter, and tooling registry
          |
          v
[3. Preceptive Interpretation] ---> Bind ToolContract, verify Slither capabilities, input/output contracts
          |
          v
[4. Thinking & Planning] ---------> Construct TaskContract, evaluate authorization (DRY_RUN vs LIVE)
          |
          +--(Dry-Run Mode: Preview & Zero Writes)-----------------------------> [DRY_RUN_COMPLETE]
          |
          v (Confirmed Mode: Write Authorized)
[5. Reasoning & Verification] ----> Supervised execution with timeouts, resource limits, atomic staging
          |
          v
[6. Context & Scope Modeling] ----> Independent artifact verification, read-back SHA-256, attribution check
          |
          v
[7. Awareness & Semantic Triage] -> Independent Challenger checks counterevidence (reentrancy guards, pragma)
          |
          v
[8. Meta-Governance & Admission] -> GateDecisionContract evaluation, veto rule, atomic evidence envelope
          |
          +--(Total Findings > 0)----------------------------------------------> [COMPLETED_WITH_FINDINGS]
          |
          +--(Total Findings == 0 && Coverage Verified)------------------------> [COMPLETED_CLEAN]
```

---

## 4. Non-Negotiable Invariants

1. **No Unauthorized Execution:** `--dry-run` always takes precedence over `--confirm`. Zero filesystem writes occur on dry run.
2. **No Unvalidated Handoffs:** Every contract and envelope is validated against strict JSON Schema before persistence.
3. **No Untraceable Findings:** Every finding is linked to primary evidence references (`evidence_refs`), rule IDs, detector version, and git commit.
4. **No Silent Failure Recovery:** All state transitions are recorded in an append-only monotonic ledger (`state_history`).
5. **No Unsupported Vulnerability Claims:** Findings progress through explicit states (`candidate` -> `triaged` -> `reproduced` / `independently_verified` / `rejected` / `inconclusive`) with documented limitations.
6. **No Automatic Production Promotion:** Consequential changes require explicit release gates.
7. **No Self-Approval:** Proposer and evaluator roles are structurally distinct on all gate decisions.
8. **No False Success Reports:** Scanner failure (`1`), missing reports, corrupt JSON, digest mismatches, or attribution mismatches must never exit 0 or be labeled clean.

---

## 5. Verification Records & Test Coverage

The implementation includes two automated test suites:

- **CLI Acceptance Test Suite (`tests/test_workflow_slither.sh`):**
  - Tests 18 distinct acceptance scenarios (59 / 59 assertions passing).
  - Validates dry-run defaults, live scans, path escapes, prefix match attacks, scanner crashes, corrupt SARIF, attribution mismatches, clean scans, and prompt injection resilience.
- **Python Pytest Suite (`tests/test_slither_mesh.py`):**
  - 16 comprehensive unit tests (all passing).
  - Validates `TaskContract`, `ToolContract`, `EvidenceContract`, `FindingContract`, `GateDecisionContract` schema compliance.
  - Validates `SlitherIndependentChallenger` counterexample detection (e.g. `nonReentrant` modifier detection) and gate adjudication fail-closed behavior.
- **Shell Wrapper Hardening (`scripts/run_slither_scan.sh`):**
  - Path canonicalization, parent existence checks, output inside target prevention, dry-run precedence.
