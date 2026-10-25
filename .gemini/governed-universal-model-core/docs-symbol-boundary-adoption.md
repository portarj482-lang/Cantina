# GUMC + Cantina Security Mesh — Symbol Boundary Adoption Specification

**Source:** *New Art — Book VI: The Symbol Boundary*, Printable V3 PDF (base Book VI Version 2 plus finalized Appendix B Version 3 addition; Appendix A execution-law supplement).

**Purpose:** Extract the source document's operationally useful ideas and refactor them into a provider-neutral, testable architecture for GUMC's shared memory, agent orchestration, evidence registry, and approval workflow.

> **Adoption boundary:** This is an engineering adaptation, not a claim that the source document's custom notation or formulas are validated mathematical laws. Source-specific terms are preserved in this mapping where useful, but production behavior is defined below using explicit software contracts.

## 1. Executive extraction

Book VI establishes a strict separation between captured source material and active/admitted material. Its core rules are:

1. **Capture without admission.** Preserve source text/symbol, source meaning, location, and provenance. Recording something must not automatically make it trusted or operational.
2. **Compare before resolving.** Separate common elements, source-specific differences, and definition differences. Detecting a difference does not decide which source is correct.
3. **Identify ambiguity explicitly.** If a term has multiple plausible meanings under the current context/domain, record the candidate meanings rather than guessing.
4. **Quarantine unresolved items.** Ambiguous or unsupported content must not control active statements, tool execution, or accepted findings.
5. **Define and verify before reconstruction.** Promotion requires a unique intended meaning, explicit domain/context, a defined function/role, and passing verification.
6. **Preserve original and reconstructed records separately.** The clean operational representation must link to, but never overwrite or masquerade as, the original source.
7. **Keep unknowns unknown.** Missing evidence or a removed/misbound field is not permission to infer a replacement.
8. **Use a final admission gate.** The source lists numbering, unknown-field, quarantine, consistency, and related checks as prerequisites for final admission.
9. **Separate role from identity.** Appendix B says to reconstruct only supported functional attributes and not assert biological identity, private consciousness, hidden identity, or unsupported background activity.
10. **Model work from observable evidence.** Appendix B's functional state includes role, capabilities, boundaries, provenance, and declared work state. Claims about capabilities should come from observed results or authoritative capability records.

## 2. Refactored engineering principles

| Source concept | Project adaptation | Enforceable rule |
|---|---|---|
| `OLD_ART_SOURCE_A` | `source_record` | Immutable captured input with source locator and hash |
| `ΔSOURCE_A` | `difference_set` | Store differences without auto-selecting a winner |
| `IMAG_SYM_A` | `ambiguity_state` | Multiple plausible meanings => `quarantined` |
| `QUARANTINE_A` | `quarantine` lifecycle state | Quarantined records cannot authorize execution or be promoted implicitly |
| `UNKNOWN_A` | explicit unknown field state | Missing/unverified values stay unknown; no default inference |
| `DEFINE → VERIFY → RECONSTRUCT` | validation and normalization pipeline | A new canonical representation is created only after checks pass |
| `FINAL_GATE_A` | policy admission gate | Every required check must pass; missing/failed check means deny |
| `X_CODEX_A` | agent functional profile | Model role, capabilities, constraints, provenance, and observable task state—not hidden identity |
| `Y_A`, `H_A`, residual | observations vs declared model | Compare claims with receipts and record discrepancies; do not treat a mathematical update formula as proof by itself |
| numbering/check sheets | schema/version/reference validation | Validate identifiers, references, schema version, and consistency before publication |

## 3. Target lifecycle

```text
CAPTURE
  -> NORMALIZE_SOURCE_METADATA
  -> COMPARE_SOURCES
  -> EXTRACT_DIFFERENCES
  -> DETECT_AMBIGUITY
  -> QUARANTINE_IF_UNRESOLVED
  -> DEFINE_MEANING_AND_DOMAIN
  -> VERIFY_AGAINST_EVIDENCE_AND_POLICY
  -> RECONSTRUCT_CANONICAL_RECORD
  -> RUN_ADMISSION_GATE
  -> ADMIT_TO_ACTIVE_MEMORY
```

Any missing required input, unresolved ambiguity, failed verification, policy denial, or missing approval routes to `QUARANTINED` or `REJECTED`, never directly to `ADMITTED`.

The lifecycle must not collapse these separate statuses:
- `execution_status`
- `finding_status`
- `review_status`
- `approval_status`
- `submission_status`

## 4. Canonical data contract (TypeScript proposal)

