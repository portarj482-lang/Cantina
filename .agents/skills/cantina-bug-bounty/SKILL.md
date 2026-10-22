---
name: cantina-bug-bounty
description: >-
  Workflow guidance and helper CLI for Cantina smart-contract and onchain reviews. The CLI checks scope snapshots, envelope shape, and provenance tags; it does not verify findings, execute PoCs, or establish report readiness.
---

# Cantina Bug Bounty Pipeline

## Overview
Provides workflow guidance and helper checks for Cantina bug bounty reviews. Scope, target runtime, program rules, and evidence requirements determine which tools and reproduction environment apply. The helper CLI does not execute audits or prove that a report is ready.

## Dependencies
The helper CLI uses only the Python standard library. No other skills are required. EVM and Solana commands shown in the workflow require their respective toolchains and must be checked against the project's installed versions and the program's rules before use.

## Quick Start
```bash
# 1. Lock and verify the full marker-delimited scope block after LF normalization
uv run python .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py scope-lock \
  --scope-file bounties/<slug>/scope.md \
  --snapshot-file bounties/<slug>/snapshots/scope.sha256 \
  --output bounties/<slug>/logs/scope_lock.json

# 2. Verify scope integrity
uv run python .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py scope-verify \
  --scope-file bounties/<slug>/scope.md \
  --snapshot-file bounties/<slug>/snapshots/scope.sha256 \
  --output bounties/<slug>/logs/scope_verify.json

# 3. Append a verified fact
uv run python .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py fact-record \
  --facts-file bounties/<slug>/facts.md \
  --fact "SpendRouter decodes (executor, recipient) from 64-byte extraData" \
  --tag "[SRC: src/SpendRouter.sol:224 @e0004e6]" \
  --output bounties/<slug>/logs/fact_record.json

# 4. Audit readiness gates for candidate finding
uv run python .agents/skills/cantina-bug-bounty/scripts/bounty_cli.py gate-check \
  --finding bounties/<slug>/findings/F-001.md \
  --bounty-root bounties/<slug> \
  --output bounties/<slug>/logs/gate_check_F001.json
```

## Utility Scripts (`scripts/bounty_cli.py`)
Zero-dependency Python standard library CLI executable via `uv run python scripts/bounty_cli.py`:

- **`scope-lock`**: Hashes the unique marker-delimited block, including both marker lines, after normalizing CRLF and CR line endings to LF. A final LF is included if the end marker has none.
- **`scope-verify`**: Re-computes LF-normalized SHA-256 and compares with snapshot. Exits with code 1 if scope has drifted.
- **`envelope-check`**: Validates agent envelopes against schema and checks for exposed private keys or API keys.
- **`fact-record`**: Formats, tags, and appends a newly established fact into `facts.md`.
- **`gate-check`**: Reports limited syntax checks and blockers for the six gates. It cannot establish source accuracy, reproduction, scope, duplicate status, or severity; a clean provenance scan is not a readiness result.

For a local custom PoC, generated file, or artifact that is not authenticated to a commit, use `[LOCAL: path:line, provenance unpinned]`, record its SHA-256 and git status when available, and describe only the local file's contents. Do not tag it `[SRC: ... @commit]` or treat it as deployment evidence.

## Workflow

### Phase 1: Intake & Scope Lock
1. Copy raw program rules and asset tiers into `bounties/<slug>/scope.md` between `<!-- SCOPE START -->` and `<!-- SCOPE END -->`.
2. Run the CLI `scope-lock` command to generate `snapshots/scope.sha256`.
3. Verify hash matches before proceeding to reconnaissance.

### Phase 2: Reconnaissance & Environment
1. Clone target repositories, check out pinned commits, and record `[TOOL: git rev-parse HEAD]` in `facts.md`.
2. Use compiler and test tools for the target runtime (for example, Foundry for EVM projects or Anchor/Solana tools for Solana programs). EVM tooling does not establish Solana execution results.
3. Verify external dependencies only in an environment permitted by the program. A fork is not interchangeable with a live devnet deployment.

### Phase 3: Analysis & Hypothesis Cycle
1. Map entry points against `references/vulnerability_checklist.md`.
2. For entry points exhibiting one of the 12 attack vectors (e.g., inline assembly, low-level calls, signatures, external swaps, or balance guards), load the relevant pattern on demand from `references/field_guide_patterns.md`. To conserve context, do not load this large reference on initial turns or unless a matching entry point is encountered.
3. Note that vulnerability category tiers are initial screening hypotheses only; final severity must reflect demonstrated economic loss and the specific program's `scope.md`. Exposed data / PII is typically out of scope or informational unless direct fund loss is proven.
4. Write a falsifiable prediction, probe the actual entrypoint, then record whether evidence confirms or refutes it.
5. Record verified facts using the CLI `fact-record` command.

### Phase 4: Dual-Plane Reproduction & Gate Check
1. Write a PoC in the target runtime's test framework, subject to the program's rules. Foundry applies to EVM contracts; Anchor tests apply to Solana programs.
2. Pin state where the runtime permits it. Use independent providers only when appropriate, and record each run's command, block or slot, provider label, and output. A test's PASS label means only that its assertions passed; it does not by itself establish a vulnerability or safety.
3. Use `gate-check` as a diagnostic only. Manually verify each report gate against saved evidence before submission.

## Rate Limiting & Secrets Handling
- API keys and private keys are **never** committed or stored in text files or repository trees.
- Read RPC endpoints strictly from `$RPC_URL`, `$RPC_URL_A`, and `$RPC_URL_B`.
- The CLI makes no RPC requests and implements no retry or backoff policy. RPC clients should follow their provider's documented retry limits.

## Common Mistakes
1. **Line ending changes**: `scope-lock` and `scope-verify` normalize CRLF and CR to LF, then hash the marker-delimited block. Whitespace and text in that block still affect the digest.
2. **Reproduction evidence**: A second RPC URL or `[POC: PASS]` tag does not prove that two runs occurred or agreed. Preserve and review the actual outputs.
3. **Provenance tags**: The audit checks for tags; it cannot confirm a citation's accuracy or that a claim follows from its source.
