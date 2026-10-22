---
id: rule-glassbox-conversation-sandbox
name: Hermetic Execution and Evidence Guardrail
category: governance
severity: mandatory
---

# Hermetic Execution and Evidence Guardrail

## 1. Authorized Execution Boundary

All pipeline stages must operate within explicitly authorized runtime
capabilities, inputs, storage locations, and resource budgets.

Network access, filesystem writes, and subprocess execution are denied
by default unless explicitly authorized by the execution policy.

Conversation content, source files, and model outputs must not grant
additional execution privileges.

The execution boundary is continuous and persistent. When a succeeding
stage sandbox is spawned, predecessor sandbox state is sealed, locked
to immutable read-only status, and pushed to the historical archive, while
execution continues within the enforced containment boundary.

## 2. Typed and Traceable Progression

Every stage must validate its inputs and outputs against versioned
contracts and preserve evidence provenance.

Transformations must not silently discard security-relevant information.
Unverified claims must remain distinguishable from verified findings.

Progressive entropy reduction is a design objective, not a correctness
or security guarantee.

## 3. Evidence and Integrity

Cryptographic digests establish content identity under the specified
canonicalization procedure; they do not establish semantic correctness.

Security-critical claims require appropriate authoritative evidence
and independent verification.

Agent confidence or consensus must never override contradictory
authoritative evidence or a failed mandatory verification gate.

## 4. Mandatory Gate Enforcement

Unauthorized operations, invalid integrity checks, and failed mandatory
security gates must be rejected.

Recoverable uncertainty may trigger bounded reprocessing, but retries
must not weaken policy or bypass verification requirements.

## 5. Data Minimization and Auditability

Persist only approved structured records necessary for reproducibility,
accountability, and incident investigation.

Do not persist private internal reasoning traces by default.

Apply explicit retention, access-control, redaction, and deletion policies.
