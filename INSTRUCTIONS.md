# Cantina Bug Bounty Operating Manual

**Version:** 2.0 · **Re-engineered:** 2026-10-10 · **Replaces:** the earlier "Leap Layer" instruction set (see Appendix B)

---

## 0. Scope of this manual

This manual governs the assistant's work on bug bounties hosted on Cantina. It covers:

- Keeping one bounty in focus at a time, with memory that persists across sessions as files.
- Smart-contract scanning with the tools in Section 7.
- A verification process in which every claim traces to a source.

What it does not do:

- It does not make claims true. It makes unsourced claims visible and blocks them from reaching a submission.
- It does not grant permission to test anything. Scope comes only from the program's own rules page.
- Its memory is files on disk. If those files are deleted or the environment resets, the memory is gone. Back them up with "export memory".

---

## 1. Non-negotiable rules

1. **Authorized scope only.** Test only the targets, chains, and addresses listed as in scope in the active bounty's `scope.md`. Anything not listed is out of scope.
2. **No live-funds action.** Exploit work runs on a local fork (`anvil --fork-url ... --fork-block-number ...`) or a testnet, unless the program rules explicitly allow otherwise and the user confirms. Never send a state-changing transaction to a live mainnet contract.
3. **Fail closed.** If a required target, chain, or severity rule is missing or ambiguous, stop before testing and ask. A repository commit is required only when the program identifies source code as the target; do not invent a commit when the program names only a deployment.
4. **One bounty in focus.** Only the active bounty is read or written during bounty work. Global workflow and tool documentation may be read when needed; cross-bounty facts still require a logged `cross-check`. See Section 4.
5. **Sourced claims only.** Every factual statement in a finding carries a provenance tag (Section 2.6). If there is no source, write `[UNKNOWN]`. A tag records provenance; it does not prove the claim is true.
6. **Confidentiality.** Findings leave the bounty folder only as a submission through the program's platform. Nothing from one bounty is used in another except through the logged `cross-check` command.
7. **Clean up.** When a session ends, stop fork nodes and background processes, and delete temporary files that hold keys or RPC secrets. Never store a real private key in this folder. Use throwaway test keys only.
8. **No public disclosure.** Do not publish, post, or summarize findings outside the platform unless the program explicitly permits it.

---

## 2. Memory architecture

### 2.1 Memory types

| Type | Where it lives | Lifetime | Purpose |
|---|---|---|---|
| Working | The current conversation | Session | What the assistant is doing right now |
| Session journal | `bounties/<slug>/journal.md` | Permanent, append-only | What happened, in order, with dates |
| Bounty state | `bounties/<slug>/state.md` | Rewritten on every switch, pause, and session end | Status, next step, open questions |
| Semantic facts | `bounties/<slug>/facts.md` | Permanent | Verified facts about this codebase |
| Findings | `bounties/<slug>/findings/F-###.md` | Permanent | Each candidate issue and its status |
| Scan records | `bounties/<slug>/scans/` | Permanent | Raw tool output with the command and version used |
| Global patterns | `global/patterns.md` | Permanent | Vulnerability patterns verified in past work |
| Playbooks | `global/playbooks/` | Permanent | Procedures that have worked once and were recorded |
| Tool registry | `global/tooling.md` | Permanent | Installed tools, versions, flags verified with `--help` |
| Lessons | `global/lessons.md` | Permanent | Mistakes and their corrections, one line each |
| Index | `MEMORY.md` | Permanent, kept under 200 lines | Active bounty pointer and list of all bounties |

### 2.2 Directory layout

```
cantina-bounty/
├── MEMORY.md                      # index + active bounty pointer
├── INSTRUCTIONS.md                # this manual
├── WORKFLOWS.md                   # advanced bounty workflows W1-W14
├── global/
│   ├── patterns.md
│   ├── tooling.md
│   ├── lessons.md
│   ├── refutations.md
│   ├── playbooks/
│   └── tools/
└── bounties/
    └── <slug>/
        ├── scope.md               # rules copied verbatim + SHA-256 of that text
        ├── state.md
        ├── facts.md
        ├── journal.md
        ├── findings/F-001.md ...
        ├── scans/<date>-<tool>/   # command, version, raw output, triage
        └── poc/                   # Foundry tests for findings
```

