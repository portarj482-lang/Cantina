# Cantina Advanced Bounty Workflows

**Version:** 1.0 · **Date:** 2026-10-10
**Companion files:** `INSTRUCTIONS.md`, `.gemini/GEMINI.md`
**Tool status:** Every scanner was MISSING at the 2026-10-10 check. **No command in this document has been run.** Commands and flags are written from tool documentation knowledge. Confirm each one with `--help` before its first use, and record the confirmed form in `global/tooling.md`.

**Runtime boundary:** Most scanner, Foundry, Cast, Anvil, and fork steps below are EVM/Solidity-specific. They do not test Solana programs. For a Solana bounty, use a Solana-capable toolchain and the environment allowed by that program; do not treat the offline TypeScript models as program execution.

---

## 0. Ground rules for every workflow

1. **Scope first.** Each workflow stage checks the SHA-256 of `scope.md` against the snapshot (W12 enforces this in code). A mismatch stops the stage.
2. **Fork-only execution.** These workflows never sign or broadcast a transaction. Banned: `cast send`, `forge script --broadcast`, and any signing prompt. Allowed on a live chain: read-only calls (`cast call`, `cast code`, `cast storage`, `cast logs`) pinned to a block number.
3. **Provenance on everything.** Every claim carries a tag from `.gemini/GEMINI.md` Part 4.3.
4. **Budgets are recorded.** Every fuzz or symbolic run logs its budget: runs, depth, time, seed, and solver timeout. A run that finds nothing within budget is recorded as `NO_COUNTEREXAMPLE_WITHIN_BUDGET`. It is never recorded as "safe" or "passed."
5. **Ledger every run.** Each run adds an entry to the matching file in `logs/`.
6. **Stop conditions are explicit.** Each workflow lists when it halts. A halt is logged, not worked around.

### 0.1 Parallelism rules

| Can run in parallel | Must run sequentially |
|---|---|
| Independent scanners (W2) | Anything that writes to a PoC or finding |
| Independent blind verifiers (W10) | Anything that changes `scope.md` |
| Read-only chain queries (W11) | Dependent steps, such as fuzz then replay |

When subagents are used, each one gets the scope path and its task only. None gets the parent's conversation.

---

## 1. Workflow map

```
            ┌──────────────── W14 memory retrieval (at every switch) ────────────────┐
            ▼                                                                        │
W8/W9 (proxy / bytecode, when applicable)                                            │
            ↓                                                                        │
W1 model ──→ W2 consensus scan ──→ W3 invariant fuzz ──→ W4 bounded proofs           │
                                        │                     │                      │
                                        └──────→ W6 hypothesis loop ←── W7 variants ─┘
                                                   │         ↑
                                     W5 fork stress ┘         W11 read-only chain watch
                                                   ↓
                                W10 blind verification ──→ W13 report + provenance audit
                                                   ↓
                                    W12 pipeline (wraps every stage above)
```

### 1.1 Selection by contract type

| Contract type | Priority workflows | Why |
|---|---|---|
| Vault (ERC-4626-style) | W1, W3, W5, W4 | Share-price and rounding invariants; donation and inflation stress |
| AMM / pricing | W1, W3, W5, W11 | Same-block manipulation; parameter ranges taken from real chain data |
| Lending / collateral | W1, W3, W5, W2 | Solvency invariants; price-drop stress |
| Upgradeable proxy | W8 first, then W1, W3 | Storage collisions and initializer exposure come before logic review |
| Bridge / messaging | W1, W6, W10 | Replay across chains; trust in relayer and message verification |
| Staking / rewards | W3, W4, W7 | Accounting identities; unchecked arithmetic; known reward-math bugs |
| Governance | W1, W6, W10 | Privilege map and timelock paths |
| Unverified deployed contract | W9 first, then W1 | Behavior is `[ASSUMPTION]` until matched to source |

---

## W1. Model-first reconnaissance

**Purpose:** Build the threat model before any scanner runs. Scanner output is then ranked against it.

**Inputs:** In-scope source at the pinned commit; `scope.md`; program docs (`[WEB]` with capture date).

