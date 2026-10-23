# Build status — Antigravity Security Mesh v0.1.0

## Implemented in this foundation

- 49 typed agent capability profiles with EVM/Solana separation and candidate skill trust state.
- TypeScript/Fastify API scaffolding, input validation, authentication token separation, PostgreSQL migration, audit events, and workflow state transitions.
- Scope registration with exact repository/commit/chain/block/address/method matching. No real target scope is preloaded.
- Source-manifest generation and validation, content-addressed artifact storage, evidence annotations, and deterministic receipt checks for source/suite/runner identity, production Ed25519 signatures (development HMAC), assertion IDs, and artifact bytes.
- Durable task queue with idempotency, dependency checks, leases, bounded retries, and Scout → pattern-scan → Strategist handlers.
- Shared versioned layer registry with parent Oracle, entry requirements, assigned agents, contracts, authority boundaries, runtime modes, validation, and authenticated `GET /v1/layers`; source, analysis, fixed-profile execution, evidence, review, and reporting layers are active through their existing API/runner paths.
- Web host scope registration; passive HTTPS header and email MX/SPF/DMARC checks; Solidity AST graph builder; persisted labeled benchmark metrics.
- Polling isolated runner fetches approved commits and runs fixed offline Foundry build/baseline or Slither profiles with per-runner tokens, lease renewal, Ed25519 receipts, and no-network containers.
- Exact target PoCs and fork/RPC suites remain disabled pending approved targets, reviewed harnesses, and a restricted RPC gateway.
- F-001 verification plan with explicit support/falsification criteria, baseline, same-digest/same-signature comparison, and patched negative control.
- Corrected `revocation` positive-test oracle: it requires observation that the same signature still validates after revocation. The patched negative control separately requires post-revocation rejection.
- G1 remains inconclusive after source-manifest hashing alone. A separate human-reviewed source-attestation record is required to pass G1.
- Report drafting and human authorization records are local only; no Cantina submission is performed.

## Checks completed in this environment

- `npm run typecheck`: **passed** (0 errors against strict TypeScript configuration and installed dependency types).
- `npm test`: **passed** (73 passed, 3 integration tests skipped as expected without `TEST_DATABASE_URL`).
- `npm run build`: **passed** (clean compile of `src/` to `dist/`).
- `npm run smoke`: **passed** (11/11 offline security checks passed using `scripts/ts-loader.mjs` with `--experimental-strip-types`):
  - `agent-registry-49`
  - `solana-disabled-for-evm`
  - `scope-match-fail-closed`
  - `source-attestation-binding`
  - `state-machine`
  - `revocation-positive-oracle`
  - `signed-receipt`
  - `tamper-detection`
  - `target-record-validation`
  - `target-revocation-fail-closed`
  - `evidence-preservation`
- `npm run test:integration`: **passed** runner check (gracefully skips 3 tests when `TEST_DATABASE_URL` is unset).
- `node --check runner/run.mjs` and `node --check runner/worker.mjs`: passed syntax checks.
- Synthetic vault reference workflow: 15-step verified lifecycle test passing in `tests/reference-workflow.test.ts`.
- Migration ledger: transactional migrations, SHA-256 drift detection, and rollback verified in `tests/migrate.test.ts`.
- RBAC separation of duties: 11 security tests passing in `tests/auth-roles.test.ts`.
- Controlled provenance: 8 tests passing in `tests/provenance.test.ts`.

## Checks requiring external services

- PostgreSQL database integration test suite (`tests/database.integration.test.ts`): Requires live PostgreSQL instance with `TEST_DATABASE_URL` configured. Verified to skip gracefully when unconfigured, with complete negative test coverage written for:
  - Expired target records fail closed
  - Out-of-scope address rejection
  - Runner lease registration and claim
  - Forged receipt signature rejection
  - Content-addressed artifact tampering rejection
  - Append-only audit log immutability (UPDATE and DELETE queries fail closed)
- Target-specific live EVM PoC harnesses and restricted RPC gateway: Disabled by design until an authorized smart-contract scope and reviewed harness are registered.
- Cantina connector: Not implemented; human authorization is recorded locally with no external automated submission.

## Next engineering milestone

Supply and review target-specific PoC harnesses and a restricted RPC gateway for an explicitly authorized smart-contract scope; connect runner-generated AST/provenance directly into the analysis pipeline; then run PostgreSQL integration and the full build/tests with Fastify and database services installed. Do not dispatch fork tests without independently validated scope and harnesses.