### 2.3 Retrieval rule

Before answering any question about a bounty, the assistant reads `MEMORY.md`, then that bounty's `state.md`, then `facts.md`. It does not answer from chat recall alone. If a needed file is missing, it says so.

### 2.4 Write rule

- A verified fact is written to `facts.md` in the same turn it is established.
- Every scan writes its output to `scans/` before its results are discussed.
- Every session that changes anything appends one entry to `journal.md`.
- `state.md` is rewritten at the end of each session and on every switch.

### 2.5 Consolidation, conflict, staleness, retraction

- **Consolidation:** when `journal.md` exceeds about 300 lines, the assistant writes a summary block at the top of `state.md` and moves the older entries to `journal-archive-<year>.md`. Nothing is deleted.
- **Conflict:** if two sources disagree, both are kept in `facts.md` with their sources. The newer verified source is marked `CURRENT`. The older one is marked `SUPERSEDED by FACT-###`.
- **Staleness:** if the scope hash or the reviewed commit changes, every fact tied to the old commit is marked `STALE` until re-verified. Stale facts are not used in findings.
- **Retraction:** on "forget <fact>", the entry is marked `RETRACTED` with a date and reason. It is not removed.

### 2.6 Provenance tags

Every factual statement in findings, `facts.md`, and reports carries one of these tags:

- `[SRC: path:line @commit]`: read from source code at a named commit
- `[LOCAL: path:line, provenance unpinned]`: inspected local harness, generated artifact, or file not authenticated to a named commit; this must never be presented as upstream or deployment evidence
- `[TOOL: scans/<dir>/<file>]`: output of a tool run, with the saved file
- `[POC: poc/<file> PASS|FAIL]`: result of a reproduction test
- `[WEB: url, captured YYYY-MM-DD]`: from a web page, with capture date
- `[USER: stated, unverified]`: the user said it; the assistant has not checked it
- `[ASSUMPTION]`: reasoning without evidence; must be verified before use
- `[UNKNOWN]`: not established

A tag records provenance; it does not prove that the source supports the claim. For `[LOCAL]` artifacts, preserve a SHA-256 and git status when available, describe only what the local file contains, and do not attribute it to a pinned upstream revision unless separately authenticated.

### 2.7 Memory commands

- **"remember <fact>"** writes to `facts.md` tagged `[USER: stated, unverified]`.
- **"what do you know about <topic>"** lists matching entries from `facts.md` and `findings/` with their tags and file paths.
- **"forget <fact>"** marks the entry `RETRACTED`.
- **"export memory"** writes `export-<date>.md`, a single snapshot of the active bounty.
- **"audit memory"** lists every file in the active bounty folder with its last-modified date and any `STALE` or `RETRACTED` markers.

---

## 3. First-run setup

Run once, from the working directory:

```bash
mkdir -p cantina-bounty/global/playbooks cantina-bounty/bounties
```

Create `cantina-bounty/MEMORY.md` with:

```
# Memory index
Active bounty: none
Last switch: none
Known bounties: none
```

Create `cantina-bounty/global/tooling.md` from the table in Section 7.1. Every status stays `UNCHECKED` until the version check has run.

---

## 4. Single-bounty focus and the switch protocol

### 4.1 Commands

| Command | Effect |
|---|---|
| `switch bounty to <slug>` | Saves the current bounty, verifies and loads the new one (4.2) |
| `new bounty <slug>` | Creates the folder from templates. Requires the scope text before anything else |
| `status` | Shows active bounty, scope hash, commit, last step, open items |
| `pause` | Saves state and stops all scans and forks |
| `close bounty` | Requires a final status (Submitted, Accepted, Duplicate, Rejected, Out of scope, Abandoned). Then archives the folder |
| `cross-check <slug> <question>` | Reads one named file from another bounty to answer one question. Logs the access in both journals |

### 4.2 Switch steps, in order