**Steps:**
1. Build at the pinned commit. Record the Foundry and solc versions in `scans/<date>_model/version.txt`.
2. Run the Slither printers (verify names with `slither --help`): `human-summary`, `inheritance-graph`, `call-graph`, `vars-and-auth`.
3. Write `threat_model.md` with these sections:
   - **Assets:** balances, shares, collateral, roles, and the functions that move each one
   - **Actors:** user, admin, keeper, oracle, relayer, governance
   - **Value-flow functions:** every function that moves tokens or ETH in or out
   - **Oracle reads:** every call that reads a price or external value
   - **Privileged writes:** every state change gated by a role
   - **Trust assumptions:** each one starts as `[ASSUMPTION]`
   - **Invariants:** each one given an ID, `INV-###`, with a statement and a source
4. Promote a trust assumption to `[SRC]` or `[WEB]` only after checking it against source or docs.

**Outputs:** `threat_model.md`, plus `facts.md` entries for the contract map.

**Stop:** Any value-flow path that cannot be traced is written as `[UNKNOWN]` and listed in `state.md`. It is not skipped.

---

## W2. Multi-engine consensus scanning

**Purpose:** Prioritize findings reported by multiple different analysis engines. Agreement is a triage signal, not proof that a finding is true or that the engines are statistically independent.

**Engines in consensus:** Slither, Aderyn, Semgrep (with the chosen ruleset). Solhint is style-only and is excluded from consensus.

**Steps:**
1. Run the three engines in parallel. Each writes raw output to `scans/<date>_<tool>/`.
2. Normalize each hit to one schema:

```json
{"tool":"slither","detector":"reentrancy-eth","file":"src/Vault.sol","function":"withdraw","line":112,"native_severity":"High","raw_ref":"scans/<date>_slither/slither.json"}
```

3. Cluster hits with the function below. Hits in the same file and function, within 5 lines of each other, form one cluster. Hits with no resolved function name go into an `<unknown>` group, which is triaged by hand.

4. Sort clusters in this order:
   - (a) engines agreeing, highest first
   - (b) touches a value-flow function from `threat_model.md`, yes before no
   - (c) native severity text, used only as a tie-breaker
5. Triage each cluster as Lead, False positive (reason with `[SRC]`), Known (source), or Informational, and record it in `triage.md`.

**Stop:** A single-engine cluster outside the value-flow map is set to Informational and queued. It is not dismissed.

---

## W3. Invariant-first fuzzing with cross-engine replay

**Purpose:** Fuzz properties that come from the threat model, and confirm any counterexample on a fork before it is trusted.

**Steps:**
1. Take each `INV-###` from `threat_model.md`. Write it once as a property in each engine:
   - Foundry: an `invariant_*` function run through a handler
   - Echidna: an `echidna_*` function that returns `bool`
   - Medusa: a property test that follows its config format (confirm with `medusa --help` and its init command)
2. Use a handler to generate valid-shaped calls. Catch only expected reverts; record unexpected reverts separately because swallowing every revert can hide a violated property.
3. Set the budget: runs, depth, time limit, and seed. Write all four to the scan's `version.txt`.
4. Run each engine on the same invariant set.
5. If any engine returns a counterexample, replay the minimal sequence in Foundry on the pinned fork. Only a replayed result goes into `poc/`.
6. Record each result as one of: `COUNTEREXAMPLE` (replayed), `NO_COUNTEREXAMPLE_WITHIN_BUDGET`, or `ERROR`.

**Stop:** A counterexample that cannot be replayed is recorded as `ERROR` with the log path. It is not reported as a finding.

---

## W4. Bounded symbolic and formal checks

**Purpose:** Check arithmetic properties over explicitly stated input ranges and solver bounds. A bounded proof does not establish behavior outside those bounds.

**Targets:** `unchecked` blocks, rounding in share and price math, fixed-point conversions, and arithmetic identities from `threat_model.md`.

**Tools:**
- **Halmos:** runs `check_*` functions with symbolic inputs. Confirm the loop-bound and timeout flags with `halmos --help`.
- **Mythril:** explores paths for one function at a time, with a bounded transaction depth. Confirm the depth and timeout flags with `myth analyze --help`.
- **Certora Prover or Kontrol:** only if installed and licensed. Record the rule file used.

