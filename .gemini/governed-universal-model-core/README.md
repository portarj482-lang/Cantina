# Governed Universal Modeling Core (GUMC) + Cognitive Perception Intelligence (CPI)

Reference scaffold for a governed, extensible model system. This project combines a basic GUMC registry/policy workflow with a conservative CPI layer and a security-analysis bridge interface.

## Included in this revision

- **CPI perception:** records explicitly supplied facts and unknowns without inventing observations.
- **Semantic interpretation baseline:** summarizes supplied metadata, tracks assumptions/questions, and does not pretend a parser or LLM inference is proof.
- **Compatibility assessment:** compares declared invariant identifiers and explicitly reports `exact-proven`, `conditional`, `lossy`, or `unknown` reversibility. The code never proves reversibility by itself.
- **Operational metacognition:** checks whether capabilities, limitations, permissions, policy version, verification time, and evidence are declared.
- **Security Mesh bridge:** proposes hypothesis-only smart-contract authorization invariants from supplied metadata. It does not parse Solidity or confirm vulnerabilities.
- **Controlled adaptation interface:** only applies a request to an isolated sandbox when policy allows it, tests and invariant checks pass, and a separate approval matches the request and artifact digest. No live execution interface is provided.
- **GUMC governance:** existing model registry, proposal evaluation, risk gates, and audit scaffold.

## Operating stages

1. **Advisory-only (default):** observe, interpret, compare, propose, and request evidence. No transformation is executed.
2. **Sandboxed adaptation (opt-in):** an external sandbox adapter may apply a low/moderate-risk change only after independent approval, digest matching, tests, invariant checks, and expiry checks.
3. **High/critical-risk changes:** deliberately blocked from this sample sandbox adapter and require a separate reviewed workflow.

## Run

Requires Node.js 22.16.0 or newer and npm 10 or newer. The project pins the
CI runtime in `.nvmrc`; when using nvm, run `nvm use` before installing or
testing.

```bash
nvm use
npm install
npm run typecheck
npm test
npm run demo
```

## Scope boundaries and production gaps

This is a prototype scaffold, not a complete universal modeling system or a production security product. It has no actual Solidity parser, Foundry runner, RPC integration, Gemini integration, authenticated identity provider, cryptographic approval verification, PostgreSQL persistence, durable tamper-evident audit log, or deployed sandbox. The `signatureRef` field is provenance metadata only; production must cryptographically verify approvals. Registry approval is not yet protected by a separate authenticated governance service. Policy keyword matching is not an ethical classifier. Human review and deterministic verification remain necessary.

For Antigravity Security Mesh, connect this through a narrow, typed adapter and preserve the platform's own allowlisted-suite execution, source pinning, independent evidence gate, and human authorization. Do not wire CPI directly to arbitrary shell commands or unrestricted tool dispatch.


## Temporal Interoperability Layer (v0.3 addition)

See `TEMPORAL_LAYER.md` and `src/temporal/` for typed temporal values, explicit mapping contracts, validation, fail-closed conversion decisions, and tests. The layer distinguishes UTC instants, monotonic durations, logical clocks, event/processing time, simulation time, model versions, and transaction time. It does not infer conversions between incompatible time bases.


## Extended expansion v0.4.0

This expansion adds:
- **Temporal mapping registry** with explicit, reviewed mapping records.
- **Lamport logical clock** for causal ordering; it is not elapsed time.
- **Simulation clock** with isolated advance/rewind operations.
- **Hash-linked audit demonstration** for detecting accidental edits to the in-memory chain.
- **Computational Complexity Intelligence (CCI)** for conservative solver planning from supplied complexity assessments, including hard budgets and independent verification requirements.
- **Expansion tests** for clock semantics, mapping registration, audit-chain integrity, and CCI decisions.

### Run
```bash
npm install
npm run typecheck
npm test
npm run demo:temporal
```

### Important limitations
CCI does not solve P vs. NP, prove complexity classes, or infer formal complexity from timing. Its labels are supplied assessments and must be supported by reviewed theorems/reductions. The audit chain is in-memory and cannot resist a privileged attacker rewriting the full chain. Mapping registration is not a production approval workflow. The simulation clock is not connected to production time or external effects. No physical time travel is implemented.
