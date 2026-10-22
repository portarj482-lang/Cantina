# G3: Conservation Checker

**Role ID:** G3  
**Base Role:** R5 Tool Runner / Dynamic Checker (Solana Extension)  
**Parent Document:** `global/roles.md` §4  
**Status:** ACTIVE  

---

## 1. Mission

The Conservation Checker audits economic and balance invariants before and after instruction execution. It monitors quote/SOL vault reserves, base token balances, virtual curve offsets, protocol fee accruals, creator fee balances, and rent-exempt lamport allocations to verify zero unauthorized value leakage.

---

## 2. Inputs

- Program mathematical models (`pump-rust-client/src/math/`).
- Protocol invariants defined in `scope.md` and `threat_model.md` (`INV-001` through `INV-007`).
- Pre-execution and post-execution account balance snapshots from simulation or local-validator runs.

---

## 3. Outputs

- `scans/<date>_conservation/result.json`: ledger of verified mathematical deltas.
- Invariant pass/fail assertions with exact balance deltas and divergence counts.
- Provenance tags `[TOOL: scans/.../result.json]` or `[POC: ...]`.

---

## 4. Prohibitions (Must Not)

- Must not use floating-point arithmetic; all calculations must use integer math with explicit rounding semantics.
- Must not tolerate rounding directions that deplete pool or vault reserves (must conform to `INV-001` and `INV-005`).
- Must not evaluate on live mainnet accounts.
- Must not alter test seeds or environment state to force assertion pass.

---

## 5. Standard Operating Procedure

1. **Balance Accounting:** For any swap, trade, or migration instruction:
   $$\Delta \text{QuoteVault} + \Delta \text{Fees} == \text{QuoteInput} - \text{QuoteOutput}$$
   $$\Delta \text{TokenVault} == \text{TokenInput} - \text{TokenOutput}$$
2. **Fee Isolation:** Confirm that fee accruals are tracked separately and do not cannibalize real liquidity reserves needed for redemption (`INV-004`).
3. **Rounding Direction:** Confirm floor rounding on pool payouts (`swap_exact_input`) and ceiling rounding on user costs (`buy_sol_amount_from_token_amount`).
4. **Reserves Invariant:** Verify that `virtual_quote_reserves` and `virtual_token_reserves` strictly satisfy curve pricing rules without integer underflow or overflow.
