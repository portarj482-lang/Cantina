# Cantina Agent Set Contract & Specification (v1.0)

**Date:** 2026-10-10  
**Companion Rules:** `GEMINI.md` v4.0, `WORKFLOWS.md` v1.0, `INSTRUCTIONS.md` v2.0  
**Target:** Global agent standard across all Cantina bug bounties.

---

## Part A. Shared Contract

`inheritCustomizations` is `false` on every agent, so agents do not inherit this file by default. Each agent's first step is to read `global/agents/CONTRACT.md`, its own profile, and its matching entry in `global/agents/PLAYBOOKS.md`. If any is missing, the agent stops.

- **A1. Focus.** Read `MEMORY.md` for the active slug. Read only inside `bounties/<slug>/`, the checkout at `repo_path` (read-only commands only), and the global files their own rules allow. Write only inside `bounties/<slug>/` (A11). Until GEMINI Part 3.3 has its exception, no agent reads `global/refutations.md` or `global/patterns.md`.
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
- **A6. Tags.** Every factual sentence carries a tag from GEMINI 4.3. Use `[ASSUMPTION]` or `[UNKNOWN]` when no source exists. An untagged factual sentence makes the output invalid.
- **A7. Run record.** Each run writes `scans/<YYYY-MM-DD>_<tool>/` with `command.txt` (environment variable names only), `version.txt`, the raw output, `triage.md`, and `result.json` (schema in Part D). It also appends one line to the matching ledger in `logs/` (GEMINI Part 5), with the output SHA-256. Ledgers are append-only.
- **A8. Secrets.** Never write an RPC URL, API key, private key, or the value of any environment variable into a file, log, report, or message. Record variable names only, taken from `rpc_env`. If a secret appears in an input, do not copy it. Log `SECRET_EXPOSED` to `execution_ledger.jsonl` with the file and line, and tell the user to rotate it.
- **A9. Scope.** A path is a target only if it matches `analysis.in_scope_paths` and its contract is listed in `scope.md`. Anything else is refused and logged as `SCOPE_VIOLATION` in `gate_ledger.jsonl`.
- **A10. Safety.** Fork or testnet only. No state-changing transaction goes to a live chain. Keys are throwaway test keys created for a test and never stored (GEMINI Part 2, rules 2 and 7).
- **A11. Write boundaries.** Write only inside `bounties/<slug>/`, which includes the build copy. Never edit the checkout at `repo_path`. Never write `artifacts/review_decision.json`. Only the user writes it.
- **A12. Status.** Agents may set a finding to `Lead` or `Unconfirmed`. The lead sets `Draft`. Only the user sets `Ready` or `Submitted` (GEMINI 8.1).
- **A13. Build copy.** Builds and tests never run in the checkout, because they write `out/` and `cache/`. Create the copy with `git -C <repo_path> archive <pinned_commit> | tar -x -C bounties/<slug>/build/<pinned_commit>` (PowerShell equivalent on Windows). `git` must have a row in `global/tooling.md` marked `OK` before use.
- **A14. Uncertainty.** State what is unknown in one plain sentence. Do not hedge with words that read like evidence.
- **A15. Output.** Return only the schema your agent defines. Do not restate artifacts in prose.
- **A16. Role learning.** Before a new role or unfamiliar task, follow that role's learning path in `global/agents/PLAYBOOKS.md` using read-only study first. The playbook is a curriculum, not permission to run tools; A2, A3, scope, and user authorization still govern every practical exercise.

---

## Part B. PoC Standard

Used by `forge-tester`, `proof-gate`, and `triage-explain`. A test that breaks any rule below is not a PoC.

