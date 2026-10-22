# Target scan plan — <target-id>

> One file per target. Copy to `bounties/<bounty>/target-workflows/<target-id>.md`. Do not reuse another target's pins, approvals, results, or artifacts.

## Target binding

- Bounty / program:
- Platform:
- Scope snapshot digest and verification artifact:
- Target ID / name / type (EVM, Solana, web, email, other):
- Exact asset (repository + commit/tree, chain + address, hostname/domain, or other):
- Environment:
- Allowed methods / prohibited methods:
- Scope expiry / recheck trigger:
- Target-specific authorization evidence:
- Target owner / parent Oracle:
- Current disposition: `PENDING`

## Assigned workflow

| Layer | Parent / assigned agent IDs | Required input pin | Output contract | Dependencies | Human gate |
|---|---|---|---|---|---|
| Scope and source | | | | | |
| Recon / analysis | | | | | |
| Verification / PoC (if authorized) | | | | | |
| Evidence / quality | | | | | |
| Independent review / reporting | | | | | |

## Five-step execution record

### 1. Bind target and authorization

- Status: `PENDING`
- Scope and target match evidence:
- Allowed method and restrictions check:
- Exceptions / next action:

### 2. Pin inputs and assign the workflow

- Status: `PENDING`
- Source / target / environment pin:
- Agent assignments and contracts:
- Required dependencies and gates:
- Exceptions / next action:

### 3. Analyze and falsify

- Status: `PENDING`
- Surface mapped / sources reviewed:
- Candidate hypotheses and concrete falsifiers:
- Known issue / exclusion review:
- Exceptions / next action:

### 4. Verify safely

- Status: `NOT_RUN`
- User request, approved tool/version, and isolation:
- Target-specific harness / controls:
- Exact command or request class and result:
- If blocked or not applicable, rationale:

### 5. Seal evidence and obtain human disposition

- Status: `PENDING`
- Artifact references and hashes:
- Quality/readiness checks and limitations:
- Independent reviewer / human decision:
- Submission authorization (separate; default `not_authorized`):
- Exceptions / next action:

## Run history

Append dated run IDs and superseding decisions here. Preserve failed, negative, and inconclusive runs.
