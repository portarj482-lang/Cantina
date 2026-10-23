# Threat Model: Pump.fun Smart Contracts (W1 Reconnaissance)

**Date:** 2026-10-10  
**Target Contracts:**
- **Pump (Bonding Curve):** `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` [SRC: scope.md:27 @2026-10-10]
- **Pump Fees:** `pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ` [SRC: scope.md:28 @2026-10-10]
- **Pump AMM (PumpSwap):** `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` [SRC: scope.md:29 @2026-10-10]

> **Evidence boundary:** This model was drafted from public documentation and IDLs. These materials describe interfaces and intended behavior; they are not the deployed program source or proof of runtime behavior. The properties below are analyst hypotheses to test, not established protocol invariants. The TypeScript files under `poc/` are offline models and do not execute these programs.

---

## 1. Assets
- **Base Tokens:** SPL Meme Coins minted upon creation (`BondingCurve.real_token_reserves`, `associated_base_bonding_curve`, `pool_base_token_account`).
- **Quote Tokens:** Native SOL (wrapped as WSOL for token accounts) or arbitrary Quote SPL Mints (e.g., USDC, pump-coins) held in curve lamports / token vaults (`BondingCurve.real_quote_reserves`, `associated_quote_bonding_curve`, `pool_quote_token_account`).
- **Protocol Fees:** Accumulated protocol fee shares sitting in curve/pool accounts awaiting sweep (`BondingCurve.protocol_fees`, `Pool.protocol_fees`).
- **Creator Fees:** Accumulated creator fee shares sitting in curve/pool accounts awaiting sweep (`BondingCurve.creator_fee`, `Pool.creator_fees`).
- **LP Shares:** Liquidity provider balances in migrated PumpSwap pools (`Pool.lp_mint`).
- **Privileged Roles:** `Global.authority`, `GlobalConfig.admin`, `BondingCurve.creator`, `Pool.coin_creator`, `FeeSharingConfig.authority`.

---

## 2. Actors
- **Trader / User:** Initiates trades (`buy`, `sell`, `buy_v3`, `sell_v3`, `multi_hop_swap`).
- **Coin Creator:** Deploys new meme coins via `create_v2`; claims/distributes creator fees.
- **CTO (Community Takeover) Authority:** Successor entity designated via `admin_cto` or `admin_cto_pool`.
- **Permissionless Sweeper:** Any account calling `sweep_protocol_fee` or `sweep_creator_fee`.
- **Protocol Admin:** Manages protocol parameters, fee recipients, quote control list (`set_params`, `add_quote_control_mint`).
- **Migrator:** Triggers `migrate_v2` once bonding curve achieves target quote reserves.

---

## 3. Value-Flow Functions
- `Pump::buy_v3` & `Pump::buy_exact_quote_in_v3`: Transfers quote token from user, issues base tokens from curve; on curve completion, executes synthetic pool buy from unmigrated base tokens. [SRC: pump.json:115 @2026-10-10]
- `Pump::sell_v3`: Transfers base tokens from user to curve, pays quote tokens to user; protocol & creator fees accumulate on curve. [SRC: pump.json:200 @2026-10-10]
- `Pump::sweep_protocol_fee`: Moves `BondingCurve.protocol_fees` to designated protocol fee recipient. [SRC: pump.json:240 @2026-10-10]
- `Pump::sweep_creator_fee`: Moves `BondingCurve.creator_fee` to creator vault PDA. [SRC: pump.json:265 @2026-10-10]
- `Pump::migrate_v2`: Permissioned/permissionless migration of completed bonding curve liquidity to a newly initialized PumpSwap pool. [SRC: pump.json:310 @2026-10-10]
- `PumpSwap::buy_v2` & `PumpSwap::sell_v2`: Constant-product AMM trades; fees accumulate in pool quote vault and adjust `virtual_quote_reserves`. [SRC: pump_amm.json:85 @2026-10-10]
- `PumpSwap::multi_hop_swap`: Sequential swap across 2+ pools/curves without intermediate user token accounts. [SRC: pump_amm.json:160 @2026-10-10]
- `PumpFees::distribute_creator_fees_v2`: Distributes swept creator fees among configured share recipients. [SRC: pump_fees.json:45 @2026-10-10]

---

## 4. Oracle Reads & External Calls
- **Oracle Reads:** Pump.fun does not rely on external Chainlink or Pyth price feeds for curve pricing; pricing is purely deterministic constant-product. [SRC: pump-public-docs/README.md:9 @2026-10-10]
- **CPI Calls:**
  - `spl_token::instruction::transfer` / `transfer_checked` to move base and quote tokens.
  - `system_instruction::transfer` for native SOL transfers.
  - Cross-program invocations between Pump and PumpSwap during `migrate_v2` and `multi_hop_swap`.

---

