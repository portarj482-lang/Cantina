---
id: rule-universal-skill-adaptation
name: Universal Architecture-Aware Skill Adaptation
category: governance
severity: mandatory
---

# Universal Architecture-Aware Skill Adaptation

## 1. Core Mandate
Every skill, oracle, agent, and workflow MUST resolve and validate its active target context before performing target-dependent analysis or execution.
- No skill may depend on an implicit bounty, repository path, contract filename, programming language, runtime, or previous chat session unless that dependency is explicitly declared and validated.
- Repository discovery MUST support heterogeneous layouts. The absence of `bounties/<slug>/` MUST NOT be interpreted as evidence that the target is invalid.

## 2. Context Resolution and Scope Boundaries
Context resolution MUST prioritize:
1. Explicit, validated invocation arguments and execution context.
2. Authoritative session selection locked at start.
3. Validated environment configuration (`CANTINA_TARGET_ROOT`, `CANTINA_BOUNTY`, `CANTINA_ARCHITECTURE`).
4. Authoritative adapter-based workspace discovery.
5. Session-local state (`MEMORY.md`) as supporting evidence, not unquestioned authority.

Ambiguous, conflicting, invalid, or missing mandatory context MUST produce a structured blocked result (`BLOCKED: MISSING_CONTEXT`) rather than an assumed target.
The resolved target MUST remain within the authorized repository and bounty scope. Discovery MUST NOT silently expand the audit scope.

## 3. Architecture-Aware Specialization
Every security skill MUST decouple and distinguish:
- **Universal Security Invariant**: Protocol-agnostic property, assumptions, preconditions, permitted transitions, violation conditions, and required evidence.
- **Architecture Specialization**: How the property maps to concrete execution semantics (EVM callers/storage slots, Solana signers/PDAs/account ownership, Move capabilities, CosmWasm messages).
- **Target Implementation Binding**: Actual source files, entry points, storage fields, test commands, and scope manifest applicable to the current target.

Architecture-specific checks MUST NOT run when their required semantics, prerequisites, or capabilities are absent. Unsupported checks MUST be reported as `NOT_APPLICABLE` or `NOT_VERIFIED`, never falsely reported as passed.

## 4. Evidence and Reporting Standards
A security finding MUST identify the relevant target, affected implementation artifact, violated property, assumptions, reproducible evidence, and applicable impact.
A successful shell command or test exit code 0 MUST NOT by itself establish that an invariant holds.
The framework MUST strictly distinguish:
- `PASS`: The check completed and required evidence supports the property within declared assumptions.
- `FAIL`: The check established a violation or reproduced a qualifying failure.
- `BLOCKED`: A mandatory prerequisite, context, permission, or dependency prevented execution.
- `NOT_APPLICABLE`: The check was determined to be irrelevant to the verified target architecture or implementation.
- `NOT_VERIFIED`: The check could not establish the property, including cases with insufficient evidence or unsupported tooling.

Missing evidence MUST NOT be interpreted as proof of security.

## 5. Isolation and Execution Safety
- Concurrent sessions MUST maintain independent target selections, temporary files, hypotheses, logs, and execution metadata.
- Session state MUST NOT be used to infer another session's active target.
- All filesystem writes and external execution MUST respect declared permissions and workspace boundaries.
- Credentials and private keys MUST NOT be written to audit logs, hypotheses, or persistent files.
- Cleanup MUST be performed for temporary processes, forked nodes, and test resources, with teardown failures reported explicitly.

## 6. Extensibility and Compliance
- New architectures MUST be integrated through validated adapter capabilities, architecture-specific profiles, and compatible verification procedures without rewriting universal invariant definitions.
- All skills MUST pass automated schema, coupling, context, isolation, applicability, and evidence-policy tests.
- A skill MUST NOT be declared universally adaptive solely because hardcoded paths have been removed.
