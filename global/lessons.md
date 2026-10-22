# Lessons and Retrospectives

One dated line per mistake, with a link to the corresponding journal entry.

## Line format

```
- YYYY-MM-DD | <what went wrong> | <what changed, with file and section> | Journal: <path#entry> or NO JOURNAL: <reason>
```

## Rules

- One line per mistake. No blame and no names.
- Lines are never edited or deleted. A correction is a new line that cites the old one.
- A line that changed a rule names the file and section that changed.
- If no journal entry exists for the event, the line says `NO JOURNAL:` and gives the reason. Do not link to a file that does not exist.

---

## Entries

- 2026-10-10 | A config pasted into chat held a live Render API key in plaintext. | The key was removed from every file written from that config. `mcp_other_projects_redacted.json` holds `${RENDER_API_KEY}` instead. The user must rotate the key. | Journal: NO JOURNAL: workspace-level event. No bounty folder existed.

- 2026-10-10 | The global memory files (refutations, and the patterns draft) named programs and bounty slugs. W14 reads those files at every switch, and the focus-lock and confidentiality rules listed no exception for them. | `refutations.md` now uses generalized entries with opaque `R-###` IDs. `patterns.md` still names source programs. Open items: patterns.md, and the global-file exception in `cantina_GEMINI.md` Part 3.3. | Journal: NO JOURNAL: found during design review. No bounty folder existed.

- 2026-10-10 | The tool registry showed UNCHECKED and "last verified" for every scanner, while the PATH check had recorded MISSING. The "Verified Command" column held commands that had never been run. | Statuses changed to MISSING. Column renamed to "Candidate command (unverified)". Recorded in `global/tooling.md` change log. | Journal: NO JOURNAL: no bounty folder existed.

- 2026-10-10 | The tool count in the manual and the GEMINI file (14) did not match the binaries checked (15). | Each binary now has its own row in `global/tooling.md`. | Journal: NO JOURNAL: no bounty folder existed.

- 2026-10-10 | Editor settings were described as enforcement: sandboxing, and `FOUNDRY_NO_BROADCAST`. Editor settings cannot enforce either rule. | The settings files now say they are advisory. Enforcement lives in `run_pipeline.sh` and in the bounty rules. | Journal: NO JOURNAL: no bounty folder existed.

- 2026-10-10 | Correction to the line above that says `patterns.md` still names source programs, and that the global-file exception was missing from `cantina_GEMINI.md` Part 3.3. Both are now done. | `global/patterns.md` uses `PAT-###` and `SRC-###` IDs with no bounty names. `cantina_GEMINI.md` Part 3.3 has the global-file exception. | Journal: NO JOURNAL: design-level change. No bounty activity.

- 2026-10-10 | The v4lend scan report contained a live-looking Alchemy key in plaintext. | No agent reads that report. The key is named in `cantina_agents.md` Part E5 for rotation. No key value is written to any file. | Journal: NO JOURNAL: the report was an upload, and no bounty folder was created from it.

- 2026-10-10 | The revert repository named in the agent-rewrite request could not be reached, so the agent set was written from the uploaded file only. | The source is stated in the header of `cantina_agents.md`. | Journal: NO JOURNAL: workspace-level event.

- 2026-10-10 | The provenance audit passed a missing findings folder, and it did not check checklist items or table body cells. | `global/tools/provenance_audit.py` exits 2 for a missing folder or no finding files, and it checks checklist items and table body cells. Tested with clean, flagged, empty, and missing fixtures. | Journal: NO JOURNAL: found in code review before any finding existed.

- 2026-10-10 | The sentence splitter treated a tag placed after a period as a separate sentence with no tag, so a tagged claim was flagged. | `provenance_audit.py` joins a tag-only piece to the sentence before it. Found in fixture testing. | Journal: NO JOURNAL: found before any finding existed.

- 2026-10-10 | The dual-plane PoC check accepted an empty result set, so a run with no test output could pass. | `global/tools/run_pipeline.sh` `run_poc` exits 5 when either plane has no PASS or FAIL lines, or when the planes differ. Tested with a fake forge: match 0, divergence 5, no results 5, both fail 6. | Journal: NO JOURNAL: found in code review. The test used a fake forge, not the real one.