1. **Save the outgoing bounty.** Rewrite its `state.md`. Append a `SWITCH OUT` entry to its `journal.md`. Stop any running fork or scan.
2. **Check the target.** Confirm `bounties/<slug>/` exists. If it does not, say so and offer `new bounty`. Do not create it silently.
3. **Load the target.** Read, in order: `scope.md`, `state.md`, `facts.md`, and the open findings in `findings/`.
4. **Verify the scope hash.** Recompute the SHA-256 of the LF-normalized marker-delimited block in `scope.md` and compare it with `snapshots/scope.sha256`. A mismatch marks the bounty `SCOPE CHANGED` and blocks new testing until scope is reviewed.
5. **Lock focus.** Update `MEMORY.md` with the new active bounty. Only this folder is read or written until the next switch.
6. **Brief the user.** Reply with five lines: bounty name, scope status, commit under review, last step, next step. Then ask for the next action.

### 4.3 Focus lock

While a bounty is active:

- Every reply begins with `[Active: <slug>]`.
- Scans, PoCs, and notes are written only inside `bounties/<slug>/`.
- A target address from another bounty is refused unless the user runs `cross-check`.
- If the user asks about a different bounty without switching, the assistant asks: "Switch to <slug>, or answer about <active slug>?"
- With no active bounty, the assistant does not run scans. It asks the user to choose or create one.

---

## 5. Phase 1: Intake and scope lock

Capture these from the program page and copy them verbatim into `scope.md`. Do not paraphrase:

- Platform, program name, program URL, and capture date
- In-scope contracts: name, address, and chain; record a source repository and commit only when the program or authoritative project source identifies them. Otherwise record `NOT PROVIDED`.
- Out-of-scope items, including excluded classes and known-issue lists
- Severity scale and its definitions, copied exactly
- Reward and eligibility rules
- Disclosure and communication rules
- Prior reports or duplicates list, if the program publishes one
- Any rule about testnets, forks, or test accounts

Compute the SHA-256 of the LF-normalized marker-delimited block and store it in `snapshots/scope.sha256`. Keep the program's copied text unchanged; record missing items outside the markers as `NOT PROVIDED BY PROGRAM`. Do not start testing until the in-scope target, network, and applicable rules are established. Other items the program does not provide are recorded as missing, not guessed.

---

## 6. Phases

The four-phase sequence from the earlier document is kept. Its content is now bounty work.

**Phase 1: Intake and scope lock.** Section 5.
Exit: `scope.md` complete, hash stored, user has confirmed scope.

**Phase 2: Reconnaissance and tooling.**
- Fetch the exact commit in scope and confirm it matches.
- Build and test with tools for the target runtime. Use Foundry/Hardhat for EVM projects and the appropriate Solana toolchain for Solana programs. Record the actual compiler or tool versions used.
- Map the contracts: entry points, privileged roles, external calls, oracles, token assumptions, upgrade paths, initializers.
- Run the version check in Section 7.1 and update `global/tooling.md`.
- Exit: contract map in `facts.md`, tool results saved in `scans/`.

**Phase 3: Analysis.**
- Automated: run the scanners in Section 7.2, save raw output, triage every result (7.3).
- Manual: walk each entry point against the checklist in 7.4.
- Dynamic: write invariant or fuzz tests (7.5) for every property the protocol claims to keep.
- Every lead becomes `findings/F-###.md` with status `Lead`. Scanner output alone is never a finding.

**Phase 4: Verification and reporting.**
- Reproduce each lead with a PoC in `poc/` on a pinned fork. Save the command and output.
- Pass the verification gates (8.2).
- Write the report in the platform's format, using only the severity scale in `scope.md`.
- Submit through the platform only. Record the submission ID in `state.md`.

---

## 7. Smart-contract scanning toolkit

The scanner table below is primarily for EVM/Solidity projects. It does not provide a Solana program-analysis toolchain. For non-EVM targets, select tools that support the target runtime and record their versions before use; Foundry, Cast, Anvil, Slither, and Solidity compilers do not establish Solana program behavior.

### 7.1 Tool table and status

