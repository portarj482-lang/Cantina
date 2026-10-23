# Antigravity Security Mesh — Foundation Roadmap & Capability Inventory

**Version:** 0.1.0\
**Status:** ACTIVE\
**Last Updated:** 2026-10-19\
**Scope:** Internal Security Research & Verification Platform (`security-mesh/security-mesh`)

---

## 1. Executive Summary & Project Positioning

Antigravity Security Mesh is an **evidence-first, fail-closed security research and verification platform**. It is designed to evaluate smart contract and decentralized system hypotheses through deterministic controls, isolated execution, content-addressed artifacts, cryptographic receipts, and strict separation of human duties.

### Core Truthfulness Standard
- The platform provides **49 governed capability profiles**, not 49 autonomous AI agents.
- No AI or model has tool-execution authority, scope-granting authority, evidence-verification authority, or submission authority.
- No target is authorized by default; every target-specific action requires an explicit, verified scope and target record.
- Arbitrary shell commands, live network probes, exploit transactions, and automated external submissions are **strictly disabled**.

---

## 2. Current Capability Inventory

| Capability | Status | Implementation Details / Limitations |
|---|---|---|
| **Fail-Closed Scope Registry** | **Implemented** | `POST /v1/scopes`, repo/commit/chain/block/methods/addresses matching; zero scopes by default. |
| **Oracle Target Records** | **Implemented** | `POST /v1/target-records`, binding run to scope snapshot `scopeSha256`, target address, pins, methods, suites, expiry. |
| **49 Capability Profiles** | **Profiled** | 49 structured profiles across EVM and Solana cohorts in `src/agents/registry.ts`. Solana is disabled for EVM workflows. |
| **Task Queue & Leases** | **Implemented** | Leased task queue with bounded retries, task dependencies, and worker execution (`src/orchestration/`). |
| **Isolated Docker Runner** | **Implemented** | Pinned digest container, network=none, read-only root, dropped capabilities, no symlinks/submodules, Ed25519 signed receipts (`runner/run.mjs`). |
| **Fixed Suite Allowlist** | **Implemented** | Fixed profiles: `build`, `baseline-tests`, `slither`. Target-specific PoC suites remain disabled. |
| **Content-Addressed Artifacts** | **Implemented** | SHA-256 content verification, size bounds (10 MB max), storage key generation (`src/evidence/artifacts.ts`). |
| **Deterministic Receipt Verification** | **Implemented** | Verification of runner identity, Ed25519 signature, exit code, assertion IDs, artifact hashes, and timing (`src/evidence/receipt.ts`). |
| **Readiness Gates (G1–G9)** | **Implemented** | Deterministic gate rules enforcing source attestation, reproduction, duplicate checks, severity rubric, provenance (`src/evidence/gates.ts`). |
| **Append-Only Audit Hash Chain** | **Implemented** | PostgreSQL trigger prevents updates/deletes; SHA-256 hash chaining over entries (`src/security/audit-chain.ts`). |
| **Passive Web/Email Scopes** | **Implemented** | Scoped public DNS MX/SPF/DMARC and single HTTPS `HEAD /` checks; no crawling or exploitation (`src/network/`). |
| **Advisory Gemini Adapter** | **Implemented** | Structured hypothesis generation without function tools or execution access (`src/providers/gemini.ts`). |
| **Source Manifest Intake** | **Partial** | Validates schema, commit binding, and tree digest; G1 remains inconclusive without human source attestation. |
| **In-Process AST Analysis** | **Partial** | Scout and pattern-scan operate on caller-supplied AST/sources; labeled provisional because source is not runner-fetched. |
| **Human Identity & RBAC** | **Partial** | Current `x-actor-id` is an audit label without cryptographic token authentication or fine-grained role enforcement. |
| **Database Migration Tracking** | **Partial** | Replays migrations sequentially without a persistent `_migrations` tracking table or checksum verification. |
| **PostgreSQL Integration Tests** | **Partial** | Test exists (`tests/database.integration.test.ts`) but requires manual `TEST_DATABASE_URL` environment variable. |
| **Target-Specific PoC Suites** | **Disabled** | Fork/RPC suites disabled until authorized target, reviewed harness, and restricted RPC gateway exist. |
| **External Submission Connector** | **Disabled** | Human submission authorization is local-only; external Cantina submission is intentionally disabled. |
| **Arbitrary Command Execution** | **Disabled** | Strictly prohibited across all endpoints and runner configurations. |

