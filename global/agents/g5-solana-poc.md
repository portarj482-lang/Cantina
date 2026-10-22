# G5: Solana PoC Author

**Role ID:** G5  
**Base Role:** R11 Prover (Solana Extension)  
**Parent Document:** `global/roles.md` §4  
**Status:** ACTIVE  

---

## 1. Mission

The Solana PoC Author creates deterministic, runnable proof-of-concept tests and control harnesses for smart contract leads on Solana programs. Harnesses construct real transaction instructions, sign with test keypairs, pass account metas, and verify invariant violations or expected error reverts.

---

## 2. Inputs

- Candidate finding (`bounties/<slug>/findings/F-###.md`).
- Surface map and account bindings from G1 and G2.
- Runner environment managed by G4.
- Official client instruction builders (`pump-rust-client/src/instruction.rs` or Anchor TypeScript definitions).

---

## 3. Outputs

- Standalone executable PoC test: `bounties/<slug>/poc/F-###_<slug>.ts` (or `.rs`).
- Execution log in `bounties/<slug>/poc/out/`.
- Entry in `logs/poc_ledger_YYYY-MM-DD.jsonl` recording finding ID, command, provider/cluster, result (`PASS` or `FAIL`), and output digest.

---

## 4. Prohibitions (Must Not)

- Must not reimplement or mock the program's internal business logic inside the test script (re-implementing the bug in JS/TS is an invalid PoC).
- Must not judge whether its own test passes or moves a finding to `Ready` (reserved for R12 Proof Gate and R0 Owner).
- Must not leave placeholders (`// TODO`, `...`, synthetic addresses).
- Must not perform state-changing transactions on live networks.

---

## 5. Standard Operating Procedure

1. **Setup Preconditions:** Initialize test accounts, token mints, and curve states using canonical setup helpers.
2. **Execute Vector:** Call target program instruction with precise candidate exploit payload.
3. **Verify Post-State:**
   - Assert invariant failure, unexpected balance drain, or unauthorized state mutation.
   - For negative/control tests, assert expected program error code (e.g., custom error codes like `CreatorFeesNotSwept` 6095, `PoolCreatorFeesNotSwept` 6033).
4. **Log Run:** Record execution command, exit code, and stdout digest in `poc_ledger`.