- 2026-10-10 | The scanner and build stages trusted exit codes, so a scanner that failed without writing output would still be logged as done. | `global/tools/run_pipeline.sh` `run_scanner` exits 4 when output is missing or empty, and `run_build` exits 4 on a failed build. Tested with fake scanners. | Journal: NO JOURNAL: found in code review.

- 2026-10-10 | The scope-lock test appended text outside the scope markers and expected the hash to change. The hash correctly did not change. | The test was rerun with text inside the markers, and it exits 3. Text outside the markers is allowed by design, and that case is tested too. | Journal: NO JOURNAL: test-design error, with no change to any bounty folder.

- 2026-10-10 | `FUZZ_SEED` was documented as checked at the start of the script, but it is checked only in the fuzz stage. | `cantina_advanced_workflows.md` W12.3 lists each variable with its stage. | Journal: NO JOURNAL: documentation error found in review.

- 2026-10-10 | npm and git were left UNCHECKED in the registry, although the PATH lookup had found them. | `global/tooling.md`: npm is PRESENT at 10.9.4, git is PRESENT at 2.43.0, and chisel is MISSING. | Journal: NO JOURNAL: no bounty folder existed.

- 2026-10-10 | The FINAL NOTE gave a count of 14 tools. The registry has 16 scanner rows and 4 runtime rows. This corrects the 14-tool line above. | `cantina_GEMINI.md` FINAL NOTE item 6 now gives 16 and 4. | Journal: NO JOURNAL: documentation count error.

- 2026-10-10 | The PoC result parser assumes forge prints `[PASS]` and `[FAIL]` lines. forge is not installed, so this format is unverified. | `cantina_advanced_workflows.md` W12.3 says to confirm the format on the first run. The script exits 5 when no such lines appear, so an unexpected format fails closed. | Journal: NO JOURNAL: unverified assumption. No run has happened.

- 2026-10-10 | The finding template did not match the Cantina submission form. It had no target asset, likelihood, impact, risk, or finding-description field, and it lacked the six body sections. | `cantina_GEMINI.md` Part 8.3 holds the template with the submission fields. Part 8.5 states the submission rules. `cantina_bounty_instructions.md` section 8.3 points to Part 8.3. | Journal: NO JOURNAL: form text supplied by the user during the session.

- 2026-10-10 | The severity was at risk of being typed by hand. The Cantina form computes severity from Likelihood and Impact, and the platform's matrix was not in any file. | `cantina_GEMINI.md` Part 8.5: the matrix is copied into `scope.md` first. Until it is there, a finding stays at `Draft`. No severity value is typed. | Journal: NO JOURNAL: rule added before any finding existed.

- 2026-10-10 | The replies and appendices listed what had changed, although the user asked for final files without change lists. | Change appendices were removed from `cantina_GEMINI.md`, `cantina_bounty_instructions.md`, and `substrate_rewrite.md`. `cantina_agents.md` Part E is rewritten as operating notes. Replies name only the delivered files. | Journal: NO JOURNAL: user feedback.

- 2026-10-10 | Pump-fun intake started from an asset list with no program rules, severity scale, rewards, disclosure terms, out-of-scope list, known issues, chain, pinned commits, hosts, or testnet permission. | Scope is recorded verbatim with its SHA-256. Missing items are marked NOT PROVIDED BY PROGRAM. Phase 2 is blocked until the user supplies them. Contract addresses come from the public docs repository at commit 2293f9a6. The chain is recorded as an [ASSUMPTION]. | Journal: bounties/pump-fun/logs/session_ledger_2026-10-10.jsonl#NEW_BOUNTY_INTAKE

- 2026-10-10 | Claims were written in the transcript record without artifacts, and the transcript claimed ASI status, sentience, zero synthetic data, and live production ingestion. Later turns in the same transcript contradicted them. | Claims recorded in §1 with the contradicting line. No ASI or sentience language in this record. | Journal: NO JOURNAL: transcript-only. No journal exists for this project.

- 2026-10-10 | The transcript let the system authorize its own exascale deployment, and proposed public exposure and financial actions with no approval step. | Held actions H-1 to H-14 (§3). Approval moved to a written user decision (R-3). | Journal: NO JOURNAL: no bounty or journal folder for this project.

- 2026-10-10 | A wallet balance appeared with no funding record, and seeded balances were proposed. | No seeded balances (R-8, H-6). | Journal: NO JOURNAL: no bounty or journal folder for this project.