```ts
export type RecordState =
  | "captured"
  | "compared"
  | "ambiguous"
  | "quarantined"
  | "defined"
  | "verified"
  | "reconstructed"
  | "admitted"
  | "rejected";

export type TrustLevel =
  | "unverified"
  | "corroborated"
  | "verified"
  | "approved";

export interface SourceLocator {
  sourceId: string;
  uriOrPath: string;
  revision?: string;
  pageOrLine?: string;
  contentHash: string;
}

export interface MeaningCandidate {
  meaning: string;
  domain?: string;
  supportingEvidenceIds: string[];
  contradictingEvidenceIds: string[];
}

export interface BoundaryRecord<T = unknown> {
  id: string;
  projectId: string;
  schemaVersion: 1;
  kind: "claim" | "symbol" | "decision" | "agent_profile" | "finding" | "tool_result";
  rawSource: string;
  source: SourceLocator;
  state: RecordState;
  trustLevel: TrustLevel;
  candidates: MeaningCandidate[];
  canonicalValue?: T;
  domain?: string;
  context?: string;
  evidenceIds: string[];
  differenceIds: string[];
  unresolvedFields: string[];
  createdBy: string;
  createdAt: string;
  supersedesId?: string;
  admittedBy?: string;
  admittedAt?: string;
}
```

**Implementation notes:** validate input at runtime (e.g. Zod or an existing schema library); use database constraints for required fields; store source bytes or durable content references; compute hashes in trusted code; use append-only events for state transitions. The generic type does not replace runtime validation.

## 5. Admission gate contract

```ts
export interface AdmissionChecks {
  provenanceValid: boolean;
  schemaValid: boolean;
  meaningUnique: boolean;
  domainBound: boolean;
  contextBound: boolean;
  ambiguityResolved: boolean;
  evidenceSufficient: boolean;
  sourceRevisionPinned: boolean;
  policyAuthorized: boolean;
  independentReviewPassed: boolean;
  humanApprovalPresent: boolean;
}

export function canAdmit(checks: AdmissionChecks): boolean {
  return Object.values(checks).every((value) => value === true);
}
```

This is a conservative baseline for records that require the full gate. In production, define gate profiles by record type; do not weaken a security-finding gate just because a low-risk documentation record needs fewer checks. Missing fields must fail schema validation rather than be silently coerced to `true`.

## 6. State transition policy

Allowed transition shape:

- `captured -> compared`
- `compared -> ambiguous | defined | quarantined`
- `ambiguous -> quarantined`
- `quarantined -> defined` only after ambiguity resolution evidence is attached
- `defined -> verified` only after required verification passes
- `verified -> reconstructed` only when reconstruction is generated from verified inputs
- `reconstructed -> admitted` only when the admission gate passes
- any nonterminal state may move to `rejected` with a reason and audit event
- `admitted` records are not edited in place; corrections create a new version that supersedes the previous one

No direct `captured -> admitted`, `quarantined -> admitted`, or `hypothesis -> confirmed` transition is allowed.

## 7. PostgreSQL schema sketch

