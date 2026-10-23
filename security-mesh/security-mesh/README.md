# Antigravity Security Mesh — Foundation v0.1

A TypeScript/Node.js foundation for scope-authorized security research. The current web/email workflow supports passive assessment of explicitly registered hosts; the legacy EVM/F-001 path remains separate and does not define the active program scope.

**Runtime:** Node.js 22+ / TypeScript · **API:** Fastify on port `8788` · **Database:** PostgreSQL · **LLM status:** optional, manually invoked, approval-gated Gemini advisory endpoint; never auto-dispatched · **Execution:** offline in-process analysis worker plus isolated manual Foundry runner

This package is a usable foundation, **not a finished autonomous auditor**. It intentionally starts with no authorized scopes, has no transaction-signing path, has no arbitrary-shell interface, and does not submit reports to Cantina.

## What's implemented

- Exactly 49 versioned agent capability profiles, with stage, skill bindings, tool allowlists, sandbox and network profiles, budgets, permissions, dependencies, schemas, and retry limits. The five Solana-specific agents are disabled for EVM workflows.
- PostgreSQL migrations for the authorized scope registry, independent workflow status fields, agent/task records, skill/knowledge records, approved suite registry, execution runs, evidence, artifact manifests, readiness gates, reviews, human approvals, submission records, and append-only execution audit events.
- A Fastify API on port `8788`, independent API/admin/approval/runner tokens, request IDs, input validation, and append-only privileged-action audit records linked by a verified SHA-256 hash chain.
- Fail-closed target checks: repository, exact source commit, chain ID, pinned nonzero fork block, target addresses, allowed methods, and expiry must match a registered scope. There are **zero scopes by default**.
- Oracle target records (`POST /v1/target-records`, `GET /v1/target-records/:id/check`) bind each EVM workflow/run to one target, active scope snapshot, source/environment pins, method/suite allowlists, optional harness digest, and expiry. Workflows, agent tasks, run approvals, runner claims, receipts, artifacts, and evidence fail closed without matching target bindings.
- A source-manifest intake flow that validates schema, paths, duplicate entries, commit/repository binding, and a deterministic digest over tracked-file hashes. Manifest upload alone deliberately leaves G1 `inconclusive`; G1 cannot pass until a reviewer has verified a separate source-attestation artifact with repository, commit-object, and source-line provenance bound to the workflow.
- Content-addressed artifact storage using SHA-256, restrictive local file permissions, and a maximum artifact size.
- A fixed suite allowlist (`build`, `baseline-tests`, `revocation`, `permit2-fork`, and `patched-negative-control`). API callers provide suite IDs, never command strings.
- A leased, retrying task worker with strict application-registered handlers. The built-in `pathway-scout` consumes supplied solc AST and emits an offline call/inheritance graph; it does not compile or fetch source.
- When matching source text is supplied, Scout also attaches byte offsets, 1-based line spans, and SHA-256 hashes of each contract/function/call span. It analyzes bounded AST/source units, not one agent per line; missing/mismatched source text yields no fabricated source provenance.
- Authorized passive web checks: public-DNS validation and one HTTPS `HEAD /` for approved hosts; email-domain MX/SPF/DMARC DNS checks. No crawling, authentication, mail sending, or exploit probes.
- Labeled benchmark submission and persisted precision/recall/F1, PoC reproduction, duration, and cost metrics. Dataset quality and labels must still be independently maintained.
- Human-approved execution queue with fixed auto-dispatched build, baseline, and Slither profiles; the runner still must claim the run before execution.
- A deterministic receipt checker that verifies Ed25519 runner signatures in production (development HMAC remains available), source/chain/fork/suite identity, required assertions, timestamps, registered artifact references, and artifact bytes.
- Separate execution, finding, review, approval, and submission statuses. A passed execution receipt does not change a finding to `supported`.
- Evidence annotation and human artifact verification, gate-specific checks for G1 source attestation, cross-provider RPC observations, overlap coverage, severity rubric, claim provenance, and symbolic evidence, plus G1–G9 readiness display.
- Optional Gemini triage at `POST /v1/triage/gemini` sends only the bounded title, hypothesis, source excerpt, and evidence summaries in that request. It is off by default (`GEMINI_TRIAGE_ENABLED=false`), also requires `GEMINI_API_KEY`, a valid `x-approval-token`, an audit actor, and `externalProcessingApproved: true` in the body. Calls are manual only; audit records contain payload/response hashes and sizes, never the submitted text. The returned analysis is advisory and requires human review; Gemini cannot approve findings, dispatch tools, or submit reports.
- Report drafting and human submission authorization. The API records authorization only; there is no Cantina submission connector.
- A local source-manifest generator and an offline smoke script for key policy/evidence checks.