**Steps:**
1. Write one `check_*` function per arithmetic property, with explicit input ranges.
2. Run the solver with a timeout. Record the solver version, timeout, loop bound, and depth.
3. Record the result as one of: `PROVED_WITHIN_BOUNDS`, `REFUTED` (with counterexample and its replay), or `NO_RESULT`.

**Rules:**
- A solver timeout is `NO_RESULT`. It is never a pass.
- Every `PROVED_WITHIN_BOUNDS` entry states its bounds in full. A bound stated in a finding is part of the claim, not a footnote.

---

## W5. Parameterized fork stress

**Purpose:** Measure how accounting, collateral, and price respond across a range of parameters, on a pinned fork.

**Steps:**
1. For EVM targets, fork at the pinned block using two independently operated providers when available. For other runtimes, use their supported state snapshot or test environment; do not impose an EVM fork workflow.
2. Write one fuzzed test per scenario. The parameters are deposit size, price move (percent), time jump, and donation amount. Each one is bounded with `bound()`.
3. For Foundry EVM tests, use cheatcodes only inside test files: `deal` for balances, `warp` for time, `roll` for block number. Pin the block.
4. Mock any oracle inside a test file only. Each mock is recorded in `facts.md` as `[ASSUMPTION] mock oracle, not live feed`.
5. Write pre- and post-state measurements (balances, share price, collateral ratio) to a CSV in `scans/<date>_stress/`.
6. Derive parameter ranges from real chain data (W11) where possible, and tag them `[TOOL]`.

**Stop:** Any scenario that needs an action outside the in-scope contracts is recorded as an assumption, not a finding.

---

## W6. Hypothesis-to-PoC loop with refutation memory

**Purpose:** Turn each suspicion into a falsifiable claim. Keep the refutations, since they prevent the same dead end from being explored again.

**Hypothesis record** (in `state.md`, one line each):

```
H-### | claim | falsifiable prediction | test name | expected if true | status
```

**Status values:**
- `OPEN`: not yet tested
- `SUPPORTED`: saved, claim-specific evidence demonstrates the predicted behavior and stated impact in the authorized target/runtime. A passing test name or process exit code alone is insufficient.
- `REFUTED`: a reproducible counterexample disproves a necessary condition of the precise hypothesis. A failed test, missing prerequisite, absent deployment evidence, or lack of observed exploit is not enough by itself.
- `UNRESOLVED`: error, timeout, missing prerequisite/evidence, or unresolved disagreement

`SUPPORTED`, `REFUTED`, and `UNRESOLVED` are analysis outcomes, not finding lifecycle states. Missing evidence is `UNRESOLVED`; do not turn it into a false-positive/closed conclusion. Before reporting, build a claim-to-evidence table and have a reviewer verify that each cited artifact supports the exact wording. Tags, status fields, agent confidence scores, and generated summaries are not evidence.

**Rules:**
1. A refuted hypothesis is written to `global/refutations.md` with its claim, the reason it failed, its source tags, and its bounty slug.
2. A hypothesis cannot become a finding until it passes W10 blind verification.
3. A refutation found in one bounty is checked in other bounties through W14 retrieval. It is never copied silently.

---

## W7. Variant analysis from fixes and known issues

**Purpose:** Find sibling bugs of an issue that is already known to be fixed or excluded.

**Inputs:** The known-issues list in `scope.md`. Fix commits only from repositories listed in `scope.md`. If a repository is not listed, ask the user before using it.

**Steps:**
1. Diff the vulnerable version against the fixed version.
2. Write the root cause as one sentence.
3. Express that sentence as a Semgrep rule or a Slither detector pattern.
4. Run the rule across in-scope code only.
5. Each hit goes to triage. A supported sibling becomes a hypothesis in W6.

**Memory:** A pattern enters `global/patterns.md` only after a reproduced PoC in its source bounty (rule 4.7 in `.gemini/GEMINI.md`).

---

## W8. Upgradeable proxy and storage safety

**Purpose:** Find storage collisions, initializer exposure, and upgrade-authority problems.

**Steps:**
1. Compare storage layouts of the old and new implementations:
   `forge inspect <Contract> storage-layout --json` (confirm with `forge inspect --help`).
   Any changed, reordered, or resized slot is a candidate hypothesis.
