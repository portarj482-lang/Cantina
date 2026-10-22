# Verified Vulnerability Patterns

Entries in this file represent vulnerability patterns verified in past bounties with a passing PoC. Each entry cites its source bounty and explains how it generalizes.

**Location:** `cantina-bounty/global/patterns.md`
**Entries:** 0 (as of 2026-10-10). No bounty has been run in this workspace, and no PoC has passed.
**Promotion rules:** `cantina_GEMINI.md` rule 4.7 and `cantina_advanced_workflows.md` W7.

---

## 1. Admission rules

A pattern enters this file only when every rule below holds:

1. **Source finding is ready.** The source finding (`bounties/<slug>/findings/F-###.md`) has all six readiness gates passed, 6 of 6, recorded in `logs/gate_ledger.jsonl`.
2. **PoC passes on both planes.** The PoC passed on both pinned forks with divergence count 0. The `poc_ledger` entries exist and are referenced in the entry.
3. **Source bounty is named.** The entry cites the bounty slug. A program name alone is not enough, because the same program can run more than one bounty.
4. **Generalization is written.** The entry includes the "Applies when", "Does not apply when", and "Generalization" fields, and the user has reviewed them.
5. **No duplicate.** If a matching entry exists, update that entry with a note instead of adding a second one.
6. **Promotion is logged.** The source bounty's `logs/session_ledger` gets a `PATTERN_PROMOTED` event with the entry ID.

**Outcome does not block admission.** A finding can pass all six gates and still be rejected by the program. The outcome is recorded in the entry. If the program gave a reason, quote it. Use `Out of scope` or `Rejected` with the reason, and do not drop the entry.

**Passing the PoC does not mean the program will accept the finding.** An entry records that the code behaves as the PoC asserts. It does not record the program's decision.

---

## 2. Rules for generalizing a pattern

- State the root cause in one sentence about the code, not about the program or protocol.
- List the code features required for the pattern to occur. Each feature is tagged `[SRC]` at the commit where it was observed.
- List the conditions under which the pattern does not apply, with the source for each. These negative conditions are as important as the positive ones.
- Name the detection signal: a Semgrep rule ID or a Slither detector pattern. Record how many files it was run against and what it matched.
- Record the triage counts from the source bounty: matched, confirmed, false positives. Use the counts from `triage.md`. If counts were not recorded, write "not measured". Do not estimate.
- Claims about how common a pattern is across protocols need a `[WEB]` tag with a capture date. Without one, leave the claim out.

---

## 3. Matching a pattern in a new bounty

A match against a pattern in this file is a hypothesis, not a finding.

1. Run the detection signal against the new bounty's in-scope code (W7).
2. Record each match as an `H-###` hypothesis (W6).
3. Run `/cross-check <source-slug> <question>` if the entry's evidence is needed. Log the read in both bounties.
4. Confirm the pattern's preconditions in the new code, with `[SRC]` tags, before writing a PoC.
5. A new PoC is written and must pass on both planes before any finding is created.

The preconditions in the new code can differ from the source bounty. Check each "Applies when" item again.

---

## 4. Retraction

- An entry found to be wrong is marked `RETRACTED` with the date and the reason. It is never deleted.
- A retracted entry stays in the file so a later bounty can see why the pattern was dropped.
- If a retraction changes the admission basis of other entries, mark those entries `UNDER REVIEW` and list them in the change log.

---

## 5. Entries

**No entries yet.** Add entries below this line only after section 1 is satisfied for each one.

---

## 6. Entry template

> TEMPLATE. This block is not an entry and must not be counted as one. Copy it below section 5 only when admission is complete.

```markdown
### PAT-### : <short pattern name>

- **Status:** VERIFIED | UNDER REVIEW | RETRACTED
- **Promoted:** YYYY-MM-DD
- **Source bounty:** <slug>, finding F-###
- **Source program:** <program name as written in that bounty's scope.md>
- **Commit reviewed:** <hash>
- **Gate result:** 6 of 6 (gate_ledger entry: <id>)
- **PoC evidence:** poc/F-###_<slug>.t.sol, [POC: PASS, providers A and B, block <n>, poc_ledger entries: <ids>]
- **Outcome:** <Submitted | Accepted | Duplicate | Rejected | Out of scope | Informational>. Reason: <quoted from the program, or "not yet known">
- **Root cause (one sentence):** <claim> [SRC: path:line @commit]
- **Applies when:**
  - <required code feature> [SRC: path:line @commit]
- **Does not apply when:**
  - <negative condition> [SRC: path:line @commit or ASSUMPTION]
- **Detection signal:** <Semgrep rule ID or Slither detector pattern>, run on <n> files in <slug>
- **Triage counts:** matched <n>, confirmed <m>, false positives <k> (scans/<dir>/triage.md)
- **Generalization:** <two to four sentences on why the pattern recurs and what varies between protocols>
- **Retraction notes:** none
```

---

## 7. Change log

| Date | Action | Entries after | Reason |
|---|---|---|---|
| 2026-10-10 | File created with admission rules, generalization rules, and template | 0 | No bounty has been run; no PoC has passed |