## Not yet implemented

The API now runs a bounded Scout → pattern-scan → Strategist task chain against caller-supplied solc AST/source and stores supplied labeled benchmark scores. EVM inputs are not independently fetched/compiled by that in-process analysis, so outputs are provisional. The separate host runner polls approved jobs, fetches the exact source commit from supported public Git hosts, then runs fixed Foundry build/baseline or Slither profiles in digest-pinned, no-network containers. Exact target PoC/fork suites remain disabled until a specific authorized target, reviewed harness, assertions, and restricted RPC gateway are supplied. Source-manifest authenticity still depends on the controlled runner; a build pass or scanner lead is not vulnerability evidence.

Production runner writes require a registered per-runner token hash, assigned lease, and matching Ed25519 key. `RUNNER_TOKEN` remains development-only. `x-actor-id` is audit metadata, not authenticated human identity; SSO/OIDC is still needed for human reviewers. The audit hash chain detects row tampering/reordering but does not prevent a privileged database operator from rewriting the whole database; retain an independently signed/exported chain head for that threat. The polling runner must run on a hardened host with Docker access; workload containers receive neither the Docker socket nor runner credentials.

## 1. Quick start (Windows PowerShell)

Install Node.js 22+ and Docker Desktop. From this project directory:

```powershell
Copy-Item .env.example .env
```

Replace all credential values in `.env` with different random secrets (at least 32 characters each). For example, generate one secret at a time:

```powershell
node -e "console.log(require('node:crypto').randomBytes(32).toString('hex'))"
```

Use a different generated value for `API_TOKEN`, `ADMIN_API_TOKEN`, `HUMAN_APPROVAL_TOKEN`, and `RUNNER_TOKEN`. Do not commit `.env`.

Start PostgreSQL and install dependencies:

```powershell
docker compose up -d postgres
npm install
npm run db:migrate
npm run typecheck
npm test
npm run smoke
npm run build
npm run dev
```