## 5. Privileged Writes
- `Global::set_params`: Updates migration fee, fee percentages, and fee recipient addresses. [SRC: pump.json:420 @2026-10-10]
- `Global::add_quote_control_mint`: Adds authorized quote mints. [SRC: pump.json:10 @2026-10-10]
- `BondingCurve::admin_cto`: Transfers creator authority to new CTO entity. [SRC: pump.json:450 @2026-10-10]
- `Pool::admin_cto_pool`: Transfers pool creator authority. [SRC: pump_amm.json:10 @2026-10-10]
- `PumpFees::update_fee_shares_v2`: Alters distribution weights for creator fee sharing. [SRC: pump_fees.json:110 @2026-10-10]

---

## 6. Trust Assumptions
- `[ASSUMPTION]`: All token transfers strictly succeed or revert; fee-on-transfer / rebasing tokens are excluded or prevented by quote control list.
- `[ASSUMPTION]`: The synthetic migration pool pricing formula precisely mirrors PumpSwap AMM constant-product curve without precision drift.
- `[ASSUMPTION]`: Negative `virtual_quote_reserves` adjustments on PumpSwap cannot be manipulated to cause underflow or negative effective reserves.
- `[ASSUMPTION]`: Sweeping fees is truly permissionless and cannot be DoS'd by frontrunning with dust or malformed accounts.

---

## 7. Candidate Properties (INV-###; unverified hypotheses)

Each statement below is a proposed property inferred from the cited documentation. Confirm its exact preconditions and behavior against the deployed Devnet program before calling it an invariant or using it to classify a finding. A documentation citation alone does not establish implementation behavior.

### INV-001: Synthetic Migration Price Continuity
- **Statement:** The marginal exchange rate of the final token purchased from the bonding curve must transition continuously into the initial exchange rate charged for tokens purchased from the synthetic pool during `buy_v3`.
- **Source:** [SRC: pump-public-docs/docs/SYNTHETIC_MIGRATION.md:10 @2026-10-10]

### INV-002: Base Token Conservation on Synthetic Migration
- **Statement:** For any completing curve, `associated_base_bonding_curve.amount == bonding_curve.real_token_reserves + pool_base_allocation`. Total tokens allocated to the user across the curve part and pool part must not exceed available reserves.
- **Source:** [SRC: pump-public-docs/docs/SYNTHETIC_MIGRATION.md:30 @2026-10-10]

### INV-003: Effective Quote Reserves Invariance to Waiting Fees
- **Statement:** In PumpSwap pools, `effective_quote_reserves = pool_quote_token_account.amount + Pool.virtual_quote_reserves` must remain invariant before and after any fee sweep.
- **Source:** [SRC: pump-public-docs/docs/VIRTUAL_QUOTE_RESERVES_FEE_ADJUSTMENT.md:17 @2026-10-10]

### INV-004: Solvency of Accumulated Fees
- **Statement:** The lamports/tokens in the bonding curve vault must always satisfy: `vault_balance >= real_quote_reserves + protocol_fees + creator_fee + rent_exempt_minimum`.
- **Source:** [SRC: pump-public-docs/docs/instructions/SWEEP_FEES.md:7 @2026-10-10]

### INV-005: Rounding Safety in Constant-Product Trades
- **Statement:** Rounding in `buy_v3` and `sell_v3` must strictly favor the protocol/pool: quote required (`quote_in`) must be rounded up (`ceil`), and base tokens distributed (`tokens_out`) must be rounded down (`floor`).
- **Source:** [SRC: pump-public-docs/docs/SYNTHETIC_MIGRATION.md:34 @2026-10-10]

### INV-006: Exclusive Synthetic Crossing Lock
- **Statement:** Only the single transaction that transitions `BondingCurve.complete` from `false` to `true` may access synthetic pool tokens. Any subsequent trade before migration must immediately revert with `BondingCurveComplete`.
- **Source:** [SRC: pump-public-docs/docs/SYNTHETIC_MIGRATION.md:17 @2026-10-10]

### INV-007: Mandatory Fee Sweep Precondition
- **Statement:** Instructions modifying creator ownership or share percentages (`admin_cto`, `admin_cto_pool`, `update_fee_shares_v2`) must strictly revert with `CreatorFeesNotSwept` if unswept creator fees exist.
- **Source:** [SRC: pump-public-docs/docs/instructions/SWEEP_FEES.md:46 @2026-10-10]

### INV-008: Intermediate Balance Non-Stranding in Multi-Hop Swaps
- **Statement:** Upon completion of `multi_hop_swap`, no intermediate base or quote tokens may remain in any temporary or protocol-owned account.
- **Source:** [SRC: pump-public-docs/README.md:6 @2026-10-10]

### INV-009: Strict Positivity of Effective Reserves
- **Statement:** Under all trading and fee conditions, `pool_quote_token_account.amount + Pool.virtual_quote_reserves > 0` and must never overflow `i128`.
- **Source:** [SRC: pump-public-docs/docs/VIRTUAL_QUOTE_RESERVES_FEE_ADJUSTMENT.md:44 @2026-10-10]

### INV-010: Quote Mint Scaling & Fee Separation
- **Statement:** Protocol fee percentages and initial virtual quote reserves must correctly adapt to the quote mint's decimal precision and denomination without cross-pair decimal distortion.
- **Source:** [SRC: pump-public-docs/README.md:99 @2026-10-10]