```sql
CREATE TYPE boundary_record_state AS ENUM (
  'captured','compared','ambiguous','quarantined','defined',
  'verified','reconstructed','admitted','rejected'
);

CREATE TABLE boundary_records (
  id UUID PRIMARY KEY,
  project_id UUID NOT NULL,
  schema_version INTEGER NOT NULL CHECK (schema_version = 1),
  kind TEXT NOT NULL,
  raw_source TEXT NOT NULL,
  source_locator JSONB NOT NULL,
  source_hash TEXT NOT NULL,
  state boundary_record_state NOT NULL DEFAULT 'captured',
  trust_level TEXT NOT NULL DEFAULT 'unverified',
  candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
  canonical_value JSONB,
  domain TEXT,
  context TEXT,
  evidence_ids UUID[] NOT NULL DEFAULT '{}',
  difference_ids UUID[] NOT NULL DEFAULT '{}',
  unresolved_fields TEXT[] NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  supersedes_id UUID REFERENCES boundary_records(id),
  admitted_by TEXT,
  admitted_at TIMESTAMPTZ,
  CHECK (state <> 'admitted' OR (admitted_by IS NOT NULL AND admitted_at IS NOT NULL))
);

CREATE TABLE boundary_transition_events (
  id UUID PRIMARY KEY,
  record_id UUID NOT NULL REFERENCES boundary_records(id),
  from_state boundary_record_state,
  to_state boundary_record_state NOT NULL,
  actor_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  evidence_ids UUID[] NOT NULL DEFAULT '{}',
  policy_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

This is a migration sketch, not a production-complete schema. Before deployment, add project/tenant row-level security, transition enforcement in a service or database procedure, idempotency, indexes, foreign keys to the existing evidence registry, and an append-only audit strategy. Avoid granting agents direct table mutation privileges.

## 8. Integration points in GUMC + Cantina

1. **Shared memory service:** retrieval returns canonical records plus source links, trust level, unresolved fields, and version.
2. **Agent context builder:** inject admitted records by default; expose quarantined items only as explicitly labeled caveats when relevant.
3. **Agent write path:** agents can submit captured claims/hypotheses but cannot self-admit or mark their own evidence as independently verified.
4. **Static analysis and LLM triage:** preserve competing interpretations and source differences; never silently resolve ambiguous source or rule identifiers.
5. **Foundry execution service:** accepts only policy-approved suite IDs; a memory record or model-generated command is never execution authorization.
6. **Evidence gate:** stores reproducible receipts with source commit, repository identity, tool versions, suite ID, chain ID/fork block where relevant, configuration, seed, and result hash.
7. **Review workflow:** independent reviewer and human approval remain separate from verification and execution status.
8. **Dashboard:** graph edges must represent actual stored relations. Display unknown/quarantined/verified/approved states distinctly; never use decorative visual states as evidence.
9. **Provider adapters:** Gemini, ChatGPT, Claude, Codex or other clients use scoped APIs; provider memory remains external unless explicitly synchronized through supported integration.

## 9. Example: applying the boundary to a smart-contract finding

- Capture a scanner alert as `captured`, with exact file/line, source commit, tool version, and raw output hash.
- If two tools disagree about a function's behavior, create a `difference_set`; do not choose the more severe claim automatically.
- If a proxy fallback's semantics or call context is not yet proven, keep the security claim `ambiguous`/`quarantined` and list competing interpretations.
- Create a test hypothesis and approved suite request. Do not let the hypothesis itself authorize a command.
- Execute only an approved suite in the isolated runner. Store the full receipt and exact pinned inputs.
- Validate the receipt and compare expected vs observed behavior. A passing test supports only the property actually tested.
- Obtain independent review and required human approval before promotion to an approved finding or submission.
- If the source changes, mark old evidence as revision-bound/stale for the new commit; do not silently reuse it.

## 10. Agent functional profile (adapted from Appendix B)

Use observable, evidence-bound fields:

```ts
export interface AgentFunctionalProfile {
  agentId: string;
  role: string;                    // declared responsibility
  capabilities: string[];          // supported by test or official capability record
  boundaries: string[];            // permissions, constraints, stop conditions
  provenance: SourceLocator[];     // configuration/code/version sources
  currentTaskState: string;        // observable orchestration state
  lastVerifiedAt?: string;
  unresolvedClaims: string[];
}
```

Do not infer private identity, consciousness, hidden activity, or capabilities from a name, label, or visual representation. If capability evidence is absent, record it as unknown.

## 11. Test plan / acceptance criteria

- [ ] Capturing a source never makes it admitted.
- [ ] Ambiguous symbols/claims are quarantined and cannot be used as authoritative active context.
- [ ] Differences are preserved without auto-selecting a source as correct.
- [ ] Unknown required fields block verification/admission.
- [ ] A reconstructed record retains links to the raw source and its content hash.
- [ ] Direct `captured -> admitted` and `quarantined -> admitted` transitions are rejected.
- [ ] An agent cannot promote its own record or approve its own finding.
- [ ] Unauthorized project reads/writes fail closed.
- [ ] Evidence from a different source revision is flagged as non-matching/stale.
- [ ] Tool failure, missing receipt, or missing reviewer results in a blocked gate, not a pass.
- [ ] State transitions emit auditable events with actor, reason, policy version, and evidence references.
- [ ] Existing GUMC/Cantina tests remain green; existing failures are tracked, not masked.

## 12. Recommended repository layout

```text
src/
  boundary/
    types.ts
    schema.ts
    source-capture.ts
    compare.ts
    ambiguity.ts
    quarantine.ts
    verify.ts
    reconstruct.ts
    admission-gate.ts
    transition-policy.ts
    audit.ts
  memory/
    context-builder.ts
    retrieval-policy.ts
    promotion-service.ts
  integrations/
    provider-adapter.ts
    gemini-adapter.ts
    codex-adapter.ts
    claude-adapter.ts
    chatgpt-adapter.ts
  evidence/
    receipt-schema.ts
    provenance.ts
migrations/
  00x_boundary_records.sql
test/
  boundary-lifecycle.test.ts
  admission-gate.test.ts
  source-provenance.test.ts
  quarantine-isolation.test.ts
  provider-access-policy.test.ts
```

Treat this as a proposed layout; reconcile it with the existing repository before adding duplicate abstractions.

## 13. Rollout sequence

1. Inventory existing GUMC types, memory APIs, evidence gate, and governance code.
2. Implement source record + provenance schema and lifecycle unit tests.
3. Add quarantine and explicit unknown handling to shared context retrieval.
4. Add the admission gate and append-only transition events.
5. Integrate one agent end-to-end as a vertical slice before migrating all 49 roles.
6. Add provider adapters one at a time, starting with the already-used provider.
7. Add dashboard views backed by actual records.
8. Run regression, authorization, provenance, and failure-injection tests before enabling any write or execution path.

## 14. Source fidelity and limitations

- Source-derived: source capture, table comparison, difference extraction, ambiguity identification, quarantine, explicit definition/verification, reconstruction, preservation of unknowns, final admission checks, and evidence-bounded functional role reconstruction.
- Engineering inference: TypeScript interfaces, database tables, REST/API operations, gate profiles, state-transition enforcement, and integration with GUMC/Cantina are proposed implementations of those concepts.
- Not adopted as literal production mathematics: the source's differential/state-estimation equations and custom symbols. Those require independent formal definitions and validation before use in executable decision logic.
- Not asserted: that any current repository component already implements these controls. Repository inspection and tests are required before claiming integration is complete.