The API binds to `127.0.0.1:8788` by default. In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8788/health
```

A healthy response includes `ok: true`, a reachable database, and an agent count of `49`.

### Layer workflow registry

Layer contracts share one registry at `src/layers/registry.ts`: each declares a parent Oracle, version, entry requirements, ordered agent steps, input/output contracts, authority boundary, and execution mode. `GET /v1/layers` exposes the registry to authenticated API clients. Source pinning, offline analysis, fixed-profile isolated execution, evidence gates, independent review, and report drafting are active through their current API/runner paths. Execution is limited to build, baseline tests, and Slither; exact target PoCs remain disabled. Registry activation does not bypass scope checks, human approvals, or grant agents authority to change workflow decisions.

`npm run smoke` runs a small offline policy/evidence smoke check using Node's TypeScript stripping support. It is not a substitute for the full Vitest suite, TypeScript typecheck, database integration tests, or sandbox acceptance tests.

### Oracle-bound EVM workflow sequence

For an independently authorized EVM target only: register the scope, create a target record scoped to its exact address/pins/methods, call `/v1/target-records/:id/check`, and include `targetRecordId` when creating the workflow. Suite IDs must be explicitly listed on the record and already dispatch-enabled; disabled target-specific PoC suites remain unavailable. `GET /v1/oracles` lists the deterministic policy checks. The scope/record registration API records operator-provided authorization references—it does not verify Cantina authorization itself.

## 2. Credential boundaries

| Header / setting | Purpose |
|---|---|
| `Authorization: Bearer <API_TOKEN>` | Workflow and read-only metadata APIs |
| `x-admin-token: <ADMIN_API_TOKEN>` | Register an authorized scope |
| `x-approval-token: <HUMAN_APPROVAL_TOKEN>` | Approve queue requests, verify evidence, evaluate human-reviewed gates, review findings, draft reports, authorize report submission |
| `x-runner-id` + `x-runner-token` | Identify a registered runner for claims, artifacts, and receipts; production writes also require its active lease token |
| `x-actor-id: <operator-id>` | Audit label for a privileged human action; **not** an authentication identity |

Never put credentials in browser code, logs, reports, or a repository. Keep the API bound to localhost until a secured gateway is configured.

## 3. Registering a target scope

**Do not copy guessed target values into the registry.** For the active Cantina website/email scope, register only the exact Cantina/Spearbit domains and email domains confirmed by the current program rules through `/v1/web-scopes`. The legacy EVM `/v1/scopes` API is separate and requires explicit repository, commit, contract, chain, block, method, and expiry authorization. Finding #1736 is a hypothesis—not authorization to test a live target.

`POST /v1/scopes` requires the administrator token and an audit actor ID. Request JSON shape:

```json
{
  "programSlug": "coinbase-cantina",
  "repositoryUrl": "https://github.com/VERIFIED_ORG/VERIFIED_REPOSITORY",
  "sourceCommit": "FULL_40_OR_64_CHARACTER_COMMIT_SHA",
  "chainId": 8453,
  "targetAddresses": ["0xREPLACE_WITH_VERIFIED_40_HEX_ADDRESS"],
  "requiredForkBlock": 12345678,
  "allowedMethods": ["static-analysis", "local-test", "fork-test"],
  "programAuthorizationRef": "REVIEWED_CANTINA_RULES_URL_OR_TICKET_REFERENCE",
  "expiresAt": "2030-01-01T00:00:00.000Z",
  "restrictions": {}
}
```

All uppercase/placeholder values above are illustrative and are **not valid target values to use directly**. Replace them with values confirmed from the actual program and source. The API validates shape; it cannot independently verify that the cited program authorization is legitimate. The workflow-creation route rejects any repository, commit, chain, block, address, method, or expiry mismatch.

Example PowerShell for reading metadata:

```powershell
$apiToken = (Get-Content .env | Where-Object { $_ -match '^API_TOKEN=' } | Select-Object -First 1).Split('=',2)[1]
Invoke-RestMethod -Headers @{ Authorization = "Bearer $apiToken" } http://127.0.0.1:8788/v1/agents
```

## 4. Create the F-001 verification workflow

Once the exact target has been independently authorized and entered into the scope registry, submit `POST /v1/workflows` with the same approved values:

```json
{
  "programSlug": "coinbase-cantina",
  "repositoryUrl": "https://github.com/VERIFIED_ORG/VERIFIED_REPOSITORY",
  "sourceCommit": "FULL_APPROVED_COMMIT_SHA",
  "chainId": 8453,
  "targetAddresses": ["0xVERIFIED_TARGET_ADDRESS"],
  "forkBlock": 12345678,
  "requestedMethods": ["local-test", "fork-test"],
  "findingId": "F-001",
  "title": "Verify EIP-7702 / ERC-1271 owner-revocation hypothesis"
}
```

Use the actual registered contract address and approved commit; this example is a schema guide, not a complete request. `8453` is shown as the Base chain ID in the current finding context, but the scope owner must still confirm the correct chain/asset target against the live program before testing. The target's real source commit and fork block are intentionally not pre-populated here.

## 5. Generate a source manifest

After preparing a clean checkout of the exact source commit in the registered scope, run from this project directory:

```powershell
node .\scripts\generate-source-manifest.mjs C:\work\approved-target https://github.com/VERIFIED_ORG/VERIFIED_REPOSITORY FULL_APPROVED_COMMIT_SHA > .\source-manifest.json
```

The generator requires `HEAD` to equal the approved commit and a clean Git working tree, hashes tracked regular files, and emits a deterministic tree digest. Symlinks/submodules are rejected in this initial version. The generated manifest is input to the separately controlled runner/source-pin endpoint; the script itself does not authenticate a runner or prove that the scope is authorized.

For the runner endpoint, encode the manifest JSON as base64 and call:

`POST /v1/workflows/:id/source-pin`

with `x-runner-token` and JSON body `{ "manifestBase64": "..." }`. The API validates the manifest schema, paths, tree digest, repository, and commit, then stores the manifest by content hash.

### Completing G1 without bypassing source provenance

After separately retrieving/validating the pinned checkout and checking the cited source lines, upload a reviewable source-attestation artifact using `POST /v1/workflows/:id/artifacts`. Then annotate it with `POST /v1/workflows/:id/evidence` using `evidenceKind: "source-attestation"` and metadata containing `repositoryUrl`, `commitSha`, `repositoryIdentityVerified: true`, `commitObjectVerified: true`, `lineProvenanceVerified: true`, and a non-empty `sourceLineRefs` array. Each source-line reference must have a safe `path`, positive `startLine`, `endLine >= startLine`, and `excerptSha256`. These metadata fields must describe an actual reviewed artifact; do not set them merely to make the gate pass. A human reviewer must verify both the source-manifest evidence and source-attestation evidence through `POST /v1/workflows/:id/evidence/:evidenceId/verify`, then explicitly evaluate `POST /v1/workflows/:id/gates/G1/evaluate` as `passed` with both evidence IDs. This API validates the evidence schema/metadata but cannot independently prove a human reviewed the underlying Git host; the reviewer and isolated source-pin service remain part of the trust boundary. G1 cannot be marked not applicable.

## 6. Main API endpoints

| Method | Endpoint | Purpose / control |
|---|---|---|
| `GET` | `/health` | Database health check; no token |
| `GET` | `/healthz` | Liveness check (pass/fail); no token |
| `GET` | `/readyz` | Readiness check (database connection and applied migration count); no token |
| `GET` | `/v1/agents` | 49 agent capability profiles; API token |
| `GET` | `/v1/tool-registry` | Allowlisted suite profiles; API token |
| `GET` | `/v1/oracles` | Deterministic Oracle registries and boundaries; API token |
| `GET` | `/v1/layers` | 6 workflow layers and execution modes; API token |
| `GET` | `/v1/scopes` | Scope registry metadata; API token |
| `POST` | `/v1/scopes` | Register scope; admin token + actor ID |
| `GET` | `/v1/target-records` | List target authorization records; API token |
| `POST` | `/v1/target-records` | Create target authorization record bound to scope snapshot; admin token + actor ID |
| `GET` | `/v1/target-records/:id` | Read target record by ID with bound program slug; API token |
| `POST` | `/v1/target-records/:id/revoke` | Revoke target authorization record and audit action; admin token + actor ID |
| `GET` | `/v1/target-records/:id/check` | Check target record binding against current scope; API or runner token |
| `POST` | `/v1/runners/register` | Register/rotate a runner's Ed25519 public key and issue a one-time token; admin token + actor ID |
| `POST` | `/v1/runners/:id/revoke` | Disable runner and cancel its active leases; admin token + actor ID |
| `POST` | `/v1/runner/claim` | Atomically claim an approved compatible run; per-runner credentials |
| `POST` | `/v1/runner/renew` | Renew the assigned run lease; per-runner credentials + lease token |
| `GET` | `/v1/audit/verify` | Verify the append-only SHA-256 audit chain; API token |
| `GET/POST` | `/v1/web-scopes` | List/register explicit website and email-domain authorization; admin token for registration |
| `POST` | `/v1/web-scopes/:id/assess/web` | One scoped HTTPS `HEAD /` and security-header observation; API token |
| `POST` | `/v1/web-scopes/:id/assess/email-dns` | Scoped MX/SPF/DMARC DNS observations only; API token |
| `GET` | `/v1/web-scopes/:id/assessments` | Read persisted web/email observations; API token |
| `POST` | `/v1/benchmarks/evaluate` | Score and persist caller-labeled benchmark cases; API token + actor ID |
| `GET` | `/v1/benchmarks` | Read benchmark score history; API token |
| `POST` | `/v1/workflows` | Create workflow bound to a validated targetRecordId; API token + actor ID |
| `GET` | `/v1/workflows/:id` | Workflow, runs, evidence, gates, reviews, approvals; API token |
| `POST` | `/v1/workflows/:id/tasks` | Queue a version-matched built-in offline AST handler; API token + actor ID |
| `POST` | `/v1/workflows/:id/pipeline` | Dispatch Scout → static pattern leads → Strategist using pinned-commit-labelled inputs; API token + actor ID |
| `GET` | `/v1/workflows/:id/tasks` | Read task and lease status; API token |
| `POST` | `/v1/workflows/:id/source-pin` | Validate and store source manifest; runner token |
| `POST` | `/v1/workflows/:id/artifacts` | Store content-hash-verified artifact bytes; runner token |
| `POST` | `/v1/workflows/:id/evidence` | Add unverified evidence annotation linked to an uploaded artifact; runner token |
| `POST` | `/v1/workflows/:id/evidence/:evidenceId/verify` | Verify stored bytes and record human review; approval token + actor ID |
| `POST` | `/v1/workflows/:id/approve-run` | Approve a fixed supported suite for the isolated runner queue; approval token + actor ID |
| `POST` | `/v1/workflows/:id/runs/:runId/receipt` | Verify signed receipt, assertions, identity, and artifact bytes; runner token |
| `GET` | `/v1/workflows/:id/gates` | Read G1–G9 outcomes and missing gates; API token |
| `POST` | `/v1/workflows/:id/gates/:gateId/evaluate` | Human evaluation for G1/G2/G4/G5/G6/G7, with evidence constraints |
| `POST` | `/v1/workflows/:id/finding-decision` | Human decision; a `supported` decision requires all G1–G8 to pass or be policy-approved N/A, plus passed execution/evidence |
| `POST` | `/v1/workflows/:id/review` | Record independent review; accepted review requires a different actor label, supported finding, passed execution, and verified evidence |
| `POST` | `/v1/workflows/:id/report-draft` | Create Markdown draft from human-supplied claims and verified evidence; approval token + actor ID |
| `POST` | `/v1/workflows/:id/approve-submission` | Record human authorization only after G1–G9 and report gates qualify; does **not** submit externally |

Approved suite requests enter the isolated-runner queue. They are not executions until a compatible registered runner claims them and returns a valid receipt. Only mapped fixed profiles can run; arbitrary commands are never accepted.

### 6.1 Required Target Authorization Sequence

All execution runs require an authorized target-record binding. Every operation follows this strict sequence:

#### Step 1: Create Target Record (`POST /v1/target-records`)
Requires `x-admin-token` and `x-actor-id`. The target record binds to one existing authorized scope, calculating and storing the exact canonical `scopeSha256` digest:

```bash
curl -X POST http://127.0.0.1:8788/v1/target-records \
  -H "x-admin-token: $ADMIN_API_TOKEN" \
  -H "x-actor-id: admin:alice" \
  -H "Content-Type: application/json" \
  -d '{
    "scopeId": "00000000-0000-4000-8000-000000000101",
    "targetId": "manager-target",
    "targetAddress": "0x1111111111111111111111111111111111111111",
    "repositoryUrl": "https://github.com/example/protocol",
    "sourceCommit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "chainId": 8453,
    "forkBlock": 123456,
    "environment": "base-mainnet-pinned-fork",
    "allowedMethods": ["local-test"],
    "suiteIds": ["build"],
    "expiresAt": "2034-01-01T00:00:00.000Z",
    "harnessSha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
  }'
