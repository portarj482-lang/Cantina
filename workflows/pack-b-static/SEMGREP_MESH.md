# Semgrep Governed Agentic Mesh: Contract-Driven Architecture

## Pack B Static Analysis & Glassbox Mirror Plane (UAIA / OAM v2.0.0)

**Document Version:** 1.0.0  
**Specification:** Contract-Driven Governed Agentic Mesh for Semgrep Static Analysis  
**Coordination Plane:** Universal Adaptive Intelligence Architecture (UAIA)  
**Evidence Plane:** Glassbox Mirror Plane (8 Stages)  
**Control Plane:** Independent Runtime Governance & Gate Adjudication (Gates G1–G8)  
**CLI Wrapper:** `workflows/pack-b-static/workflow-semgrep.sh`  
**Execution Engine:** `workflows/pack-b-static/semgrep_orchestrator.py`  
**Adapter:** `.agents/skills/qrpe/adapters/semgrep_adapter.py`  
**Contracts Module:** `workflows/pack-b-static/mesh_contracts.py`  
**Meta-Agent Prompt:** `.agents/prompts/universal_adaptive_meta_agent.md`  

---

## 1. Architectural Overview: Governed Agentic Mesh

The Semgrep static analysis workflow evolves from a governed script wrapper into a high-fidelity, evidence-driven meta-agentic mesh under the Universal Adaptive Intelligence Architecture (UAIA). The architecture enforces three non-negotiable invariants:

1. **Authority is centralized; reasoning is distributed.** Specialist agents analyze, challenge, and recommend, but cannot grant themselves permissions or override mandatory gates. Proposer and evaluator roles are strictly separated (`proposer != evaluator`).
2. **Evidence is the synchronization mechanism.** Agents exchange versioned artifacts and typed task envelopes (`MeshTaskEnvelope`) backed by cryptographic SHA-256 digests rather than conversational assertions.
3. **Completion is an admitted state, not a successful process exit.** A clean exit from the Semgrep binary is merely one execution receipt; admission requires deterministic passage through all eight acceptance gates.

```
+---------------------------------------------------------------------------------+
|                        UAIA META-AGENT CONTROL PLANE                            |
|             Intent · Planning · Policy · Capability Selection · Budget          |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                            SPECIALIST AGENT MESH                                |
|  1. ScopeRepositoryAgent   2. SemgrepConfigAgent    3. ExecutionCoordinator     |
|  4. FindingVerification    5. CoverageReconciliation 6. GovernanceAdmission     |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                         GLASSBOX MIRROR EVIDENCE PLANE                          |
|  Stage 1: Perception     (request.normalized.json)                              |
|  Stage 2: Parsing        (inputs.inventory.json)                                |
|  Stage 3: Interpretation (analysis.intermediate.json)                           |
|  Stage 4: Planning       (execution.plan.json)                                  |
|  Stage 5: Verification   (verification.report.json)                             |
|  Stage 6: Context        (provenance.manifest.json)                             |
|  Stage 7: Reconciliation (reconciliation.report.json)                           |
|  Stage 8: Governance     (admission.decision.json)                              |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       GOVERNANCE & ADMISSION CONTROLLER                         |
|         Gates G1–G8 Evaluation · Veto Policy · Evidence Envelope Sealing        |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
+---------------------------------------------------------------------------------+
|                       BOUNDED EXECUTION ADAPTER (QRPE)                          |
|         Semgrep Adapter · Process Isolation · Timeout · Staged Atomic Swap      |
+---------------------------------------------------------------------------------+
```

---

## 2. Six Cooperating Planes

