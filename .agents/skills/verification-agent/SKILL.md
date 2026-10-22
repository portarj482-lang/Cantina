---
name: verification-agent
description: >-
  Sub Goal #9 — Verification Agent & Independent Gate. Provides deterministic test execution harnesses,
  adversarial negative controls, SHA-256 artifact digest calculation, and evidence tracking
  under the 5-state result taxonomy (PASS, FAIL, BLOCKED, NOT_APPLICABLE, NOT_VERIFIED).
---

# Verification Agent Skill (USAP Architecture)

## Overview
The Verification Agent Skill establishes deterministic proof of system behavior. It acts as an independent verification gate for all domain invariant oracles and governance workflows, pairing positive test executions with adversarial negative controls and registering cryptographic evidence in the canonical `EvidenceStore`.

---

## 5-State Result Model & Evidence Standards

| Status | Meaning | Required Evidence Standard |
|---|---|---|
| `PASS` | Property definitively held within verified assumptions | Test execution trace, passing forge/anchor output, or mathematical invariant proof digest |
| `FAIL` | Violation detected or adversarial attack succeeded | Reproducible counterexample, falsification log, or breached assertion transcript |
| `BLOCKED` | Prerequisite, manifest, permission, or scope missing | Canonical blocker classification (`MISSING_CONTEXT`, `PERMISSION_DENIED`, etc.) |
| `NOT_APPLICABLE` | Invariant irrelevant to the target architecture | Target capability matrix proving absence of relevant surface |
| `NOT_VERIFIED` | Analysis incomplete or tooling unavailable | Documented gap analysis detailing missing toolchain or unresolved symbolic constraint |

---

## Capabilities & Workflows
- **Deterministic Harness**: Runs unit and fuzz tests with output capture, timeout guards, and isolation.
- **Cryptographic Fingerprinting**: Computes SHA-256 digests for all generated artifacts, manifests, and negative control execution matrices.
- **Independent Challenger Gates**: Asserts falsification controls (e.g. verifying that corrupting an artifact digest creates divergence, and that early withdrawal or tampered attestation reverts).
- **Audit Verification Gate**: Reconciles evidence references across all stage handoffs, preventing unbacked assertions from passing as verified.