```

Returns HTTP 201 with `{ "id": "<targetRecordId>", "status": "active", "oracle": { "outcome": "allow" } }`.

#### Step 2: Check Target Record (`GET /v1/target-records/:id/check`)
Requires `Authorization: Bearer $API_TOKEN` or `x-runner-token`. Validates that the stored `scopeSha256` still matches the scope's current binding digest, the scope and target records are unexpired and active, and all constraints hold:

```bash
curl http://127.0.0.1:8788/v1/target-records/00000000-0000-4000-8000-000000000102/check \
  -H "Authorization: Bearer $API_TOKEN"
```

Returns `{ "targetRecordId": "...", "valid": true, "oracle": { "outcome": "allow", "reasons": [] } }`.

#### Step 3: Create Bound Workflow (`POST /v1/workflows`)
Requires `Authorization: Bearer $API_TOKEN` and `x-actor-id`. The workflow must provide `targetRecordId`. The Target Dispatch Oracle verifies that the workflow's parameters match the target record exactly:

```bash
curl -X POST http://127.0.0.1:8788/v1/workflows \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "x-actor-id: researcher:bob" \
  -H "Content-Type: application/json" \
  -d '{
    "targetRecordId": "00000000-0000-4000-8000-000000000102",
    "programSlug": "base-cantina",
    "repositoryUrl": "https://github.com/example/protocol",
    "sourceCommit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "chainId": 8453,
    "targetAddresses": ["0x1111111111111111111111111111111111111111"],
    "forkBlock": 123456,
    "requestedMethods": ["local-test"],
    "title": "Authorized target-bound verification workflow"
  }'