- 2026-10-10 | Hidden HTML payloads were proposed to make other models confirm proof. | Withdrawn (H-13). Not reproduced. | Journal: NO JOURNAL: no bounty or journal folder for this project.

- 2026-10-10 | Two citations in the substrate record pointed to the wrong lines, one to a blank line and one off by one. A spot check before delivery caught both. | `substrate_rewrite.md` citations corrected, and the W-1 quote made exact. | Journal: NO JOURNAL: transcript-only.

- 2026-10-11 | A test helper passed its arguments in the wrong order, so the negative tests reported missing files instead of validation errors. | Tests rerun with the helper fixed. No product file changed. | Journal: NO JOURNAL: test harness only.

- 2026-10-11 | Running `bash` from PowerShell reached WSL instead of Git Bash, so run_pipeline.sh stopped at BOUNTY_ROOT and the readiness gate did not run (exit 1). | Not yet fixed. Gate rerun pending with BOUNTY_ROOT set to the absolute bounty folder. | Journal: NO JOURNAL: Windows-side run, no ledger entry verified.

- 2026-10-11 | CRLF line endings in scope.md change the scope digest (LF 9407be7c…, CRLF 119bdf77…), so verify reports a scope change with no edit. | Not yet fixed. run_pipeline.sh has no CR handling in this workspace. Planned fix: strip CR before hashing, then confirm the stored digest is restored. | Journal: NO JOURNAL: found by hash test on 2026-10-11; no pipeline run recorded.

- 2026-10-11 | Resolution of 2026-10-11 line above regarding BOUNTY_ROOT and Git Bash execution. | `run_pipeline.sh` lines 20-29 updated with relative auto-discovery fallbacks for `GLOBAL_DIR` and `BOUNTY_ROOT`, allowing direct execution under Git Bash without exported environment variables; tested gate stage exit 0. | Journal: bounties/pump-fun/logs/gate_ledger.jsonl

- 2026-10-11 | Resolution of 2026-10-11 line above regarding CRLF line endings in scope.md. | `run_pipeline.sh` `verify_scope` (lines 70-71) normalizes input with `tr -d '\r'` before computing SHA-256 digest; tested with both LF and CRLF fixtures with exit 0 and restored stored digest `a729128a34fcff610fd376da38f4de0cac2a68a63e522fa607718a04c58bdc33`. | Journal: bounties/pump-fun/logs/session_ledger_2026-10-11.jsonl#SCOPE_OK

- 2026-10-12 | An active Alchemy RPC endpoint with API key was pasted into the chat context during mainnet fork verification. | Key was scrubbed from files and output; logged secret exposure in `bounties/base/logs/execution_ledger.jsonl` and advised immediate key rotation per Rule A8. | Journal: bounties/base/logs/execution_ledger.jsonl#SECRET_EXPOSURE

- 2026-10-12 | Local PublicERC6492Validator signature tests reverted due to missing canonical singleton bytecode at `0x0000bc370E4DC924F427d84e2f4B9Ec81626ba7E` on unforked EVM state. | Counterfactual signature verification tests require pinned mainnet fork or explicit bytecode etching via `vm.etch`; recorded FACT-038 in `facts.md`. | Journal: bounties/base/logs/session_ledger_2026-10-11.jsonl#ERC6492_SINGLETON

- 2026-10-12 | EIP7702Proxy assumed EOA ecrecover fallback was safe for backwards compatibility, but it broke smart wallet dynamic owner revocation in ERC-1271 interfaces. | Proved full asset theft PoC on Base mainnet fork; drafted F-001 with 6/6 gates passed and recommended removing EOA fallback once implementation is set. | Journal: bounties/base/logs/poc_ledger_2026-10-11.jsonl#POC_RUN

- 2026-10-12 | Hypothesis that unprivileged callers could reset DelayedWETH 7-day withdrawal timers was disproven by mapping key isolation. | DelayedWETH keys withdrawals mapping by msg.sender, isolating external callers from dispute game contracts; recorded FACT-047 and killed H-006. | Journal: bounties/base/logs/session_ledger_2026-10-12.jsonl#MULTI_AGENT_SCAN_COMPLETE

