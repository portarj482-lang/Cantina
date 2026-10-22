# Cantina Roles, Jobs, and Functions

**Date:** 2026-10-11
**Status:** Assignment only. Nothing in this file has run.
**Active bounty for the status column:** pump-fun (Solana program, scope in `bounties/pump-fun/scope.md`).
**Inputs reviewed:** the 1,854-line title cross-product (`adfda3ea-attachment.txt`), `cantina_agents.md` v1.0 (36 agents, Parts A to E), and Appendix A (43 titles from the revert-v4lend upload).

---

## 1. Review of the title upload

**What it is.** 150 headings. Each heading is one of 5 lanes (Actor, Role, Tenant, Object, Action, plus Role-Agent and Tenant-Agent variants) crossed with 3 families (base, Response Evidence, Taxonomy Mapping) and 10 component groups. It holds 1,550 distinct title lines. The titles come from combining words. None of them names a job, a tool, an input, or an output.

**Problems.**

1. **Titles are not jobs.** "Scope Status," "Policy Revision Date," and "Test Data" are fields in project records. A field has no owner, so "Scope Status Auditor" is not a role anyone can hold.
2. **Most component words describe an AI application, not a Solana program.** Prompting, Conversation State, Model, Provider, API Version, Developer Instructor, and System Instructor have no counterpart in an instruction-and-account program. The target has instructions, accounts, PDAs, fee accounts, and CPIs.
3. **Garbled forms.** "Analysts" and "Analyst" appear side by side. Word order flips ("Scope Status Developer Analyst" and "Developer Analysts"). The same role appears under several names.
4. **"Oracle" prefixes every heading.** In DeFi it usually means a price feed. The word names nothing in this project, so it is dropped.
5. **No check role.** GEMINI requires the step that verifies a lead to be separate from the step that produced it. The upload contains producer titles only.
6. **Scale.** 1,550 names against 36 defined agents leaves most of them with no agent, no tool, and no owner. Ownership is what decides who may claim a finding.

**What is kept.** The lanes are useful as questions for the mapper (R4) and the deep reviewer (R8):

- **Actor:** who signs, or holds authority over, each instruction?
- **Role:** what may each authority do, and does the program check it on chain?
- **Object:** which accounts does each instruction bind, and which are unbound?
- **Action:** which instruction runs, in what order, and what happens if it runs twice?
- **Component:** which program or module owns each piece of state?
- **Tenant (reinterpreted):** does one bonding curve's state affect another curve? This is per-mint isolation.

**What is dropped.** Prompting, Conversation State, Model, Provider, API Version, Developer Instructor, and System Instructor. The Response Evidence and Taxonomy Mapping families are covered by the tool runners (R5) and the normalizer (R6), so they are not separate roles.

---

## 2. Roles

Each role has one job, a list of what it writes, and a list of what it must not do.

| ID | Role | Job | Writes | Must not |
|---|---|---|---|---|
| R0 | Owner (user) | Sets scope, confirms the severity scale, approves installs and any network write, decides Ready and Submitted | `scope.md`, `artifacts/review_decision.json`, final status | Nothing delegated |
| R1 | Lead | Chooses which leads run, gives each agent one narrow task, accepts results only from saved artifacts | `state.md`, finding files at Draft | Set Ready or Submitted. Accept a sub-agent's verdict with no artifact. Type a severity by hand |
| R2 | Sequencer | Runs stages in order and records every stop and skip | Session ledger lines, stage table | Judge evidence |
| R3 | Pin keeper | Confirms commit, scope hash, and tool status. Creates the build copy | Snapshots, build copy | Edit the checkout |
| R4 | Mapper | Writes factual maps: entry points, privileged roles, external calls, value flow, instruction and account graph | Map rows, each with a `[SRC]` tag | Judge exploitability or severity |
| R5 | Tool runner | Runs one tool, saves its raw output and version | `scans/<date>_<tool>/` | Summarize output as evidence. Assign severity |
| R6 | Normalizer | Converts paths, lines, and rule IDs. Drops and logs anything invalid | `findings.json` | Invent categories |
| R7 | Known-issue checker | Compares leads with the program's known issues and accepted risks | Annotations on each lead | Delete a lead |
| R8 | Deep reviewer | Traces one lead and challenges both confirmation and falsification conditions | `SUPPORTED`, `REFUTED`, or `UNRESOLVED`, with artifact-level evidence and limits | Treat source lines, model output, or process status as proof of deployed behavior or impact; assign severity |
| R9 | Triage (opt-in) | Groups, ranks, and explains candidates. May send one function's context to an external model | Group and rank files | Run without manifest and scope permission |
| R10 | Citation checker | Checks each citation and identifier against the build copy. Drops failures | Drop log | Rewrite claims |
| R11 | Prover | Writes the PoC and counter-test under Part B | Test files and raw run records; reports what assertions establish | Decide whether its own test passes or label a finding confirmed |
| R12 | Proof gate | Runs each test five times on two planes and checks the post-fix test | Gate result | Write or edit a test |
| R13 | Reviewer packet | Builds the packet the owner reviews before anything is submitted. Ends the pipeline | Review packet | Set Ready or Submitted |

