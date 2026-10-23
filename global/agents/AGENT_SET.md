# Cantina Agent Set, v1.0 (draft)

**Date:** 2026-10-10
**Status:** Nothing here has been run. `global/tooling.md` lists every scanner as MISSING, so every executor stops at its first step until its tool is installed and checked.
**Source:** role specifications in `global/agents/`. The registry currently contains 51 role profiles (49 executable capability profiles matching `security-mesh` `AGENT_REGISTRY` + 2 specialized reasoning roles in `bug-hunting-system.md`), including five Solana extensions. Reconciled via `scripts/reconcile-registries.ts`.
**Layout:** `CONTRACT.md` is the shared policy; each role has a profile file and a unique learning/playbook entry in `PLAYBOOKS.md`. Agents read the shared contract, own profile, and matching playbook before role work.

---

## Part A. Shared contract

`inheritCustomizations` is `false` on every agent, so agents do not inherit this file by default. Each agent's first step is to read `global/agents/CONTRACT.md`, its own profile, and the matching `global/agents/PLAYBOOKS.md` entry. If any are missing, the agent stops.

- **A1. Focus.** Read `MEMORY.md` for the active slug. Read only inside `bounties/<slug>/`, the checkout at `repo_path` (read-only commands only), and the global files their own rules allow. Write only inside `bounties/<slug>/` (A11). Agents read `global/refutations.md` and `global/patterns.md` only for their generalized entries (GEMINI Part 3.3). Full records are read only through `/cross-check`.
- **A2. Fail closed.** Stop and write a stop record (step, field, reason) when any of these hold:
  - a field the agent needs is missing from `analysis` in the manifest;
  - the scope hash does not match `snapshots/scope.sha256`;
  - the checkout's `HEAD` is not `pinned_commit`;
  - the build copy is dirty;
  - a tool row in `global/tooling.md` is not `OK`;
  - a flag the command uses does not appear in the tool's help output.

  Never fill a missing value with a default. The starting values in Part C are for the user to copy into the manifest. Agents never apply them silently.
- **A3. Tool gate.** Run a tool only when its row in `global/tooling.md` has status `OK`. Before the first run in a bounty, save `<tool> --help` to `scans/<YYYY-MM-DD>_help-<tool>/help.txt` and confirm that every flag the command uses appears in it. Never install a tool. Installs need the user's approval (`tooling.md`, install log).
- **A4. Grounding.** Every code claim cites `path:line @commit` with the `[SRC]` tag and quotes the cited line verbatim. Names, selectors, storage slots, and addresses come from the build copy, a verified ABI, or saved tool output. Never write them from memory.
- **A5. Evidence.** Only saved artifacts count: `[SRC]` lines, `[TOOL]` output files, and `[POC]` run logs. A score, boolean, flag, or summary written by an agent or a script is not evidence. Every number in an output comes from a file, and the output names that file.
- **A5a. Claim semantics.** A citation tag or passing process is not proof that a claim follows from the cited artifact. For every material conclusion, state the exact artifact location, what it establishes, its limits, and whether the conclusion is `SUPPORTED`, `REFUTED`, or `UNRESOLVED`. Missing evidence is `UNRESOLVED`; a test failure refutes only the specific prediction it tested. Do not promote a finding because another agent, report, status field, or caller-supplied boolean says it passed.
- **A6. Tags.** Every factual sentence carries a tag from GEMINI 4.3. Use `[ASSUMPTION]` or `[UNKNOWN]` when no source exists. An untagged factual sentence makes the output invalid.
- **A7. Run record.** Each run writes `scans/<YYYY-MM-DD>_<tool>/` with `command.txt` (environment variable names only), `version.txt`, the raw output, `triage.md`, and `result.json` (schema in Part D). It also appends one line to the matching ledger in `logs/` (GEMINI Part 5), with the output SHA-256. Ledgers are append-only.
- **A8. Secrets.** Never write an RPC URL, API key, private key, or the value of any environment variable into a file, log, report, or message. Record variable names only, taken from `rpc_env`. If a secret appears in an input, do not copy it. Log `SECRET_EXPOSED` to `execution_ledger.jsonl` with the file and line, and tell the user to rotate it.
- **A9. Scope.** A path is a target only if it matches `analysis.in_scope_paths` and its contract is listed in `scope.md`. Anything else is refused and logged as `SCOPE_VIOLATION` in `gate_ledger.jsonl`.
- **A10. Safety.** Fork or testnet only. No state-changing transaction goes to a live chain. Keys are throwaway test keys created for a test and never stored (GEMINI Part 2, rules 2 and 7).
- **A11. Write boundaries.** Write only inside `bounties/<slug>/`, which includes the build copy. Never edit the checkout at `repo_path`. Never write `artifacts/review_decision.json`. Only the user writes it.
- **A12. Status.** Agents may set a finding to `Lead` or `Unconfirmed`. The lead sets `Draft`. Only the user sets `Ready` or `Submitted` (GEMINI 8.1).
- **A13. Build copy.** Builds and tests never run in the checkout, because they write `out/` and `cache/`. Create the copy with `git -C <repo_path> archive <pinned_commit> | tar -x -C bounties/<slug>/build/<pinned_commit>` (PowerShell equivalent on Windows). `git` is PRESENT (2.43.0) in `global/tooling.md`. Run `git archive --help` to confirm the archive form before the first use.
- **A14. Uncertainty.** State what is unknown in one plain sentence. Do not hedge with words that read like evidence.
- **A15. Output.** Return only the response envelope in `global/agents/CONTRACT.md`. Do not restate artifacts in prose.
- **A16. Guards.** Every run passes the three guards in `global/agents/CONTRACT.md` (ingress, in-flight, egress), in that order. A stage's own rules add to the guards and never replace them.

