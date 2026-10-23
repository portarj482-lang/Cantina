# Antigravity Security Mesh — Reference Verification Workflow

**Version:** 0.1.0\
**Target:** Synthetic Solidity Fixture (`cases/synthetic-vault/SyntheticVault.sol`)\
**Status:** VERIFIED (Offline / Local Test Harness)

---

## 1. Overview & Objective

This document details the **end-to-end reference verification workflow** of the Antigravity Security Mesh platform using a synthetic, locally contained smart contract fixture (`SyntheticVault.sol`).

The purpose of this reference workflow is to prove the integrity of the platform's 15-step evidence-first lifecycle:
from synthetic scope registration, target-record binding, and controlled source acquisition, through to independent review, human approval, and draft report generation—without touching live mainnet contracts or public RPCs.

---

## 2. The 15-Step Reference Lifecycle

```
[1. Scope Registration] ──> [2. Target Record Binding] ──> [3. Controlled Source Manifest]
           │
           ▼
[4. Compiler Provenance] ──> [5. Deterministic Lead] ──> [6. Falsifiable Hypothesis]
           │
           ▼
[7. Baseline Test] ──> [8. Positive Reproduction] ──> [9. Patched Negative Control]
           │
           ▼
[10. Signed Receipt] ──> [11. Evidence Annotations & G1-G9] ──> [12. Independent Review]
           │
           ▼
[13. Human Approval] ──> [14. Draft Report Generation] ──> [15. Held Local (No Submission)]
```

### Step 1: Synthetic Scope Registration
- Scope registered via `POST /v1/scopes` with explicit repository, commit (`1111111111111111111111111111111111111111`), chain ID (`31337`), and allowed method (`local-test`).
- Registration records metadata; zero scopes exist by default.

### Step 2: Target-Record Binding
- Created via `POST /v1/target-records`, calculating and storing the exact canonical `scopeSha256` snapshot.
- Binds all subsequent tasks, runs, and artifacts to this single immutable target record.

### Step 3: Controlled Source Manifest
- Clean checkout of the repository at the pinned commit.
- Tracks files (`SyntheticVault.sol`, `SyntheticVaultPatched.sol`, `SyntheticVaultTest.sol`) and computes deterministic SHA-256 tree digest.
- Validated via `ControlledSourceRecord`.

### Step 4: Compiler & AST Provenance
- Compiled using a digest-pinned container image (`ethereum/solc@sha256:...`).
- `CompilerProvenanceRecord` captures compiler settings hash, AST digest, and output artifact hashes.

### Step 5: Deterministic Analysis Lead
- Pattern scanner detects low-level call pattern in `withdraw()`:
  ```solidity
  (bool success, ) = msg.sender.call{value: amount}("");
  shares[msg.sender] -= amount;
  ```
- Normalizes lead into `FindingLead` with exact line spans and excerpt SHA-256 hash.

### Step 6: Falsifiable Hypothesis
- Hypothesis stated: *"withdraw() transfers funds prior to decrementing internal share balance, enabling reentrant exploitation."*
- Confirmation criteria: Reentrant attacker drains more funds than deposited.
- Falsification criteria: Patched contract adhering to CEI and reentrancy guard rejects the exploit.

### Step 7: Baseline Test
- Executes `test_baseline_deposit_and_withdraw()`.
- Verifies normal expected protocol operation holds under benign conditions.

### Step 8: Positive Reproduction Test
- Executes `test_positive_reproduction_reentrancy_exploit()`.
- Observes the attack count > 0 and asset conservation invariant violated.

### Step 9: Patched Negative-Control Test
- Executes `test_negative_control_patched_vault_reverts()` against `SyntheticVaultPatched.sol`.
- Proves that the exact same reentrancy call is rejected by the patched contract.
- *Rule: A positive test without a passing negative control cannot qualify for evidence support.*

### Step 10: Signed Receipt and Hashed Artifacts
- The isolated runner executes the test suite in a container with `network=none` and dropped capabilities.
- Produces `run-*.log` content-addressed artifact and signs the execution receipt using Ed25519.
- Verified by the platform's deterministic receipt checker.

### Step 11: Evidence Annotations & Readiness Gates (G1–G9)
- Source attestation evidence, execution receipts, and duplicate checks uploaded.
- Gates G1–G6 evaluated as `passed`; G7 (symbolic) evaluated as `not_applicable` with recorded reason.

### Step 12: Independent Review
- Evaluated by a distinct identity (`reviewer:bob`), not the original researcher (`researcher:alice`).
- Separation of duties strictly enforced: self-review is rejected.

### Step 13: Human Approval Record
- Evaluated by an authorized approver (`approver:carol`).
- Confirms all gates passed and verified evidence is complete.
- Researcher self-approval is rejected.

### Step 14: Draft Report Generation
- Markdown report draft created citing only verified evidence IDs, exact source spans, and explicit limitations.

### Step 15: External Submission Held (No Submission)
- The platform records the submission authorization decision locally.
- No external HTTP request or Cantina API call is dispatched.

---

## 3. Verified Security Invariants in Reference Test

| Invariant | Test Evidence |
|---|---|
| **Separation of Duties** | `tests/reference-workflow.test.ts`: Researcher cannot review or approve own finding. |
| **Receipt Integrity** | `tests/reference-workflow.test.ts`: Forged Ed25519 signature is rejected. |
| **Source Span Integrity** | `tests/reference-workflow.test.ts`: Tampered source excerpt hash fails admission. |
| **Negative Control Requirement** | `tests/reference-workflow.test.ts`: Negative control verified before gate qualification. |