**Separation of duties.**

- A lead's producers (R4, R5, R8) may not also be its checkers (R10, R12).
- The prover (R11) and the proof gate (R12) are different agents.
- R1 accepts results from artifacts only (A5 in `cantina_agents.md`).

---

## 3. Assignment for pump-fun

**Current blockers.**

- **Program source is NOT PROVIDED.** `scope.md` lists only three IDL files, so every role that needs a code path is blocked.
- **No Solana tool is installed.** `solana`, `solana-test-validator`, and `anchor` are MISSING. `tsx` is OK in this container.
- **The program's known-issue list is NOT PROVIDED.** Any role that compares against it finds nothing.

| Role | Agent(s) from `cantina_agents.md` | Status for pump-fun | Reason |
|---|---|---|---|
| R0 Owner | user | Active | Scope, approvals, and final decisions |
| R1 Lead | lead-security-auditor | Limited: leads from the IDL and public incidents only | Source-based leads are blocked |
| R2 Sequencer | pipeline-orchestrator | Active for the `verify` and `known` stages | The `build`, `scan`, `fuzz`, and `poc` stages in `run_pipeline.sh` are Foundry-based and inactive |
| R3 Pin keeper | source-pin | Partial: scope hash and tool versions only | No program source commit is in scope, so there is no build copy |
| R4 Mapper | bounty-scanner, pathway-scout | Blocked on source | Both read Solidity source. An IDL alone is not a code path |
| R5 Tool runner | slither-runner, aderyn-runner, sarif-collector, forge-inspect-layout, layout-diff, forge-unit-runner, forge-fuzz-runner, forge-invariant-runner, echidna-executor, medusa-executor | Inactive | Solidity and Foundry tools. No Solana equivalent exists yet (see §4) |
| R6 Normalizer | normalize-file, normalize-line | Active after a candidate exists. Needs the build copy | Both check paths against the build copy |
| R6 Normalizer | normalize-rule | Inactive | Rule IDs come from tools that are not installed |
| R7 Known-issue checker | known-tags-scan, known-overlap-annotator | Runs, finds nothing until the program's list is provided | The known list is NOT PROVIDED |
| R7 Known-issue checker | known-accepted-risk | Inactive | Extracts Solidity NatSpec. Solana uses Rust doc comments, which need a new parser |
| R8 Deep reviewer | deep-scanner | Blocked on source | Needs a code path to trace |
| R9 Triage | triage-gemini-runner, triage-schema-guard, triage-group, triage-rank, triage-explain | Inactive | `scope.md` does not permit an external model. `triage-explain` writes Foundry tests |
| R10 Citation checker | hallucination-dropper | Active once a candidate exists | Checks against the build copy, or against the IDL copy for IDL citations |
| R11 Prover | forge-tester | Inactive | Foundry. A Solana PoC author is needed (see §4) |
| R12 Proof gate | proof-gate | Inactive | This role currently supports EVM fork workflows only. Solana reproduction requires an Anchor/Solana harness; two RPC endpoints at one slot are a consistency check, not equivalent dual-fork execution. |
| R13 Reviewer packet | review-packet-builder | Active when a lead reaches Draft | Nothing has reached Draft |