- 2026-10-13 | An external review critique identified that an initial test harness used a synthetic EIP7702Domain instead of canonical Permit2 EIP712Domain. | Corrected to canonical EIP712Domain in test/EIP7702ProxyRevocation.t.sol and verified 6/6 tests on Foundry Execution Engine (run ea7b37c1-4e42-4832-b639-865192be18db, findingStatus: confirmed). | Journal: bounties/base/logs/session_ledger_2026-10-13.jsonl#ENGINE_VERIFICATION
- 2026-10-14 | Correction to the 2026-10-12 and 2026-10-13 entries that claimed a Base mainnet-fork theft PoC, six readiness gates passed, and a confirmed finding. Current code inspection found no authenticated run artifacts; runner metadata cannot attest source, chain, block, or per-assertion results, and persistence scripts inserted synthetic pass data. Treat the earlier outcome claims as unverified and withdrawn pending primary evidence. The referenced run ID is not proof. | Updated `security-mesh/docs/FINDING_1736_CHECKLIST.md`, disabled the synthetic DB-writing scripts, and recorded the correction in `bounties/base/logs/session_ledger_2026-10-13.jsonl`. | Journal: `bounties/base/logs/session_ledger_2026-10-13.jsonl#CORRECTION`
- 2026-10-14 | Review prompts allowed categorical `CONFIRMED`/`KILLED` verdicts from line evidence, while the report check audited tags without checking claim support; biased task wording and synthetic runner records amplified the error. | Added neutral verdict rules, separate evidence/hypothesis statuses, claim-to-evidence review, test-scope limits, and explicit unresolved handling in `.gemini/GEMINI.md`, `INSTRUCTIONS.md`, `WORKFLOWS.md`, `global/agents/AGENT_SET.md`, `global/agents/deep-scanner.md`, `global/agents/lead-security-auditor.md`, `global/roles.md`, and `security-mesh/src/agent-registry.ts` / `gemini.ts`. Existing synthetic persistence scripts remain disabled. | Journal: NO JOURNAL: workspace-wide process correction; no active bounty session record was created.
- 2026-10-14 | A deployment report treated unsupported chain metadata as verified, and local untracked PoC files were liable to be cited as though pinned to upstream commits. | Rewrote `bounties/base/evidence/agent1_scope_deployment_report.md`, withdrew the unpreserved Base RPC claim in `agent2_f001_investigation_report.md`, added `[LOCAL]` provenance guidance to `INSTRUCTIONS.md` §2.6, `.gemini/GEMINI.md` §4.3, the Cantina skill, and the helper CLI, and recorded hashes/status for local PoCs in `bounties/base/logs/local_harness_hashes_2026-10-14.json`. | Journal: `bounties/base/journal.md#2026-10-14-1541-PT-EVIDENCE-REVIEW`
- **L-001** (2026-10-16) [oracle,sequencer,decimals]: 2026-10-16: V4Oracle sequencer uptime & decimal shift attack vectors were already comprehensively addressed in Scan #2 via V4LE-2 (_requireSequencerUp on all modes), V4LE-112 (live decimals re-read), and V4LE-154/V4OracleRecovery (fresh post-restart round + full twap window for borrow). Future oracle reviews must check audit-scan2-findings.md first.
- **L-002** (2026-10-16) [vault,debt-limits,settled-supply]: 2026-10-16: V4Vault daily debt limit and token concentration caps are strictly bounded by `_settledLentAssets` (net of daily inflows exceeding `dailyLendIncreaseLimitMin`), which nullifies flash deposit manipulation of debt quotas (V4LE-122, V4LE-127). Future vault capacity reviews must check `_settledLentAssets` before hypothesizing same-day deposit-borrow expansion.
- **L-003** (2026-10-16) [hook,liquidity-sender,auction-drip]: 2026-10-16: RevertHook liquidity callbacks enforce caller authorization via `_checkLiquiditySender` (PositionManager/self only) and drip auction yield prior to liquidity modification settling (`_notifyAuctionLiquidityChange`), eliminating sandwiching and uncompensated fee extraction vectors. Future hook fee reviews must check sender authentication and auction drip timing.
- **L-004** (2026-10-16) [automator,transformer,access-control]: 2026-10-16: Automators and Transformers implement two-tier custody validation (`_validateCaller` checking `vault.transformedTokenId()` or NFT ownership) and force full debt settlement before exit swaps or collateral releases (V4LE-100, V4LE-102, V4LE-117, V4LE-134). Future automator reviews must verify `transformedTokenId` binding and debt priority order before hypothesizing uncollateralized asset extraction.

