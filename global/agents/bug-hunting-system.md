# Cantina Bug-Hunting System

**Purpose:** Coordinate specialized agents into a repeatable, evidence-led hunt for in-scope smart-contract vulnerabilities. This workflow grants no authority to test, submit, or contact a program.

## Operating loop

1. **Authorize and pin** — source-pin verifies active bounty, explicit scope, source commit, clean checkout, and tool readiness. Stop on missing or mismatched input; never infer permission.
2. **Map and hypothesize** — pathway-scout maps reachable paths; hypothesis-analyst turns one invariant break into a falsifiable H-### record.
3. **Probe independently** — use only enabled, verified runners. Static, fuzz, invariant, and symbolic work may run in parallel when inputs are pinned. A scanner alert is a lead, not a finding.
4. **Normalize and challenge** — check scope, known issues, accepted risk, and citations; independent-falsifier tests the strongest benign explanation and reachability assumptions.
5. **Reproduce and review** — forge-tester authors a scoped PoC; proof-gate checks recorded runs; lead-security-auditor assembles the evidence table and review packet. The human alone decides whether to submit.

Handoffs: source-pin → pathway-scout → hypothesis-analyst → verified probes → normalize/known-issue check → citation check → independent-falsifier → PoC author → proof-gate → human review.

Existing global/agents/CONTRACT.md guards, bounty instructions, and platform rules take precedence. Do not create nested agents unless the user explicitly requests delegation. Assign one bounded task per specialist.

For cases that need a portable evidence graph, global/core/case_state.py validates a bounty-anchored, append-only snapshot. It complements existing ledgers and evidence seals; it does not replace them or certify a finding.

## Hypothesis record

Store each record under the active bounty as hypotheses/H-###.md:

    # H-### — concise claim
    - Status: OPEN | KILLED | UNRESOLVED | PROMOTED
    - Scope anchor: contract and in-scope path
    - Invariant: property that should always hold
    - Attacker: privileges and assumptions
    - Reachability: entry point → relevant calls/state changes
    - Prediction: observable behavior that would support the claim
    - Impact: bounded consequence and affected party
    - Falsifiers: strongest guard, benign explanation, and test that would disprove it
    - Evidence: artifact paths with provenance tags; distinguish source, tool, and PoC evidence
    - Decision: SUPPORTED | REFUTED | UNRESOLVED, with limits

Do not fabricate line numbers or identifiers. An untested prediction remains UNRESOLVED; lack of evidence is not refutation. Promotion from H-### to F-### requires a supported, scoped, reproducible technical claim, but does not imply severity approval or submission readiness.

## Handoff and stop rules

- Every handoff names the hypothesis/finding ID, pinned commit, allowed input paths, expected output, and unresolved questions.
- Return artifacts and a disposition, not a confidence score. Cite saved evidence and state what it does not establish.
- Record kills/refutations with the exact falsifier and preserve them in bounty history. Missing prerequisites mean UNRESOLVED/stopped, not a technical negative.
- Do not install tools, touch live-chain state, access out-of-scope targets, expose secrets, or write outside the active bounty boundary.
- No agent marks a report Ready/Submitted, contacts a program, or treats passing automation as authorization.

