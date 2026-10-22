---
id: rule-evidence-provenance-integrity
name: Evidence Provenance, Integrity, and Verification Standards
category: evidence
severity: mandatory
---

# Evidence Provenance, Integrity, and Verification Standards

## 1. Explicit Evidence Classification

All claims, findings, and analysis records must distinguish:
- **OBSERVED:** Directly seen in source code, logs, or reproducible execution on disk.
- **DERIVED:** Inferred from identified observations through explicit, documented rationale.
- **HYPOTHESIS:** Plausible, testable assertion not yet confirmed by deterministic test.
- **UNVERIFIED:** Evidence is incomplete, unpinned, or relies on assumptions.
- **REFUTED:** Contradicted under stated reproduction or falsification conditions.
- **SUPERSEDED:** Replaced by newer verified evidence; historical record preserved.

Confidence follows evidence quality, not agent assertiveness or consensus.

## 2. Cryptographic Provenance and Artifact Tracking

1. Every physical artifact referenced in claims or findings must have an immutable cryptographic hash (SHA-256).
2. Provenance tags must adhere to canonical formats:
   - `[SRC: path:line @commit]` for repository source pinned to a git commit.
   - `[CORPUS: dataset/entry @version]` for imported vulnerability datasets.
   - `[LOCAL: path:line, provenance unpinned]` for uncommitted or generated local files.
   - `[UNKNOWN]` when provenance cannot be verified.
3. Content hashes establish identity, not semantic truth. A valid SHA-256 does not prove an exploit is viable.

## 3. Independent Challenge and Falsification

1. Security-critical and architectural claims must undergo independent review by an adversarial reviewer or challenger agent.
2. The challenger must attempt to find counterexamples, test falsification preconditions, and run negative controls.
3. A single failing negative control refutes the claim until resolved.

## 4. Rollback and Recovery Prerequisites

1. No adaptation or release may be promoted to production without a documented, verified rollback mechanism.
2. In the event of health-check regression, state corruption, or verification failure, the system must trigger reversible rollback.
3. Historical audit records, blocked attempts, and failed test logs must never be expunged.