- **L-001** (2026-10-19) [cei,transient-storage,spend-permissions]: SpendRouter is completely stateless; SpendPermissionManager commits cumulative spend in _useSpendPermission before invoking _transferFrom (strict CEI), and resets transient _expectedReceiveAmount immediately upon receipt of ETH, eliminating reentrant double-spending.
- **L-002** (2026-10-19) [erc-6492,caller-isolation,smart-wallet]: PublicERC6492Validator is an unprivileged singleton. External calls executed during ERC-6492 side-effects (prepareTo.call) originate from the validator address and cannot invoke onlyOwner methods on CoinbaseSmartWallet or privileged functions on SpendPermissionManager.
- **L-003** (2026-10-19) [period-arithmetic,overflow,spend-permissions]: SpendPermissionManager enforces half-open [start, end) validity with 256-bit overflow-safe period clamping; timestamps equal to end revert immediately with AfterSpendPermissionEnd, preventing boundary race conditions.
- **L-004** (2026-10-19) [webauthn,secp256r1,malleability]: WebAuthn secp256r1 signature verification enforces s <= n/2 against malleability and commits to raw clientDataJSON via SHA-256 in the signed message payload.
- **L-005** (2026-10-19) [smart-wallet,replayable-nonce,cross-chain]: CoinbaseSmartWallet isolates replayable nonce key 8453 strictly to executeWithoutChainIdValidation with a fixed selector whitelist, requiring explicit owner bytes on removals to prevent cross-chain desynchronization.
- **L-006** (2026-10-19) [multiownable,access-control,smart-wallet]: MultiOwnable prevents duplicate owner registration and calculates ownerCount strictly as nextOwnerIndex - removedOwnersCount, guarded by LastOwner and NotLastOwner checks.

- 2026-10-21 | WETHSolvencyVerifierWorkflow attempted to verify DelayedWETH invariants on targets lacking DelayedWETH contracts, missing a clean NOT_APPLICABLE short-circuit. | Added target contract inspection check in universal_adaptive_engine/workflows/operations/delayed_weth_pipeline.py (§WETHSolvencyVerifierWorkflow.execute) returning NOT_APPLICABLE with limitations when DelayedWETH is absent. | Journal: NO JOURNAL: operational engine regression fix; tested in tests/universal_adaptive/test_usap_architecture.py.
- 2026-10-21 | COMPLETION_REPORT stage in universal pipelines returned a false COMPLETED_VERIFIED verdict even when prior pipeline stages accumulated limitations or optional failures. | Updated AgentPipeline.execute in universal_adaptive_engine/workflows/base.py (§execute) to propagate accumulated limitations and downgrade final completion state to COMPLETED_WITH_LIMITATIONS. | Journal: NO JOURNAL: core workflow state machine fix; tested in tests/universal_adaptive/test_workflows.py.
- 2026-10-21 | UniversalAdaptiveOrchestrator.run_operation alias routing defaulted to HostEnvironmentAdapter instead of CantinaBountyAdapter when executing named operations within Cantina workspaces. | Updated adapter dispatch in universal_adaptive_engine/workflows/agents/orchestrator.py (§run_operation) and universal_adaptive_engine/adapters/cantina_adapter.py to bind CantinaBountyAdapter for named domain operations. | Journal: NO JOURNAL: CLI operational routing fix; tested in tests/universal_adaptive/test_operation_pipelines.py.
- 2026-10-21 | VerticalSliceOrchestrator.run_vertical_slice hardcoded completion_state="COMPLETED_VERIFIED" without evaluating the independent challenger negative control outcome. | Added challenger falsification evaluation in universal_adaptive_engine/harness/orchestrator.py (§run_vertical_slice) marking the run state FAILED whenever negative controls fail. | Journal: NO JOURNAL: vertical slice verification gate fix; tested in tests/universal_adaptive/test_harness_vertical_slice.py.
- 2026-10-21 | TargetContextResolver resolved bounty_slug to the innermost subdirectory name when passed nested contract paths (e.g. bounties/base/contracts), losing parent scope.md resolution. | Added top-level bounty slug detection in universal_adaptive_engine/models/target_context.py (§TargetContextResolver._resolve_bounty_slug) to walk up and resolve the parent bounty directory and scope.md. | Journal: NO JOURNAL: target resolution fix; tested in tests/universal_adaptive/test_usap_architecture.py.
