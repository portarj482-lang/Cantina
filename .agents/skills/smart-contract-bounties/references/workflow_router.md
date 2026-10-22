# Master Bounty Workflow & Platform Routing

## Overview
This workflow coordinates smart-contract bug bounty operations across any platform (Cantina, Immunefi, Code4rena, Sherlock, Private disclosures). It synthesizes:
- Platform lifecycle and scope governance (`cantina-bug-bounty`, `bug-bounty`)
- Disciplined hypothesis testing (`v4lend-hypothesis-cycle`)
- Rigorous PoC engineering (`foundry-poc-writing`)
- Post-investigation continuous learning (`audit-retrospective`)

---

## 1. Six-Stage Lifecycle

To inspect current progress without changing bounty state, run the local execution matrix:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py execution-matrix
```

It checks the scope snapshot and inventories repository checkouts, facts, hypotheses, findings, PoCs, and scan artifacts. Artifact presence is not proof that a finding is valid or that a test passed.

Seal the evidence set before sharing or reviewing it, then verify the seal after any transfer or later edit:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py evidence-seal \
  --output bounties/<slug>/artifacts/evidence-manifest.json
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py evidence-verify \
  --manifest bounties/<slug>/artifacts/evidence-manifest.json
```

The SHA-256 Merkle manifest covers `scope.md`, `facts.md`, and files under `findings/`, `scans/`, and `poc/`. It detects content or inventory changes; it does not establish that the evidence is truthful or complete.

Create a privacy-minimized local telemetry snapshot when aggregate workflow metrics are useful:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py telemetry-report \
  --output bounties/<slug>/artifacts/telemetry-report.json
```

It verifies the execution ledger before reporting run-stage counts, hypothesis status counts, fact/provenance counts, and scope-lock status. It omits raw claims and targets and performs no network transmission.

Use the unified read-only preflight to combine continuity and fact-memory checks, optionally including a finding's six readiness gates:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py workflow-preflight \
  --finding bounties/<slug>/findings/F-001.md \
  --output bounties/<slug>/artifacts/preflight.json
```

The result is `HOLD`, `FINDING_AUDIT_REQUIRED`, or `HUMAN_REVIEW_REQUIRED`. It never grants authorization or submits a finding.

Run a read-only continuity audit when resuming work or before closing a session:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py continuity-audit
```

It checks that the active bounty pointer and state heading agree, agent names are unique, the scope snapshot and local source commits match, fact records have provenance, and hypothesis-ledger lines are valid JSON. It reports stale facts and issues without rewriting state or deleting records. A nonzero exit means at least one check needs review.

Review persistent facts before consolidating or retiring memory:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py fact-review \
  --output bounties/<slug>/artifacts/fact-review.json
```

This read-only review lists provenance gaps, explicit stale markers, fact citations outside current source pins, and possible exact textual duplicates. It never merges or deletes facts; handle any retirement as an append-only status update.

For an explicit, tamper-evident record of a stage result, store a digest of its in-bounty artifact and verify the execution chain:

```bash
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py run-record \
  --stage poc-reproduction --status ok --artifact poc/PoC_F001.t.sol
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py run-verify
py -3 .agents/skills/smart-contract-bounties/scripts/bounty_orchestrator.py run-observe --window 10
```

Records are manual, append-only JSONL under `logs/execution_ledger.jsonl`; `ok` requires an artifact. Verification fails closed on malformed or changed history/artifacts. `run-observe` flags repeated unsuccessful stages but does not attempt recovery. The hash chain is not signed and does not prove that a recorded stage actually ran. `continuity-audit` also checks it when present.

```
[Phase 1: Intake & Scope Lock]
             │
             ▼
[Phase 2: Reconnaissance & Surface Mapping]
             │
             ▼
[Phase 3: Hypothesis Cycle (Read-Predict-Probe-Prove/Kill-Record)]
             │
             ▼
[Phase 4: PoC Engineering (8 Non-Negotiables & Dual-Fork Proof)]
             │
             ▼
[Phase 5: Six Readiness Gates & Triage]
             │
             ▼
[Phase 6: Submission & Retrospective Learning Loop]
```