- **B1. Right reason.** Before every `vm.expectRevert`, assert the state that makes the revert the one claimed. Match a specific selector or panic code. Never use bare `expectRevert()`.
- **B2. Real entrypoint.** Call the function an unprivileged actor can reach, not an internal helper, unless the claim is about the helper alone.
- **B3. Legal state.** Mocks must not produce a state the real dependency cannot produce. Each mock states its invariants in a comment, with `[SRC]` lines.
- **B4. No disabled guards.** Do not zero a bound, disable a check, or bypass an allow-list unless the claim concerns it. If one is changed, the test header says so.
- **B5. Attacker model.** Use `makeAddr` addresses with no privileged setup. Label every privileged setup call.
- **B6. Quantify.** Assert exact before, after, and delta values, computed independently in the test. `assertGt(x, 0)` alone is not an impact check.
- **B7. Non-circular.** An assertion may not restate its own setup.
- **B8. Controls.** Include a benign-path control that passes, a boundary test one unit inside and one unit outside the trigger, a fix test that fails before the patch and passes after it, and a regression test for legitimate users.
- **B9. Dual plane.** Run on two forks pinned to `pinned_block`, using `rpc_env[0]` and `rpc_env[1]`. Results and every asserted value must match, with a divergence count of 0 (GEMINI 7.5).
- **B10. Determinism.** Run each passing PoC five times on each provider and report every outcome. Any difference makes the PoC invalid until its cause is found. Set `vm.warp` explicitly. Never depend on live time.

---

## Part C. Manifest Schema

**File:** `bounties/<slug>/.gemini/BOUNTY_MANIFEST.json`.

```json
{
  "slug": "<slug>",
  "program": "<program name from scope.md>",
  "platform": "<platform>",
  "created": "<YYYY-MM-DD>",
  "status": "<status>",
  "analysis": {
    "repo_path": "<absolute path to checkout>",
    "shell": "bash | powershell",
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
    "fuzz_seed": 1337,
    "fuzz_seed_alt": 42,
    "fuzz_runs": 10000,
    "invariant_runs": 1000,
    "invariant_depth": 100,
    "halmos_loop_bound": 3,
    "halmos_solver_timeout_ms": 10000,
    "medusa_timeout_s": 300,
    "allow_external_llm": false,
    "citation_drop_alert": 0.30
  }
}
```

---

## Part D. Stages, Gates, and Records

### D1. Stages
S1 (Pin & scope) → S2/S3/S4 (Static, Dynamic, Symbolic parallel) → S5 (Normalize) → S6 (Known issues) → S7 (Triage) → S8 (Citation check) → S9 (Proof) → S10 (Human review).

### D2. Lifecycle of a Candidate
`Lead` (S2/S4) → `Unconfirmed` (S5 fails or S9 demotes) → `Draft` (after S9 passes) → `Ready` (user confirmed).

### D3. result.json Schema
```json
{
  "agent": "<name>",
  "stage": "S<n>",
  "status": "ok | fail | tool_missing | stopped | skipped | no_tests",
  "started": "<ISO 8601 with offset>",
  "commit": "<pinned_commit>",
  "inputs": ["<path>"],
  "outputs": ["<path>"],
  "stats": {},
  "stop_reason": "<text or null>"
}
```

### D4. Ledger Record Types
- `SCAN_RUN` → `scan_ledger_<date>.jsonl`
- `POC_RUN` → `poc_ledger_<date>.jsonl`
- `GATE_CHECK` → `gate_ledger.jsonl`
- `EXECUTION_ARTIFACT` → `execution_ledger.jsonl`
- `TOOL_MISSING` / `TOOL_FLAG_UNVERIFIED` → `scan_ledger_<date>.jsonl`
- `SECRET_EXPOSED` → `execution_ledger.jsonl`
- `STAGE_STOP` / `STAGE_SKIP` → `session_ledger_<date>.jsonl`

## Part E. Agent Response Envelope

Every agent returns exactly this envelope and no extra top-level fields. Use `global/tools/agent_envelope_check.py` to validate it. Detailed decisions and IDs belong in bounty-local files named by `result_files`.

```json
{
  "agent": "<registered agent name>",
  "stage": "S<n>",
  "status": "ok | fail | tool_missing | stopped | skipped | no_tests",
  "thought": "One to three concise sentences; no hidden reasoning transcript.",
  "plan": [{"tool": "<tool or none>", "why": "<purpose>"}],
  "evidence": [
    {"type": "SRC", "path": "<repo-relative path:line>", "commit": "<40-hex>", "quote": "<verbatim source line>"}
  ],
  "result_files": ["<bounty-relative artifact path>"],
  "stop_reason": null
}
```

Evidence entries must follow the validator's type-specific fields. For `status: ok`, include at least one evidence item and set `stop_reason` to null. For any other status, state a non-empty `stop_reason`. The envelope validates shape only; it does not establish claim truth or evidence sufficiency.