2. Check the constructor and initializer. The implementation should block direct initialization. Confirm the project's pattern in source. On a fork, call the initializer on the implementation and expect a revert. A success is a candidate hypothesis.
3. Check who can call the upgrade function, and whether a timelock exists. Each claim is tagged `[SRC]`.
4. Read the proxy's admin and implementation slots with `cast storage <proxy> <slot> --block <pinned>`. Take the slot values from the EIP-1967 text, with a `[WEB]` tag. Do not type them from memory.
5. Search the implementation for `delegatecall` and `selfdestruct` paths.

---

## W9. Bytecode review of deployed contracts

**Purpose:** Compare a deployed EVM contract's runtime bytecode with a local build from the pinned source commit.

**Steps:**
1. Read runtime bytecode: `cast code <addr> --block <pinned>`.
2. Compile the local source and get its runtime bytecode: `forge inspect <Contract> deployedBytecode` (confirm with `forge inspect --help`).
3. Compare using compiler metadata and immutable-reference information, plus matching compiler version, settings, library links, and constructor arguments where applicable. A manual metadata strip and placeholder replacement alone is not conclusive.
4. **Match:** record the exact comparison method and result. A bytecode match supports correspondence with that build; it does not prove the source is safe or cover proxy/delegatecall behavior.
5. **Mismatch:** this comparison did not match the selected build; it does not by itself prove the deployment is unverified. Check build settings, linked libraries, immutables, and verified-source metadata. Decompiled output is an interpretation, not source code.

**Stop:** Addresses not listed in `scope.md` are not analyzed. They are not tested.

---

## W10. Blind verification

**Purpose:** Separate the author of a claim from an independent reviewer when an authorized reviewer is available.

**Steps:**
1. When a separate reviewer is available and its use is authorized, provide only these inputs:
   - The claim text
   - The path to `scope.md`
   - The commit hash
   - The PoC file path
2. Do not pass the hypothesis history, the conversation, or the author's conclusions.
3. The subagent must:
   - Run the PoC in the target runtime's permitted environment, and compare independent providers when applicable. Report the assertion result and provide raw logs.
   - Write one counter-test for each precondition the claim relies on, and report whether it passes
4. Its report goes into the finding file under a "Blind verification" heading, with its own tags.
5. Any disagreement between the verifier and the author sets the finding to `Unconfirmed`.

**Limit:** A subagent built on the same model can share the author's blind spots. Blind verification lowers self-grading. It does not remove the need for human review before submission.

---

## W11. Read-only chain watch

**Purpose:** Gather real-world state (parameter ranges, event history, storage values) at pinned blocks, without any write.

**Allowed commands:** `cast call`, `cast code`, `cast storage`, `cast logs` (confirm flags with `cast <cmd> --help`), and trace queries if the provider supports them.

**Forbidden:** `cast send`, `forge script --broadcast`, and anything that prompts for a signature. Stop on any signing prompt.

**Steps:**
1. Record the query, block range, and provider label.
2. Save output to `scans/<date>_chainwatch/`, with the SHA-256 of each file.
3. Log each run in `logs/scan_ledger`.

**Use:** Values from this workflow feed W5 sweeps and W8 slot checks. They are tagged `[TOOL]` or `[WEB]`.

---

## W12. Pipeline runner (partial automation)

**Purpose:** Run a limited set of build, scanner, fuzz, PoC, scope-verification, and provenance-audit stages with logs. The script does not implement or wrap W1 through W13, and a successful stage does not imply the full workflow passed.

### 12.1 Pinning

| Item | Pin | Record |
|---|---|---|
| Compiler | `solc-select` version | `version.txt` |
| Foundry | `forge --version` output | `version.txt` |
| Python | `python --version` and a locked environment when one is used | Scan folder |
| Fuzz seed | `FUZZ_SEED` environment variable | Ledger entry |
| Scope | SHA-256 snapshot | `snapshots/scope.sha256` |

### 12.2 Scope snapshot

`scope.md` must contain exactly one pair of these marker lines around the scope text:

```
<!-- SCOPE START -->
...scope text, verbatim...
<!-- SCOPE END -->
```

Generate the snapshot with the same command the script uses:

```bash
sed -n '/<!-- SCOPE START -->/,/<!-- SCOPE END -->/p' bounties/<slug>/scope.md | sha256sum | cut -d' ' -f1 > bounties/<slug>/snapshots/scope.sha256
```