---

## 2. Platform Nuances & Routing

| Dimension | Cantina | Immunefi | Code4rena / Sherlock |
|---|---|---|---|
| **Scope Lock** | Marker-delimited `<!-- SCOPE START -->` SHA-256 snapshot | Target contracts/assets list in program rules | Pinned commit / repo branch |
| **Severity Model** | Program-specific quoted scale; strictly based on demonstrated economic impact | Preliminary tier screening, validated by loss feasibility | High (direct theft), Medium (conditional/griefing), Low/QA |
| **Proof Standard** | Dual-plane pinned fork reproduction (0 divergence) | End-to-end runnable Foundry test or transaction replay | Runnable forge test replicating vulnerability |
| **Evidence Tagging** | Mandatory provenance tags (`[SRC]`, `[POC]`, `[TOOL]`, `[LOCAL]`) | Clear reproduction steps and impact calculation | Coded PoC with clear attack path walkthrough |

---

## 3. Phase Details

### Phase 1: Intake & Scope Lock
1. Ingest program rules, in-scope contracts, commits, and explicit exclusions into `scope.md`.
2. Compute LF-normalized SHA-256 digest and seal into `snapshots/scope.sha256`.
3. If scope text changes by even 1 character, freeze pending findings until re-verified.

### Phase 2: Reconnaissance & Threat Modeling
1. Check out pinned commit (`git rev-parse HEAD`).
2. Catalog all entry points: external/public functions, modifiers, delegates, hooks, fallbacks.
3. Map external trust boundaries: oracles, ERC-20/777/4626 tokens, cross-chain messaging, admin roles.
4. Run routing check:
   ```bash
   py -3 scripts/bounty_orchestrator.py route --target <contract.sol>
   ```

### Phase 3: Hypothesis Testing Loop
Execute the 5-beat rhythm:
1. **Read**: Focus on a single 100-300 line slice. Trace all preconditions and guards.
2. **Predict**: In writing, specify the unprivileged actor, precise call order, and expected revert selector or balance delta.
3. **Probe**: Execute the smallest test against the real entry point.
4. **Prove or Kill**:
   - *Prove*: Passes 5/5 deterministically for the exact predicted reason.
   - *Kill*: Specific guard or bound stops it. Log immediately with kill category and rationale.
5. **Record**: Log into hypothesis ledger.

### Phase 4: PoC Engineering
Follow all 8 non-negotiables from `references/foundry_poc_standards.md`. Write 4 tests:
- `test_BenignFlow()`: Demonstrates standard honest protocol behavior.
- `test_Exploit()`: Triggers vulnerability and extracts funds or bricks state.
- `test_Boundary()`: Proves the condition 1 unit outside trigger does not exploit.
- `test_PostPatch()`: Shows fix prevents exploit without regressing benign flow.

### Phase 5: Six Readiness Gates
Before any candidate report is considered draft/ready, evaluate:
1. **Source Gate**: Every code reference tagged `[SRC: path:line @commit]`.
2. **Reproduction Gate**: Dual-plane pinned-fork runs match with zero divergence.
3. **Scope Gate**: Affected contract and method are verified in `scope.md`.
4. **Duplicate Gate**: Checked against known issues, past audits, and contest issues.
5. **Severity Gate**: Severity level strictly quoted from program severity scale.
6. **Provenance Gate**: Every sentence tagged with factual provenance.

The machine-readable disposition is `HOLD` if any gate fails, otherwise `HUMAN_REVIEW_REQUIRED`; `authorization_granted` always remains false. A passing audit is not submission approval.

### Phase 6: Retrospective Learning Loop
After each audit or failed hypothesis:
1. Record mistakes and surprises into lessons.
2. Run `learn-summary` to identify top false-positive kill categories.
3. Calibrate severity biases (preventing High/Medium inflation).