| Plane | Responsibility | Enforceable Output |
|---|---|---|
| **Intent and governance** | Interpret request, validate slug, enforce path containment, resolve authorization mode | `request.normalized.json` |
| **Agent mesh** | Delegate bounded research, configuration inspection, finding challenge, and coverage | Typed `MeshTaskEnvelope` messages |
| **Orchestration** | Schedule dependencies, manage timeouts, process containment, state machine transitions | Monotonic `state_history` |
| **Execution** | Run pinned adapter under isolated runtime, capture stdout, stderr, raw artifacts | `raw/stdout.log`, `raw/stderr.log`, `raw/semgrep.json` |
| **Glassbox verification** | Validate schema, provenance, SHA-256 digests, and finding source attribution | `validation/schema-report.json`, `verification-report.json` |
| **Evidence and audit** | Preserve run artifacts, audit manifests, admission ledger, sealed envelope | `manifest.json`, `evidence_envelope.json` |

---

## 3. The Specialist Agent Mesh

1. **Scope and Repository Agent (`scope-agent`):**
   - *Capability:* `repository.scope.inspect` (Read-only)
   - Resolves git revision, target boundary containment, scannable files, and exclusions.
   - Produces `inputs.inventory.json` and claims scope containment.
2. **Semgrep Configuration Agent (`semgrep-config-agent`):**
   - *Capability:* `semgrep.config.inspect` (Proposal only)
   - Inspects pinned rulesets, language support, exclusions, and computes configuration digest.
   - Produces configuration assessment without authority to modify approved settings silently.
3. **Execution Coordinator (`execution-coordinator`):**
   - *Capability:* `execution.run.broker` (Brokered access)
   - Enforces execution grants (`write_allowed = confirm && !dry_run`), creates run directory, captures stdout/stderr, records execution duration and exit codes.
4. **Finding Verification Agent (`finding-verification-agent`):**
   - *Capability:* `finding.verify.challenge` (Independent review)
   - Challenges candidate findings against physical source code, lines, test fixtures, inline ignore pragmas (`nosec`, `semgrep-ignore`), assigns classifications (`candidate` -> `triaged` -> `independently_verified` / `rejected` / `inconclusive`).
5. **Coverage and Reconciliation Agent (`coverage-reconciliation-agent`):**
   - *Capability:* `coverage.reconcile` (Read-only)
   - Compares requested scope inventory with actual Semgrep scan coverage (`paths.scanned`), flags missing or excluded files, produces coverage ratio and reconciliation report.
6. **Governance and Admission Agent (`governance-admission-agent`):**
   - *Capability:* `governance.admit` (No self-approval)
   - Evaluates gates G1 through G8 and proposes disposition; final admission is adjudicated by `GovernanceGateAdjudicator`.

---

## 4. Glassbox Mirror Plane 8 Stages & Synchronization Barriers

Execution transitions monotonically through eight stages with explicit synchronization barriers:

- **Stage 1 (Perception):** Ingest intent, resolve paths, validate slug containment -> `request.normalized.json`
- *Barrier A (Authorization):* Gate G1 & G2 check scope, permissions, path containment.
- **Stage 2 (Parsing):** Preflight adapter, Python, Semgrep tool, inventory files -> `inputs.inventory.json`
- **Stage 3 (Interpretation):** Bind ToolContract, verify config and compute digest -> `analysis.intermediate.json`
- *Barrier B (Reproducibility):* Gate G5 pins tool version, config digest, source revision.
- **Stage 4 (Planning):** Construct TaskContract, evaluate dry-run vs confirmed mode -> `execution.plan.json`
  - *Dry-run exit:* Preview plan and exit 0 with zero filesystem writes.
- **Stage 5 (Verification Execution):** Brokered execution, process timeouts, capture raw stdout/stderr/JSON.
- *Barrier C (Execution Integrity):* Gate G3 checks process exit codes and diagnostics.
- **Stage 6 (Context Modeling):** Independent read-back SHA-256 verification, schema check, finding attribution -> `provenance.manifest.json`
- *Barrier D (Evidence Integrity):* Gate G4 verifies artifacts, digests, and JSON conformances.
- **Stage 7 (Reconciliation):** Challenge findings against source lines, evaluate scan coverage -> `verification.report.json`, `reconciliation.report.json`
- *Barrier E (Semantic Reconciliation):* Gates G6 & G7 verify coverage and finding challenge results.
- **Stage 8 (Governance):** Evaluate Gate G8, adjudicate admission, seal evidence envelope -> `admission.decision.json`, `manifest.json`, `evidence_envelope.json`.
- *Barrier F (Governance Admission):* Mandatory passage of all gates before `ADMITTED` status.