### 12.3 Pipeline script

The checked-in `global/tools/run_pipeline.sh` supports `verify`, `build`, `scan`, `fuzz`, `poc`, and `gate`. It infers `BOUNTY_ROOT` and `GLOBAL_DIR` from its location unless overridden. `FUZZ_SEED` is required only for `fuzz`; `SEMGREP_RULES` only for `scan`; `FINDING`, `PINNED_BLOCK`, `RPC_URL_A`, and `RPC_URL_B` only for the EVM `poc` stage. Run build/test commands from the isolated target checkout while setting the bounty metadata root separately. The `gate` stage runs only the provenance audit.

---

## W13. Report generation with provenance enforcement

**Purpose:** Find untagged claim sentences and selected wording in finding files. This script is diagnostic and is not connected to a submission platform; it cannot prevent submission or verify tagged claims.

**Steps:**
1. Fill the finding template from `.agents/skills/cantina-bug-bounty/references/finding_template.md`. Quote the applicable severity criteria from `scope.md`.
2. Run the audit stage: `run_pipeline.sh <slug> gate`.
3. Fix each flag. Flags are not dismissed. A removed or corrected claim is logged.

4. Separately review a claim-to-evidence table for semantic support. The tag audit does not check whether a citation says what the claim asserts, whether a test exercised the real entry point, or whether the target state and impact were authenticated. Never treat a clean tag audit as a factuality or readiness result.

Save audit script as `global/tools/provenance_audit.py`.

---

## W14. Memory-driven workflow

**Purpose:** Use what past bounties recorded, and make visible what influenced an analysis.

**At every switch:**
1. Read `global/refutations.md` and `global/patterns.md`. Filter by the contract types in `threat_model.md`.
2. Write a `MEMORY_RETRIEVED` entry to the session ledger. It lists each file read and each entry used, so an audit can show what shaped the work.
3. Mark any entry tied to an old commit or scope hash as `STALE` until it is re-verified.

**Before each new hypothesis (W6):**
- Search `global/refutations.md` for the same claim. If a match exists, record the match and its reason. Do not re-test without a new reason.

**Cross-bounty use:**
- Use `/cross-check <slug> <question>` for one question at a time. Every cross-check is logged in both bounties' switch ledgers.

**Periodic consolidation:**
- After every fifth session, or when `state.md` exceeds 300 lines, write a summary block at the top of `state.md`. Archive older entries. Delete nothing.

---

## 2. Failure modes to watch for

| Failure | How it shows up | Guard |
|---|---|---|
| Overclaiming silence | A fuzz run with no counterexample is reported as "secure" | Use `NO_COUNTEREXAMPLE_WITHIN_BUDGET` with its budget (rule 0.4) |
| Mock hides the bug | A stress test passes only because the mock oracle is well-behaved | Every mock is `[ASSUMPTION]`; stress uses a live-derived range (W11) |
| Duplicate scanner noise | The same bug appears in three engines' output, counted three times | Cluster by (file, function, window) before counting (W2) |
| Shared blind spots | The verifier accepts the author's reasoning | Fresh context and a counter-test per precondition (W10) |
| Fork drift | Two providers return different state at the same block | Dual-plane check fails the run (W12, exit 5) |
| Flaky time-based tests | `warp` results change between runs | Pin the seed; record the block timestamp in the PoC log |
| Misread decompiled code | Heimdall output treated as source | Decompiled claims stay `[ASSUMPTION]` until checked (W9) |
| Unverified flags | A command fails because a flag was wrong | Confirm every flag with `--help` before first use (section 0) |

---

## 3. Install order

Install in this order, and run `/tool-check` after each step:

1. Foundry (forge, cast, anvil): needed by W3, W5, W6, W8, W9, W11, W12
2. Slither: W1, W2, W12
3. Aderyn: W2, W12
4. Semgrep: W2, W7, W12
5. Echidna and Medusa: W3
6. Halmos: W4
7. Mythril: W4
8. Heimdall-rs: W9
9. Certora or Kontrol: W4, only if licensed

**Status after each install:** A tool is OK only after `/tool-check` records its version in `global/tooling.md`.