---

## Part B. PoC standard

Used by `forge-tester`, `proof-gate`, and `triage-explain`. A test that breaks any rule below is not a PoC.

- **B1. Right reason.** Before every `vm.expectRevert`, assert the state that makes the revert the one claimed. Match a specific selector or panic code. Never use bare `expectRevert()`.
- **B2. Real entrypoint.** Call the function an unprivileged actor can reach, not an internal helper, unless the claim is about the helper alone.
- **B2a. Test scope.** Classify each test as source/unit, integration, fork, or deployed-state reproduction. Identify mocks, cheatcodes, impersonation, direct helper calls, and manually altered state. These can prove only the behavior they exercise; never describe them as end-to-end or deployed proof unless the test actually establishes that.
- **B3. Legal state.** Mocks must not produce a state the real dependency cannot produce. Each mock states its invariants in a comment, with `[SRC]` lines.
- **B4. No disabled guards.** Do not zero a bound, disable a check, or bypass an allow-list unless the claim concerns it. If one is changed, the test header says so.
- **B5. Attacker model.** Use `makeAddr` addresses with no privileged setup. Label every privileged setup call.
- **B6. Quantify.** Assert exact before, after, and delta values, computed independently in the test. `assertGt(x, 0)` alone is not an impact check.
- **B7. Non-circular.** An assertion may not restate its own setup.
- **B8. Controls.** Include a benign-path control that passes, a boundary test one unit inside and one unit outside the trigger, a fix test that fails before the patch and passes after it, and a regression test for legitimate users.
- **B9. Dual plane.** Run on two forks pinned to `pinned_block`, using `rpc_env[0]` and `rpc_env[1]`. Results and every asserted value must match, with a divergence count of 0 (GEMINI 7.5).
- **B10. Determinism.** Run each passing PoC five times on each provider and report every outcome. Any difference makes the PoC invalid until its cause is found. Set `vm.warp` explicitly. Never depend on live time.

---

## Part C. Manifest schema

**File:** `bounties/<slug>/.gemini/BOUNTY_MANIFEST.json`. Add an `analysis` key to the existing manifest (`slug`, `program`, `platform`, `created`, `status`).

Values the program states come from `scope.md`. A value the program does not state is written as `NOT PROVIDED BY PROGRAM`, and any stage that needs it stops (A2). The user sets every value. An agent may propose a value with its `[SRC]` line, but only the user writes it into the manifest.