A status is the result of a version check, not an assumption. Last checked: **2026-10-23**, via `scripts/check-tool-versions.sh` with PATH expanded to include `$HOME/.foundry/bin`, `$HOME/.cargo/bin`, and `$HOME/.local/bin`.

| Tool | Type | Use it for | Install | Check | Status (2026-10-23) | Version |
|---|---|---|---|---|---|---|
| Foundry (forge, cast, anvil, chisel) | EVM test framework, fork node, chain tools | EVM unit, fork, fuzz, invariant tests; PoCs | `curl -L https://foundry.paradigm.xyz \| bash && foundryup` | `forge --version` | OK | 1.8.5 |
| cast and block explorers | Chain queries | Reading state, storage slots, verified source | Included with Foundry | `cast --version` | OK | 1.8.5 |
| anvil | Local fork node | Fork testing against pinned blocks | Included with Foundry | `anvil --version` | OK | 1.8.5 |
| chisel | Solidity REPL | Interactive Solidity snippet testing | Included with Foundry | `chisel --version` | OK | 1.8.5 |
| cargo / rustc | Rust compiler & package manager | Building Rust clients and Solana BPF programs | System / rustup install | `cargo --version` | PRESENT | 1.94.1 |
| Anchor CLI | Solana framework | Building and testing Anchor programs | `cargo install --git https://github.com/coral-xyz/anchor anchor-cli` | `anchor --version` | OK | 1.0.0 |
| Solana CLI (solana, validator) | Solana test validator & chain tools | Local cluster execution and account dumping | Solana install script | `solana --version` | OK | 1.18.4 |
| python3 | Runtime | Test harnesses, engine and scope validation | System install | `python3 --version` | PRESENT | 3.12.3 |
| git | Source control | Commit verification and archive extraction | System install | `git --version` | PRESENT | 2.43.0 |
| Slither | Static analysis (Trail of Bits) | Detectors, call graphs, inheritance, printers | `pip install slither-analyzer` | `slither --version` | MISSING | — |
| Aderyn | Static analysis (Cyfrin) | Fast detector pass | `cargo install aderyn` | `aderyn --version` | MISSING | — |
| Semgrep | Pattern matching | Custom Solidity rules | `pip install semgrep` | `semgrep --version` | MISSING | — |
| Mythril | Symbolic execution | Searching for reachable bad states | `pip install mythril` | `myth version` | MISSING | — |
| Echidna | Property fuzzer (Trail of Bits) | Fuzzing invariants you write | GitHub releases, crytic/echidna | `echidna --version` | MISSING | — |
| Medusa | Parallel fuzzer (Trail of Bits) | Fuzzing with Foundry-style tests | GitHub releases, crytic/medusa | `medusa --version` | MISSING | — |
| Halmos | Symbolic testing for Foundry tests | Checking properties over symbolic inputs | `pip install halmos` | `halmos --version` | MISSING | — |
| Solhint | Linter | Style and common-mistake rules | `npm install -g solhint` | `solhint --version` | MISSING | — |
| solc | Compiler | Matching project compiler versions | `pip install solc-select && solc-select install <ver>` | `solc --version` | MISSING | — |
| Certora Prover | Formal verification (commercial) | Rule-based proofs; needs a license | `pip install certora-cli` | `certoraRun --version` | MISSING | — |
| Kontrol | Formal verification (Runtime Verification) | Proofs over Foundry tests | Runtime Verification install guide | `kontrol --version` | MISSING | — |
| Heimdall-rs | Bytecode decompiler | Recovering ABI and logic from bytecode | heimdall-rs install docs | `heimdall --version` | MISSING | — |
| node / npm | Runtime & package manager | Running JS/TS tools | System install | `node --version` | MISSING | — |
| tsx | TypeScript runner | Executing TypeScript PoCs | `npm install -g tsx` | `tsx --version` | MISSING | — |

### 7.2 Automated scanner execution

Automated scanners are executed via `./scripts/run-scanner.sh` or directly with confirmed flags. All scanner commands default to `--dry-run` and must record raw execution logs to `scans/<date>-<tool>/`.

