# Verification Contract & Glassbox Mirror Plane Protocol

**Version:** 1.0.0  
**Status:** Canonical Reference  
**Applicability:** Pack C Dynamic Verification & Bounded Forge Fuzzing

---

## 1. Overview

The Glassbox Mirror Plane Protocol structures dynamic security evaluations into eight verifiable stages with explicit synchronization barriers:

```
[Stage 1: Perception Filtering]
             ↓
[Stage 2: Parsing & Tokenization]
             ↓
[Stage 3: Preceptive Feature Interpretation]
             ↓
[Stage 4: Thinking & Planning]
             ↓
[Stage 5: Reasoning & Verification]
             ↓
[Stage 6: Context & Scope Modeling]
             ↓
[Stage 7: Awareness & Semantic Interpretation]
             ↓
[Stage 8: Meta-Governance & Executive Authorization]
```

---

## 2. Stage Breakdown & Verification Deliverables

### Stage 1 — Perception Filtering
- Ingestion and containment of requested parameters (`--target`, `--output-dir`, `--confirm`, `--dry-run`).
- Enforces syntax validation and repository-relative path checks.
- Deliverable: Validated parameter set.

### Stage 2 — Parsing & Tokenization
- Verification of repository layout, toolchain availability (`python3`, `forge`).
- Verification of backend adapter presence (`foundry_adapter.py`).
- Deliverable: Tool version strings and capability verification.

### Stage 3 — Preceptive Feature Interpretation
- Extraction of test target filters (`testFuzz_`).
- Resolution of configuration files and target contracts.
- Deliverable: Target inventory and filter definition.

### Stage 4 — Thinking & Planning
- Bounded task formulation with resource limits (timeout: 120s, memory: container defaults).
- Deliverable: Task Contract (`task_contract.schema.json`).

### Stage 5 — Reasoning & Verification
- Execution of bounded fuzz test suite via Foundry adapter.
- In dry-run mode: generates command preview and tool diagnostics.
- In confirmed mode: executes subprocess under timeout and captures exit status.
- Deliverable: Raw stdout and stderr streams.

### Stage 6 — Context & Scope Modeling
- Binding execution logs to Git commit revision and repository state.
- Calculation of cryptographic SHA-256 digests for all generated logs (`stdout.log`, `stderr.log`).
- Deliverable: Pinned artifact digests.

### Stage 7 — Awareness & Semantic Interpretation
- Extraction and reconciliation of test outcome:
  - Total tests executed vs filtered.
  - Failures, reverts, or counterexamples observed.
  - Contradiction and limitation detection.
- Deliverable: Reconciled test outcome record.

### Stage 8 — Meta-Governance & Executive Authorization
- Evaluation of mandatory acceptance criteria:
  - Did the process exit 0?
  - Were all intended fuzz tests executed?
  - Is `receipt.json` present, schema-valid, and internally consistent?
- Terminal outcome assignment: `COMPLETED_VERIFIED`, `COMPLETED_WITH_LIMITATIONS`, `BLOCKED`, or `FAILED`.
- Atomic publication of `receipt.json`.
- Deliverable: Gate Decision Contract & Audit Event.