| Field | Type | Source | Used by |
|---|---|---|---|
| `repo_path` | string | user; read-only checkout | S1 |
| `shell` | `bash` or `powershell` | user | all runners |
| `pinned_commit` | 40-hex string | `scope.md` | S1 and every later stage |
| `pinned_block` | integer | `scope.md` or user; never `latest` | S3, S9 |
| `chain` | string | `scope.md` | S1, S9 |
| `compiler` | exact version string | repository config, `[SRC]` | S2, S9 |
| `in_scope_paths` | repo-relative paths or globs | `scope.md` | A9 and all scanners |
| `exclude_paths` | array | user (suggested: `lib`, `test`, `script`) | S2, S5 |
| `test_dirs` | array | user | S3, S4, S9 |
| `docs_paths` | array | user | S6 |
| `domains` | array of checklist names | GEMINI 7.4 names, plus any added in the bounty `GEMINI.md` | S2 and focus of every lead |
| `layout_contracts` | array of `path:Contract` | user; may be empty | S2 |
| `delegatecall_pairs` | array of `[host, target]` | user; may be empty | S2 |
| `no_state_targets` | array of contract names | user; may be empty | S2 |
| `known_tag_patterns` | array of regex | `scope.md` known-issue list | S6 |
| `accepted_risk_patterns` | array of regex | user | S2, S6 |
| `rpc_env` | array of two variable names | user; names only | S3, S9 |
| `fuzz_seed` | integer | user | S3 |
| `fuzz_seed_alt` | integer | user | S3 (second pass) |
| `fuzz_runs` | integer | user (suggested start: 10000) | S3 |
| `invariant_runs` | integer | user (suggested start: 1000) | S3 |
| `invariant_depth` | integer | user (suggested start: 100) | S3 |
| `halmos_loop_bound` | integer | user, after reading `halmos --help`; no suggestion | S4 |
| `halmos_solver_timeout_ms` | integer | user; no suggestion | S4 |
| `medusa_timeout_s` | integer | user | S3 |
| `allow_external_llm` | boolean (default `false`) | user, only if `scope.md` allows sending code outside | S7 |
| `citation_drop_alert` | number (suggested start: 0.30) | user | S8 |

**Schema example** (not a valid file; angle brackets are placeholders):

```json
{
  "slug": "<slug>",
  "program": "<program name from scope.md>",
  "platform": "<platform>",
  "created": "<YYYY-MM-DD>",
  "status": "<status>",
  "analysis": {
    "repo_path": "<absolute path to checkout>",
    "shell": "bash",
    "pinned_commit": "<40-hex from scope.md>",
    "pinned_block": "<integer from scope.md>",
    "chain": "<chain from scope.md>",
    "compiler": "<exact solc version>",
    "in_scope_paths": ["<repo-relative path from scope.md>"],
    "exclude_paths": ["lib", "test", "script"],
    "test_dirs": ["test"],
    "docs_paths": ["docs"],
    "domains": ["<checklist name>"],
    "layout_contracts": [],
    "delegatecall_pairs": [],
    "no_state_targets": [],
    "known_tag_patterns": ["<regex from scope.md>"],
    "accepted_risk_patterns": ["@custom:accepted-risk"],
    "rpc_env": ["<variable name A>", "<variable name B>"],
    "fuzz_seed": "<integer>",
    "fuzz_seed_alt": "<integer>",
    "fuzz_runs": "<integer>",
    "invariant_runs": "<integer>",
    "invariant_depth": "<integer>",
    "halmos_loop_bound": "<integer>",
    "halmos_solver_timeout_ms": "<integer>",
    "medusa_timeout_s": "<integer>",
    "allow_external_llm": false,
    "citation_drop_alert": 0.30
  }
}
```

**Domain names** match GEMINI 7.4: `access_control`, `reentrancy`, `oracle`, `flash_loan`, `rounding`, `token_assumptions`, `signatures`, `upgradeability`, `dos`, `economic`, `cross_contract`. A bounty may add its own names in its `GEMINI.md`. Each name must have its checklist text there.

---

## Part D. Stages, gates, and records

### D1. Stages

A stage starts only when every expected output of the prior stage exists and its `result.json` has `status: ok`, or when a skip is recorded in `state.md` with its reason. S2, S3, and S4 may run in parallel. S5 waits for all three.