---

## 3. Explicit Security Invariants

All future developments must preserve these non-negotiable invariants:

1. **Zero Default Authorization (Fail-Closed):** No execution, analysis, or workflow can proceed without matching an unexpired, active scope and target record.
2. **Deterministic Inputs Only:** API callers and task runners can select only allowlisted, immutable suite IDs (`build`, `baseline-tests`, `slither`). Never accept raw shell commands, script fragments, or arbitrary URLs.
3. **Model Non-Authority:** Models (LLMs) cannot execute tools, modify scopes, approve evidence, advance gate states, or authorize submissions. AI output is advisory and treated as unverified candidate hypotheses.
4. **Separation of Duties:**
   - A researcher cannot approve their own finding.
   - An approver cannot approve without independently verified evidence and passed gates.
   - A runner cannot create scopes or human approvals.
   - An administrator cannot silently impersonate reviewers or approvers.
5. **No Live-Funds / Remote Exploitation:** All dynamic testing must execute on pinned, isolated local containers or verified mock forks. Never transmit transactions to live mainnet contracts or public RPCs.
6. **Immutable Audit Chain:** Privileged actions generate append-only audit entries bound by SHA-256 cryptographic chaining. Database mutations or deletions are rejected by triggers.
7. **Artifact and Receipt Integrity:** Execution outcomes are valid only when backed by signed receipts matching the registered runner key and content-hashed artifact bytes.

---

## 4. Prioritized Engineering Backlog

### Priority P0 — Reliability & Safe Foundation (Immediate)

#### P0.1: Database Migration Ledger (`_migrations`)
- **Problem:** `src/db/migrate.ts` executes static SQL files without tracking applied state or validating checksums.
- **Acceptance Criteria:**
  - Create table `_migrations (id VARCHAR(255) PRIMARY KEY, checksum VARCHAR(64) NOT NULL, applied_at TIMESTAMPTZ NOT NULL)`.
  - Compute SHA-256 checksum of each migration file before application.
  - Fail closed if an already-applied migration has a modified checksum (drift detection).
  - Wrap migrations in transactions where PostgreSQL allows.
  - Test fresh setup, idempotent re-run, and tamper/drift rejection.

#### P0.2: Automated PostgreSQL Integration Test Environment
- **Problem:** `tests/database.integration.test.ts` is skipped by default unless `TEST_DATABASE_URL` is set manually.
- **Acceptance Criteria:**
  - Provide a safe local test configuration (e.g., automated test harness or local Docker container script).
  - Verify complete lifecycle: scope registration -> target record -> workflow -> runner lease -> audit chain.
  - Add negative integration tests for expired target records, forged receipts, and audit tampering.
  - Document exact local and CI instructions for running integration tests.

#### P0.3: Authenticated RBAC & Human Identity
- **Problem:** `x-actor-id` is an unverified caller-supplied header.
- **Acceptance Criteria:**
  - Define structured roles: `researcher`, `reviewer`, `approver`, `admin`, `runner`.
  - Validate bearer tokens against configured role keys or authenticated identity records.
  - Enforce separation of duties: researcher != reviewer for finding decisions; approver != researcher.
  - Bind authenticated principal, assigned role, and correlation ID to all audit entries.
  - Add comprehensive unit tests verifying authorized access and denying unauthorized transitions.

#### P0.4: Controlled Source Acquisition & Compiler Provenance Pipeline
- **Problem:** In-process AST analysis currently trusts caller-supplied AST/sources without runner provenance.
- **Acceptance Criteria:**
  - Define `ControlledSourceRecord` (repo URL, commit SHA, tree digest, git archive hash, fetch timestamp).
  - Define `CompilerProvenanceRecord` (compiler image digest, solc version, settings hash, AST digest).
  - Require analysis admission checks: source-attested status requires matching records; caller-supplied inputs remain marked `provisional`.
  - Define normalized `FindingLead` schema with stable ID, commit binding, source span, detector rule, and falsification criteria.