---

## 5. Acceptance Gates (G1–G8)

| Gate | Name | Required Checks | Proposer | Evaluator |
|---|---|---|---|---|
| **G1** | Authorization | `policy_permitted_scope`, `authorization_mode_valid` | `SCOPE_REPOSITORY_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G2** | Scope integrity | `slug_format_valid`, `path_containment_verified`, `target_exists` | `SCOPE_REPOSITORY_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G3** | Execution integrity | `adapter_clean_exit`, `scanner_clean_exit`, `timeout_clean` | `EXECUTION_COORDINATOR` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G4** | Artifact integrity | `receipt_present`, `report_present`, `digest_verified`, `schema_conformant` | `VALIDATOR` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G5** | Provenance | `tool_version_pinned`, `configuration_digest_recorded`, `source_revision_captured` | `SEMGREP_CONFIG_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G6** | Coverage | `scope_coverage_evaluated`, `discrepancies_disclosed` | `COVERAGE_RECONCILIATION_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G7** | Verification | `findings_challenged`, `classifications_assigned` | `FINDING_VERIFICATION_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |
| **G8** | Governance | `prior_gates_accepted`, `policy_satisfied`, `no_self_approval` | `GOVERNANCE_ADMISSION_AGENT` | `INDEPENDENT_GOVERNANCE_GATE` |

---

## 6. Run Directory Layout

```
bounties/<slug>/scans/semgrep/
├── evidence_envelope.json         # Canonical sealed Pack B envelope for latest run
├── semgrep.json                   # Latest verified scan results
├── receipt.json                   # Latest cryptographic execution receipt
├── latest_run                     # Pointer to current active run directory
└── runs/
    └── <run-id>/
        ├── request.normalized.json
        ├── inputs.inventory.json
        ├── execution.plan.json
        ├── provenance.manifest.json
        ├── verification.report.json
        ├── reconciliation.report.json
        ├── analysis.intermediate.json
        ├── admission.decision.json
        ├── manifest.json
        ├── evidence_envelope.json
        ├── raw/
        │   ├── stdout.log
        │   ├── stderr.log
        │   ├── semgrep.json
        │   └── receipt.json
        ├── validation/
        │   ├── verification-report.json
        │   ├── coverage-report.json
        │   └── reconciliation.report.json
        └── governance/
            └── admission.decision.json
```

---

## 7. Verification Records & Test Coverage

The Semgrep governed agentic mesh is verified via two comprehensive test suites:

- **Python Pytest Suite (`tests/test_semgrep_mesh.py`):**
  - Canonical contracts validation (`TaskContract`, `ToolContract`, `EvidenceContract`, `FindingContract`, `GateDecisionContract`, `MeshTaskEnvelope`).
  - Path containment, slug traversal rejection, and symlink escape checks.
  - Preflight checks and tool registry resolution.
  - Semgrep config agent and configuration digest pinning.
  - Finding verification agent: source line matching, inline ignore annotations (`nosec`, `semgrep-ignore`), mock/test heuristics.
  - Coverage and reconciliation agent: coverage ratios and omitted files.
  - Gate adjudication G1–G8 fail-closed enforcement and no self-approval.
  - Adversarial negative controls (corrupted JSON, digest mismatch, timeout, attribution mismatch).
- **CLI Acceptance Test Suite (`tests/test_workflow_semgrep.sh`):**
  - 18 distinct acceptance scenarios mirroring production requirements.
  - Dry-run zero filesystem writes guarantee.
  - Live execution and atomic staged promotion.
  - Adversarial simulation flags and schema validation.