| Stage | Agents | Output | Gate (GEMINI 8.2) | `run_pipeline.sh` stage |
|---|---|---|---|---|
| S1 Pin and scope | `source-pin` | `pin.json` | 3 Scope | `verify` |
| S2 Static, layout, and maps | `bounty-scanner`, `pathway-scout`, `hypothesis-analyst`, `slither-runner`, `aderyn-runner`, `forge-inspect-layout`, `layout-diff`, `sarif-collector` | SARIF, layouts, `facts.md` entries, `hypotheses/H-###.md` | none | `build`, `scan` |
| S3 Dynamic | `forge-unit-runner`, `forge-fuzz-runner`, `forge-invariant-runner`, `echidna-executor`, `medusa-executor` | JSON and text per run | none | `fuzz` |
| S4 Symbolic and replay | `halmos-arithmetic`, `halmos-guards`, `halmos-proofing`, `halmos-counterexample`, `counterexample-tracer` | `proofs.json`, replay inputs, traces | none | none yet |
| S5 Normalize | `normalize-file`, `normalize-line`, `normalize-rule` | `findings.json` | 1 Source (line exists) | `scan` |
| S6 Known issues and validation | `known-tags-scan`, `known-accepted-risk`, `known-overlap-annotator`, `deep-scanner` | `findings_annotated.json`, validation status | 4 Duplicate | none yet |
| S7 Triage (only if `allow_external_llm` is true) | `triage-gemini-runner`, `triage-schema-guard`, `triage-group`, `triage-rank`, `triage-explain` | `groups.json`, `ranked.json`, `candidates.md` | none | none yet |
| S8 Citation and adversarial challenge | `hallucination-dropper`, `independent-falsifier` | `candidates_validated.json`, challenge note | 1 Source and 6 Provenance | none yet |
| S9 Proof | `forge-tester`, `proof-gate` | `poc/F-###_<short-name>.t.sol`, `poc_ledger` lines | 2 Reproduction | `poc` |
| S10 Human review | `review-packet-builder` | `artifacts/review_packet_F-###.md` | 5 Severity and 6 Provenance audit | `gate` |

Orchestration sits above the stages: `lead-security-auditor` chooses leads and writes the final draft, and `pipeline-orchestrator` sequences the stages and checks gates. Neither judges evidence.

The six-step `run_pipeline.sh` (`verify`, `build`, `scan`, `fuzz`, `poc`, `gate`) has no slots for S4, S6, S7, S8, or S10 yet. Add them before running the pipeline end to end.

### D2. Lifecycle of a candidate

`Lead` (S2 or S4) → `Unconfirmed` (S5 fails, or S9 demotes) → `Draft` (lead, after S9 passes) → `Ready` (user). A candidate with a failed citation, failed scope check, covered known issue, or falsified guard is logged in `gate_ledger.jsonl` and kept. A failed scope gate is an eligibility blocker, not proof the technical hypothesis is false. It is never deleted.

A hypothesis is written as `H-###`. When it becomes a lead, it gets an `F-###` ID (GEMINI 7.3), and the lead file keeps the `H-###` as a cross-reference.

### D3. result.json

Every executor and reasoning agent writes this file in its run folder:

```json
{"agent": "<name>", "stage": "S<n>", "status": "ok | fail | tool_missing | stopped | skipped | no_tests", "started": "<ISO 8601 with offset>", "commit": "<pinned_commit>", "inputs": ["<path>"], "outputs": ["<path>"], "stats": {}, "stop_reason": "<text or null>"}
```

`no_tests` means zero tests matched the filter. It is not a pass.

### D4. Ledger record types