- **Slither:** `./scripts/run-scanner.sh --tool slither --target <path> --out scans/<date>-slither/report.json`
  - Visual printers: `slither <target> --print call-graph`, `slither <target> --print inheritance-graph`
- **Aderyn:** `./scripts/run-scanner.sh --tool aderyn --target <path> --out scans/<date>-aderyn/report.md`
- **Semgrep:** `./scripts/run-scanner.sh --tool semgrep --target <path> --out scans/<date>-semgrep/report.json`
- **Foundry (Forge):** `./scripts/run-scanner.sh --tool forge --target <path> --out scans/<date>-forge/test.log`
- **Anchor (Solana):** `./scripts/run-scanner.sh --tool anchor --target <path> --out scans/<date>-anchor/test.log`

Never execute scanners against live mainnet endpoints. All execution runs against local source checkouts or local forks.

### 7.3 Scanner triage protocol

Raw scanner output is NEVER a finding on its own. Every alert must be triaged according to this protocol before promotion:

1. **Intake & Archival:** Save raw tool output to `bounties/<slug>/scans/<date>-<tool>/` and tag claims with `[TOOL: scans/<date>-<tool>/<file>]`.
2. **False Positive Filter:** Evaluate each finding against the contract source and business logic:
   - Does the reported issue violate an intended protocol invariant or is it an accepted trade-off?
   - Is the vulnerable code path guarded by access control, reentrancy locks, or internal visibility?
   - If discarded as a false positive, document the refutation in `facts.md` or `scans/<date>-<tool>/triage.md` with explicit justification.
3. **Lead Promotion:** If the alert represents a plausible, unmitigated attack vector:
   - Create `findings/F-###.md` with initial status `Lead`.
   - Record the candidate severity matching the exact scale in `scope.md`.
   - Formulate a testable security hypothesis `H-###`.

### 7.4 Manual review checklist

For every in-scope entry point and contract, systematically walk through the following security domains:

1. **Access Control & Authorization:**
   - Are privileged functions guarded by `onlyOwner`, timelocks, or multi-signatures?
   - Can initializers or upgrade proxies be front-run or called repeatedly?
   - Are signature validations protected against cross-chain and nonce replays (EIP-712 / ERC-1271 / ERC-6492)?
2. **Reentrancy & State Invariants:**
   - Does all state mutation strictly follow Checks-Effects-Interactions (CEI)?
   - Are external interactions vulnerable to read-only or cross-function reentrancy?
3. **Arithmetic, Token & Accounting Invariants:**
   - Are token transfer amounts validated for fee-on-transfer, rebasing, or non-standard returns?
   - Can first-depositor share inflation grief vault pricing?
   - Is token conservation maintained monotonically across deposit, mint, burn, and withdraw flows?
4. **Oracle & Timestamp Dynamics:**
   - Are price feeds checked for staleness, round completeness, and min/max circuit breaker bounds?
   - Can block timestamps or sequencer downtime be manipulated to bypass maturity delays?
5. **Bridge & Cross-Domain Messaging:**
   - Are message relays validated to ensure sender aliasing cannot be spoofed?
   - Can failed messages be retried without double-spending or replaying value transfers?

### 7.5 Dynamic property & invariant testing

Formulate invariants as executable Forge / Echidna test suites in `poc/` or `test/invariants/`:

1. **Define the Invariant:** Express the protocol guarantee as a mathematical condition (e.g., `totalAssets() >= totalShares()`, `isSolvent == true`).
2. **Implement Fuzz Harness:** Construct stateful test handlers constraining inputs to valid domain ranges while maximizing actor concurrency.
3. **Execute & Record:** Run fuzz campaigns with high call depth (`forge test --match-path test/invariants/ -vvv`).
4. **Triage Broken Invariants:** If an invariant reverts or assertion fails, isolate the minimal transaction sequence, record raw logs to `poc/` or `scans/`, and promote to an executable exploit PoC under Phase 4.

---

## 8. Findings

### 8.1 Status lifecycle

`Lead` → `Unconfirmed` → `Draft` → `Ready` → `Submitted` → one of `Accepted`, `Duplicate`, `Rejected`, `Out of scope`, `Informational`.

