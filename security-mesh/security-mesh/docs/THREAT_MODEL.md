# Antigravity Security Mesh — Threat Model

**Version:** 0.1.0\
**Status:** ACTIVE\
**Methodology:** STRIDE / Asset-Centric Threat Analysis

---

## 1. System Assets & Security Boundaries

### Protected Assets
1. **Scope & Target Authorization Records:** Prevents unauthorized scanning or testing against unapproved targets or methods.
2. **Execution Runner Environment:** Pinned Docker containers where untrusted code or analysis scripts execute.
3. **Evidence Artifacts & Receipts:** Signed proofs of test outcomes, code spans, and baseline/negative control results.
4. **Append-Only Audit Trail:** Cryptographically chained log of all privileged security decisions and actions.
5. **Human Approval Authority:** Separation between researcher, reviewer, and final approver.

### Trust Boundaries
- **External Caller ↔ Fastify API:** Authenticated via bearer tokens (`API_TOKEN`, `ADMIN_API_TOKEN`, `HUMAN_APPROVAL_TOKEN`).
- **Fastify API ↔ PostgreSQL Database:** SQL interface protected by triggers and schema constraints.
- **Fastify API ↔ Isolated Runner:** Hardened boundary; runners use lease tokens, per-runner credentials, and Ed25519 signatures.
- **Runner Host ↔ Workload Container:** Workload containers run with `network=none`, `read-only` root filesystem, dropped capabilities, no Docker socket access.

---

## 2. Threat Actor Profiles

| Profile | Capability | Motivation |
|---|---|---|
| **Untrusted API Caller** | Can send arbitrary HTTP requests to port 8788. | Attempt out-of-scope scanning, target spoofing, credential brute-forcing, or denial of service. |
| **Malicious / Compromised Runner** | Controls a host running worker software. | Attempt to forge execution receipts, tamper with test outcomes, or upload fraudulent artifacts. |
| **Untrusted LLM / Agent Output** | Outputs text/JSON responses to prompts. | Hallucinate vulnerabilities, propose unverified claims, attempt indirect prompt injection. |
| **Compromised Insider (Researcher)** | Possesses researcher API token. | Attempt to approve their own finding, bypass gates, or submit unverified reports. |

---

## 3. STRIDE Threat Analysis & Mitigations

### 3.1 Spoofing
- **Threat:** Malicious caller claims to be an authorized runner or administrator.
- **Mitigation:**
  - Token separation: distinct tokens for admin, approval, api, and runners.
  - Ed25519 cryptographic signing for runner execution receipts; receipts with invalid signatures or mismatched public keys are rejected.
  - Constant-time string comparison (`timingSafeEqual`) prevents timing side-channel attacks on credentials.

### 3.2 Tampering
- **Threat:** Tampering with artifact bytes, altering execution logs, or modifying audit records.
- **Mitigation:**
  - Content-addressed artifact storage: artifact storage keys and database records are verified against SHA-256 byte hashes.
  - Append-only audit chain: `execution_audit` table is protected by a PostgreSQL trigger (`prevent_audit_mutation()`) that rejects any `UPDATE` or `DELETE` statements.
  - Consecutive entries in `execution_audit` contain cryptographic hash links (`previous_hash` and `record_hash`), enabling deterministic tamper detection.

### 3.3 Repudiation
- **Threat:** An operator denies performing a privileged action (e.g. revoking a target record or approving a run).
- **Mitigation:**
  - Every privileged API route requires an actor label and records an audit entry containing `actor_id`, `action`, `subject_type`, `subject_id`, `request_id`, and exact timestamp.
  - Correlated request IDs are logged and bound into the audit entry.

### 3.4 Information Disclosure
- **Threat:** Exposure of API credentials, database connection strings, or sensitive source code in logs/responses.
- **Mitigation:**
  - Fastify logger explicitly redacts `authorization`, `x-admin-token`, `x-approval-token`, and `x-runner-token` headers.
  - Structured error responses return non-sensitive error codes and omit internal stack traces or database error details.
  - Local loopback binding (`127.0.0.1`) prevents unintentional network exposure.

### 3.5 Denial of Service (DoS)
- **Threat:** Massive payload upload, recursive AST graph exhaustion, or runner execution hangs.
- **Mitigation:**
  - Fastify `bodyLimit` enforced on all requests (maximum 20.5 MB; artifacts capped at 10 MB).
  - Bounded AST depth and source size checks in `boundedSolcAst` and `boundedSources`.
  - Runner timeouts (10 minutes) with automatic container termination via `--cidfile` and `docker stop`.

### 3.6 Elevation of Privilege
- **Threat:** An LLM or automated tool attempts to approve a finding or execute arbitrary shell commands.
- **Mitigation:**
  - **Zero Default Authority:** LLM adapter (`src/providers/gemini.ts`) has zero tool definitions and produces only advisory triage text.
  - **Fixed Suite Allowlist:** Runners only execute immutable allowlisted suite IDs (`build`, `baseline-tests`, `slither`); command strings are never accepted over API.
  - **Separation of Duties:** Researchers cannot approve their own findings (`checkFindingApprovalSeparation`); independent review must be conducted by a distinct identity (`checkIndependentReviewSeparation`).

---

## 4. Residual Risks & Future Mitigations

1. **Database Superuser Compromise:** A root PostgreSQL superuser could disable triggers and alter historical rows.
   - *Mitigation:* Periodic notarization of `GET /v1/audit/export` chain-head hash to external append-only storage.
2. **SSO / OIDC Absence in Development:** In local development, actor labels are supplied via `x-actor-id`.
   - *Mitigation:* In production, integrate enterprise OIDC provider and bind authenticated JWT claims to principal identity.