| Event | Ledger file | `type` value | Extra fields |
|---|---|---|---|
| Scan run | `scan_ledger_<date>.jsonl` | `SCAN_RUN` | `tool`, `version`, `command`, `output`, `output_sha256` |
| PoC run | `poc_ledger_<date>.jsonl` | `POC_RUN` | `finding`, `command`, `block`, `provider`, `result`, `output`, `output_sha256` |
| Gate decision (pass, fail, kill, duplicate, citation drop, scope violation) | `gate_ledger.jsonl` | `GATE_CHECK` | `finding`, `gate`, `result`, `reason`, `evidence` |
| Artifact | `execution_ledger.jsonl` | `EXECUTION_ARTIFACT` | `path`, `sha256` |
| Tool missing or flag unverified | `scan_ledger_<date>.jsonl` | `TOOL_MISSING` or `TOOL_FLAG_UNVERIFIED` | `tool`, `flag` |
| Secret seen in input | `execution_ledger.jsonl` | `SECRET_EXPOSED` | `file`, `line` |
| Stage stop or skip | `session_ledger_<date>.jsonl` | `STAGE_STOP` or `STAGE_SKIP` | `stage`, `reason` |

`gate` values come from GEMINI 8.2 (`source`, `reproduction`, `scope`, `duplicate`, `severity`, `provenance`). Stage stops use `session_ledger`.

---

## Part 2. Agent definitions

Each role definition is maintained in its corresponding `global/agents/<agent-name>.md` file. The 43 role-specific playbooks are indexed in `global/agents/PLAYBOOKS.md` and are mandatory under `CONTRACT.md` A16.

## Part 2a. Bug-hunting system

Use global/agents/bug-hunting-system.md as the coordination map for one scoped bounty. It reuses existing pinning, pathway, scanner, normalization, citation, PoC, and review agents; it adds two focused roles: hypothesis-analyst and independent-falsifier. The system grants no scope or submission authority. All agents remain bound by Part A, CONTRACT.md, and active bounty instructions.

hypothesis-analyst creates falsifiable H-### records from pinned source and pathway evidence. Each candidate is challenged independently before PoC work. Missing evidence stays UNRESOLVED; tool alerts are leads, not findings. Only the human may mark a report ready or submit it.

---

## Part E. Operating notes

### E1. Tools with no agent yet

Mythril (`myth`), Solhint, Certora (`certoraRun`), Kontrol, Heimdall, `cast`, `anvil`, and `chisel` have no agent in this set. Semgrep runs only in the `scan` stage of `run_pipeline.sh`, and no agent wraps it. Each tool without an agent needs its own row in `global/tooling.md`, checked by its version command, and then its own runner before it is used.

### E2. Nothing has run

Every scanner is MISSING in `global/tooling.md` (2026-10-10). Nothing in this set has run. Before a tool's first run, its help output is saved (A3), and its row moves to OK only after its version command runs. Installing a tool needs the user's approval first.

### E3. ID scheme

- `H-###`: a hypothesis, written in the hypothesis loop (W6).
- `F-###`: a lead (GEMINI 7.3). The lead file keeps the `H-###` it came from as a cross-reference.
- `R-###`: a refutation in `global/refutations.md`. Its source hypothesis is recorded in the source bounty's `state.md`.
- `PAT-###`: a pattern in `global/patterns.md`. Its source is an opaque `SRC-###` ID, mapped in `MEMORY.md`.

### E4. Pipeline stages

`run_pipeline.sh` in `global/tools/` has six stages: `verify`, `build`, `scan`, `fuzz`, `poc`, and `gate`. Stages S4, S6, S7, S8, and S10 are not in the script. The agents for those stages run them directly and write to the ledgers in D4. PoCs use the two providers in `RPC_URL_A` and `RPC_URL_B`, pinned to `PINNED_BLOCK`.

### E5. Keys to rotate

An earlier config pasted into chat held a live Render API key in plaintext. The v4lend scan file holds an Alchemy key. Both are treated as exposed, and the user must rotate them. The Render key begins `rnd_`, and the Alchemy key begins `alch_`. No key value is written to any file in this workspace, and nothing from the scan file is reused.

### E6. Tool names in frontmatter

Names such as `send_message`, `invoke_subagent`, and `manage_subagents` have not been checked against the runtime. If a name is not available there, remove it from that agent and log the removal in the active bounty's session ledger.

### E7. Scan reports from other sources

The v4lend scan report is not used by any agent. Its findings are unverified. They can be considered as a Cantina lead only after the user names the bounty it belongs to and confirms that bounty's scope.