**Agents for other bounties.** The 43 titles in Appendix A of `cantina_agents.md` belong to the revert-v4lend pipeline and are not assigned here.

---

## 4. Solana extension roles (defined in global/agents/)

These roles govern Solana audit and PoC workflows. Specifications are written under `global/agents/`. Each role has a job, an input, an output, and its current execution blocker.

| ID | Role | Specification | Job | Input | Output | Execution Blocker |
|---|---|---|---|---|---|---|
| G1 | IDL surface mapper (R4) | `global/agents/g1-idl-mapper.md` | Lists instructions, accounts, writable and signer flags, PDA seeds, and CPI targets | Pinned IDL | Map rows, each with `[SRC]` | None; active against pinned IDL and pump-rust-client |
| G2 | Account binding checker (R8 variant) | `global/agents/g2-binding-checker.md` | For each account a caller supplies, checks whether the program binds it to an expected identity | Map from G1, client state models | Lead, or `BOUND` / `NEEDS-SOURCE` | None for client models; source needed for full bytecode constraint check |
| G3 | Conservation checker (R5) | `global/agents/g3-conservation-checker.md` | After each instruction, checks that reserves, fees, rent, and lamports still sum to the total | Local validator run / math model | `result.json` | `solana-test-validator` is MISSING; active via tsx / Rust math models |
| G4 | Local-validator runner (R5) | `global/agents/g4-validator-runner.md` | Runs Anchor or `tsx` tests against a local validator. Records seed and slot | Test script | Run record with `command.txt` and `version.txt` | `solana` and `anchor` are MISSING. `tsx` is OK here |
| G5 | Solana PoC author (R11) | `global/agents/g5-solana-poc.md` | Writes tests that call the real instructions. Never reproduces the logic in the test | G1 map, G4 runner | Test file | Active via tsx harnesses in `poc/` |

---

## 5. Order of work

1. **Settle the canonical copy.** The Windows copy and this workspace disagree on scope, phase, and findings. Compare the scope hash on both copies. The scope is the input every role depends on.
2. **Provide the program source repository and the pinned commit.** This unblocks R4, R8, the R3 build copy, and G2.
3. **Approve the Solana install** in this container, or confirm the Windows machine as the environment for G3 and G4. Install needs a clear yes, and the earlier yes covered only the Windows machine.
4. **Build G1 through G5 before any PoC.** R11 writes nothing until G1 and G4 are in place.

Until steps 1 to 3 are done, the only roles that can run are R0, R2 (partly), R7 (on the IDL and public incidents), and R13 once a lead reaches Draft.

---

## 6. Base Tier 0 Fault Dispute & Multiproof Attestation Roles (Option B)

These roles govern Option B: Tier 0 Fault Dispute System, DelayedWETH Solvency & Multiproof TEE Attestation under `bounties/base/`. Specifications are written under `global/agents/` and `.agents/skills/`.

### 6.1 Invariant Orchestration Oracles

| ID | Oracle Role | Specification | Domain / Invariant | Supervised Sub-Agents |
|---|---|---|---|---|
| G4 | Dispute Invariant Oracle | `global/agents/G4_dispute_invariant_oracle.md` | `INV-DISPUTE-01` — Withdrawal finalization monotonicity & dispute game verification | #11, #12, #21, #22, #23 |
| G5 | DelayedWETH Invariant Oracle | `global/agents/G5_delayed_weth_invariant_oracle.md` | `INV-DELAYED-WETH-02` — Balance solvency, sub-account scoping & delay timelocks | #13, #14, #20, #21 |
| G6 | Multiproof TEE Invariant Oracle | `global/agents/G6_multiproof_tee_invariant_oracle.md` | `INV-MULTIPROOF-03` — AWS Nitro attestation, P-384 hints & signer authenticity | #15, #16, #17, #18, #19 |

### 6.2 Target Sub-Oracles & Inherited Contract Agents