```

Returns HTTP 201 with `{ "id": "<workflowId>", "status": "learning", "executionStatus": "queued" }`.

#### Step 4: Approve Run for Fixed Suite (`POST /v1/workflows/:id/approve-run`)
Requires `x-approval-token` and `x-actor-id`. Re-verifies the target record and selects only allowlisted, safe, enabled fixed suites (`build`, `baseline-tests`, `slither`):

```bash
curl -X POST http://127.0.0.1:8788/v1/workflows/<workflowId>/approve-run \
  -H "x-approval-token: $HUMAN_APPROVAL_TOKEN" \
  -H "x-actor-id: approver:carol" \
  -H "Content-Type: application/json" \
  -d '{
    "suiteId": "build",
    "rationale": "Human approval to compile pinned target in isolated runner."
  }'
```

Returns HTTP 202 with `{ "runId": "...", "suiteId": "build", "status": "queued", "executed": false }`. An isolated runner claims this run, verifies the target record binding, and posts back the signed execution receipt.

## 7. F-001 verification sequence

1. Register only the live, documented, authorized source/contract/chain/block/method scope.
2. Pin the exact source commit and independently inspect the relevant `EIP7702Proxy` / `CoinbaseSmartWallet` implementation relationship.
3. Confirm the target code and source line claims; keep the reported fallback/revocation behavior as a falsifiable hypothesis.
4. Design a valid-signature baseline, same-digest/same-signature comparison, owner-removal assertion, and appropriate patched negative control.
5. Use the `revocation` suite only after a worker maps that immutable suite ID to a reviewed command profile. The `permit2-fork` suite is applicable only if Permit2 prerequisites and downstream balance-impact claims are actually in scope.
6. Save raw logs/traces/outputs as artifact bytes. Upload them, make evidence annotations, and have a reviewer verify their content and hashes.
7. Evaluate independent RPC, overlap, severity, claim provenance, and symbolic-analysis gates with the evidence required by each gate.
8. Record a finding decision separately from execution status. An AI suggestion or exit code is not a finding verdict.
9. Require independent review and a human submission authorization. Submission remains manual until a separately reviewed Cantina integration exists.

## 8. Learning and AI boundaries

`src/providers/gemini.ts` is a structured triage adapter and is intentionally not exposed as an arbitrary model-to-tool bridge. It has no function tools, validates its response shape, and can only produce hypotheses, confirmation criteria, falsification criteria, and uncertainty notes. The actual learning approval/promotion API and dashboard are future phases. The database schema reserves versioned skill and knowledge records, but there is no autonomous skill promotion.

## 9. Verification checklist

Run locally once dependencies can be installed:

```powershell
npm run typecheck
npm test
npm run smoke
npm run build
```

With Docker Desktop running, start the loopback-only PostgreSQL test service with `docker compose up -d postgres`. Copy `.env.example` to `.env` and replace each token placeholder with a different random secret of at least 32 characters before starting the API or running migrations. Then run `npm run db:migrate`; for the PostgreSQL/API integration test set PowerShell `$env:TEST_DATABASE_URL='postgres://mesh:mesh_dev_password@127.0.0.1:5432/security_mesh_integration'` and run `npm run test:integration`. The integration test uses a synthetic-only scope and verifies allow/deny target records, workflow binding, audit-chain verification, and append-only enforcement. The host runner auto-detects the per-user Docker Desktop CLI on Windows; its container image must be locally available and pinned by digest.

Before controlled research use, also run integration tests for PostgreSQL transactions, unauthorized scopes, runner receipt forgery, artifact tampering, queue idempotency, and recovery. Before any remote execution, add and review the isolated worker, egress policy, tool version pinning, immutable suite mappings, resource limits, runner-specific identity/signature keys, and artifact retention policy.