#### P0.5: End-to-End Synthetic Reference Workflow (Phase 4)
- **Problem:** Need a complete vertical reference proving all components work in harmony on a safe fixture.
- **Acceptance Criteria:**
  - Create synthetic Solidity test fixture in `cases/synthetic-vault/`.
  - Execute full lifecycle: scope registration -> target record -> source manifest -> compiler provenance -> pattern lead -> falsifiable hypothesis -> baseline test -> positive reproduction -> patched negative control -> signed receipt -> evidence gates G1-G9 -> independent review -> human approval -> draft report.
  - Verify that missing negative controls or forged receipts fail closed.
  - Document reference walkthrough in `docs/REFERENCE_WORKFLOW.md`.

---

### Priority P1 — Operational Hardening & Observability

#### P1.1: API Protection & Operational Endpoints
- Request body size limits (reject payloads > 10 MB).
- Structured, non-sensitive error responses (RFC 7807 compliant error codes; no stack traces or file paths).
- `/healthz` (liveness) and `/readyz` (database connectivity & queue readiness) endpoints.
- Request correlation IDs (`x-request-id`) logged across all operations and audit events.
- Audit-chain export endpoint (`GET /v1/audit/export`) producing signed chain-head summaries.

#### P1.2: Operations & Threat Model Documentation
- Create `docs/OPERATIONS.md`: runner key lifecycle, token rotation, backup & restore procedures, disaster recovery.
- Create `docs/THREAT_MODEL.md`: trust boundaries, attacker profiles, mitigation matrix, residual risks.

#### P1.3: Continuous Integration (CI) Baseline
- GitHub Actions workflow (`.github/workflows/ci.yml`) automating:
  - `npm run typecheck`
  - `npm test`
  - `npm run smoke`
  - `npm run test:integration` (with ephemeral PostgreSQL service)
  - Dependency audit and secret scanning.

---

### Priority P2 — Advanced Verification & Extensions (Future Phases)

- **P2.1 Restricted RPC Gateway:** Rate-limited, method-restricted JSON-RPC proxy for pinned fork testing.
- **P2.2 External Tool Adapters:** Hardened container definitions for Slither, Aderyn, Echidna, Medusa, Halmos.
- **P2.3 OIDC/SSO Identity Provider:** Enterprise SSO integration for human researcher/reviewer authentication.
- **P2.4 External Cantina Connector:** Controlled API bridge for submission once human approval is sealed.

---

## 5. Readiness Definitions

### Definition: Production-Ready Internal Use
A deployment tier is considered **production-ready for internal use** when:
1. All database migrations are tracked via `_migrations` with cryptographic checksum verification.
2. All API endpoints require authenticated tokens and enforce strict RBAC roles.
3. Separation of duties is cryptographically and logically enforced (no self-approval).
4. All privileged actions append to an untamperable, verified audit hash chain.
5. All executions occur within isolated, network-disabled containers pinned by image digest.
6. The test suite passes 100% of unit, smoke, and real PostgreSQL integration tests.
7. Operations and threat models are documented, with tested backup/recovery procedures.

### Definition: Authorized Target-Specific Verification Ready
A specific target workflow is considered **ready for target-specific verification** when:
1. An official, verified scope entry is registered with immutable repository, commit, chain ID, fork block, and addresses.
2. An Oracle Target Record binds the run to that exact scope snapshot and allowlisted suite.
3. An independent source-attestation artifact confirms commit object and repository identity.
4. A reviewed test harness with explicit baseline, positive, and patched negative controls is compiled.
5. Execution occurs in an offline or restricted-gateway container producing signed Ed25519 receipts.
6. A distinct human reviewer independently validates evidence against G1–G9 gates.
7. External submission is held until an explicit human approval token is recorded.