| # | Role | Specification | Target Surface | Job | Writes | Must Not |
|---|---|---|---|---|---|---|
| 11 | dispute-prove-agent | `.agents/skills/dispute-prove-agent/` | `OptimismPortal2.proveWithdrawalTransaction` | Synthesize Merkle proofs and record proven withdrawals | `F-PORTAL-PROVE-xxx`, local PoCs | Prove against invalid dispute game root |
| 12 | dispute-finalize-agent | `.agents/skills/dispute-finalize-agent/` | `OptimismPortal2.finalizeWithdrawalTransaction` | Audit airgap, reentrancy guard, and dispatch execution | `F-PORTAL-FINALIZE-xxx`, local PoCs | Bypass proof maturity delay or airgap |
| 13 | weth-unlock-agent | `.agents/skills/weth-unlock-agent/` | `DelayedWETH.unlock` | Verify sub-account scoping and timestamp reset | `F-WETH-UNLOCK-xxx`, local PoCs | Mix caller withdrawal balances |
| 14 | weth-withdraw-agent | `.agents/skills/weth-withdraw-agent/` | `DelayedWETH.withdraw` | Audit pause guards, delay enforcement, and ETH transfer | `F-WETH-WITHDRAW-xxx`, local PoCs | Allow withdrawal before delay expiry |
| 15 | tee-register-agent | `.agents/skills/tee-register-agent/` | `TEEProverRegistry.registerSigner` | Verify COSE Sign1 TBS, PCR0 measurements, register signer | `F-TEE-REG-xxx`, local PoCs | Register debug mode PCR0 enclaves |
| 16 | tee-validity-agent | `.agents/skills/tee-validity-agent/` | `TEEProverRegistry.isValidSigner` | Validate dynamic signer authenticity against active image hash | `F-TEE-VAL-xxx`, local PoCs | Accept stale signer after image rotation |

### 6.3 Sub-Surface Attestation Agents

| # | Role | Specification | Target Surface | Job | Writes | Must Not |
|---|---|---|---|---|---|---|
| 17 | attestation-timestamp-agent | `.agents/skills/attestation-timestamp-agent/` | `TEEProverRegistry.sol:166-168` | Audit millisecond conversion, MAX_AGE (60 min), future timestamps | `F-TEE-TIME-xxx`, boundary tests | Accept attestations > 3600s old or future-dated |
| 18 | inverse-hint-integrity-agent | `.agents/skills/inverse-hint-integrity-agent/` | `crates/proof/tee/registrar/src/hints.rs` | Audit P-384 hint transcript affine schedule and malleability | `F-TEE-HINT-xxx`, Rust unit tests | Permit unverified hint scalar bit-flips |
| 19 | signer-lifecycle-agent | `.agents/skills/signer-lifecycle-agent/` | `TEEProverRegistry.deregisterSigner` | Audit EnumerableSet cleanup and hardfork image rotation | `F-TEE-LIFE-xxx`, state tests | Retain signer validity across hardforks |
| 20 | weth-solvency-agent | `.agents/skills/weth-solvency-agent/` | `DelayedWETH` balance & admin ops | Verify total supply vs ETH balance solvency across recover/hold | `F-WETH-SOLV-xxx`, fuzz tests | Ignore fractional reserve deficits |
| 21 | delay-bypass-agent | `.agents/skills/delay-bypass-agent/` | Dual contract delay boundaries | Falsify temporal off-by-one delay bypasses across delays | `F-DELAY-BYPASS-xxx`, invariant PoCs | Treat boundary equality as strictly greater |
| 22 | game-resolution-agent | `.agents/skills/game-resolution-agent/` | `AnchorStateRegistry` / `AggregateVerifier` | Verify DEFENDER_WINS resolution and bond credit claiming | `F-GAME-RES-xxx`, simulation logs | Allow credit claiming on unfinalized games |
| 23 | blacklist-maturity-agent | `.agents/skills/blacklist-maturity-agent/` | `AnchorStateRegistry.disputeGameBlacklist` | Audit Guardian blacklisting and airgap finality delays | `F-BLACKLIST-xxx`, state logs | Finalize against blacklisted dispute games |