Keep analytical outcome separate from execution and administrative status. A passing process/test means only that the command exited and its assertions passed; it is not by itself proof that the claimed vulnerability occurred. Mark a hypothesis `SUPPORTED` only when saved evidence demonstrates the complete claimed behavior and impact. Mark it `REFUTED` only when a reproducible counterexample disproves a necessary condition. If scope, deployment, signature, downstream-consumer, or impact evidence is missing, the result is `UNRESOLVED`, not `REFUTED`. Never infer a finding lifecycle state from an agent's status label.

### 8.2 Verification gates

1. **Source gate.** Every code claim has a `[SRC: path:line @commit]` tag. The assistant re-reads the line at that commit to confirm it.
2. **Reproduction gate.** A PoC in the target runtime's test framework reproduces the claimed behavior in an environment allowed by the program. Save the command and raw output. A test marked PASS means its assertions passed; interpret the assertions to determine whether the vulnerability was reproduced. Without a reproduced exploit, a finding is at most `Unconfirmed`.
3. **Scope gate.** The affected contract, address, and chain appear in `scope.md` as in scope.
4. **Duplicate gate.** Check the program's known-issue list and published reports when available. Record what was checked, with URL and capture date. Missing lists are recorded as unavailable; they are not treated as a clean duplicate check.
5. **Severity gate.** Severity is assigned only with the scale copied into `scope.md`. Impact and likelihood are stated in that scale's terms.
6. **Provenance gate.** Every sentence in the report carries a tag. An untagged claim is removed, or tagged `[ASSUMPTION]` and the finding stays in `Draft`.

Before drafting a verdict, make a claim-to-evidence table for every material claim: exact claim, artifact and line/output location, what it establishes, limitations, and status (`SUPPORTED`, `REFUTED`, `UNRESOLVED`). A provenance tag identifies a source; it does not prove the claim is true or that the source supports it. Model output, agent summaries, test names, process exit codes, caller-supplied booleans, and database status fields are leads to inspect, not evidence. Absolute claims (`all`, `never`, `impossible`, `confirmed`, `closed`), gate scores, deployment state, and economic impact require primary artifacts establishing that exact statement. Preserve conflicting evidence and leave the claim `UNRESOLVED` until reconciled.

---

## 9. Templates for state, journal, and facts

### 9.1 state.md

```markdown
# State: <slug>
Updated: <date time PT>
Scope hash: <sha256>   (matches scope.md: yes / no)
Commit under review: <hash>
Phase: <1 to 4, and sub-step>
Last step: <one line>
Next step: <one line>
Open questions:
- ...
Findings: F-001 (Lead), F-002 (Draft), ...
Blocked on: <none, or description>
```

### 9.2 journal.md entry

```markdown
## 2026-10-10 14:05 PT | <SESSION | SCAN | POC | SWITCH IN | SWITCH OUT | NOTE>
- What:
- Files:
- Result:
- Next:
```

### 9.3 facts.md entry

```markdown
- FACT-014: Vault share price is computed from balanceOf(this) with no offset. [SRC: src/Vault.sol:112 @abc1234] Status: CURRENT, captured 2026-10-10.
```

---

## 10. Output rules in chat

- First line of each reply during a bounty session: `[Active: <slug>]`.
- Claims about code cite `path:line`. If the file was not read this session, read it first.
- Claims about tool output name the saved file.
- Claims about the live chain name the block number and the RPC source. If not checked, say "not checked."
- When uncertain, say "I don't know" or "unverified," then state what would settle it.
- Program rules are never restated from memory. Quote the stored `scope.md`.
- Keep prose short. Use a table when comparing tools or findings.

---

## 11. Reuse and lessons

- A pattern moves from a bounty to `global/patterns.md` only after it has a passing PoC in its source bounty and a note on how it generalizes. Each pattern cites its source bounty. Using it in another bounty still goes through the logged `cross-check` rule.
- A playbook is written only after a procedure has worked once and been recorded in a journal.
- `global/lessons.md` records mistakes (wrong severity, rejected findings, tool misuse). One line each, with a date and a link to the journal entry.
