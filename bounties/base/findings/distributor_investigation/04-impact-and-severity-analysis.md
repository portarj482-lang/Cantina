# 04 — Impact and Severity Analysis: Coinbase Echo Distributor

**Finding Reference:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Target Contract:** `Distributor.sol` (`0x1798D23f29968b4fff7A60A90645B0939d04f47E` on Base Mainnet)  
**Authoring Persona:** `META-QUALIA: CANTINA EXECUTION-BUILDING AGENT (MQ-CANTINA-DISTRIBUTOR-001)`  
**Repository Source:** [Distributor.sol](https://github.com/portarj482-lang/Cantina/blob/main/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol)  
**Basescan Verification:** [0x1798D23f29968b4fff7A60A90645B0939d04f47E](https://basescan.org/address/0x1798D23f29968b4fff7A60A90645B0939d04f47E#code)  

---

## 1. Mathematical Derivation of Performance Fee (Carry) Accounting

In Coinbase Echo SPVs, carried interest represents the deal lead and platform's performance fee (typically 2000 bps = 20%) charged on capital gains once the investor's principal capital hurdle has been recovered.

### 1.1 Formula Specification

According to [`_calculateCarryAmountUSDC`](https://github.com/portarj482-lang/Cantina/blob/main/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol#L349-L361):

$$R_{\text{free}} = \max(0, I_{\text{USDC}} - C_{\text{claimedUSDC}})$$

$$A_{\text{carryUSDC}} = \max(0, A_{\text{claimUSDC}} - R_{\text{free}})$$

$$\text{Carry}_{\text{USDC}} = \left\lfloor \frac{A_{\text{carryUSDC}} \times \text{totalCarryBPS}}{10000} \right\rfloor$$

$$\text{Carry}_{\text{token}} = \text{PriceLib.convertUSDCToToken}(\text{Carry}_{\text{USDC}})$$

Where:
- $I_{\text{USDC}}$ = Initial invested capital in USDC (`amountInvestedUSDC`)
- $C_{\text{claimedUSDC}}$ = Cumulative USD value previously claimed (`_claimerState[entityUUID].amountClaimedUSDC`)
- $A_{\text{claimUSDC}}$ = USD value of the current claim, computed as $\text{PriceLib.convertTokenToUSDC}(A_{\text{claim}})$
- $\text{totalCarryBPS}$ = Performance fee basis points (e.g. 2000 = 20%)

### 1.2 The Valuation Evasion Divergence

When a voucher from Tranche 1 (token price $P_1$) is replayed during Tranche 2 (market token price $P_2$, where $P_2 > P_1$):

1. **Under Honest Claim ($P_2 = \$10.00$):**
   - Claim amount: $400 \text{ tokens}$
   - $A_{\text{claimUSDC}} = 400 \times \$10.00 = 4,000 \text{ USDC}$
   - With $I_{\text{USDC}} = 1,000 \text{ USDC}$ and prior claims $C_{\text{claimedUSDC}} = 400 \text{ USDC}$:
     $$R_{\text{free}} = 1,000 - 400 = 600 \text{ USDC}$$
     $$A_{\text{carryUSDC}} = 4,000 - 600 = 3,400 \text{ USDC}$$
     $$\text{Carry}_{\text{USDC}} = 3,400 \times 20\% = 680 \text{ USDC}$$
     $$\text{Carry}_{\text{token}} = \frac{680}{\$10.00} = 68 \text{ tokens}$$
   - **Net Payout:** Investor receives $400 - 68 = 332 \text{ tokens}$ (\$3,320); Deal Lead receives $68 \text{ tokens}$ (\$680).

2. **Under Replay Exploit ($P_1 = \$1.00$ replayed when market is $\$10.00$):**
   - Replayed voucher inputs: `amount = 400`, `price = $1.00`
   - $A_{\text{claimUSDC}} = 400 \times \$1.00 = 400 \text{ USDC}$
   - Hurdle calculation:
     $$R_{\text{free}} = 1,000 - 400 = 600 \text{ USDC}$$
     $$A_{\text{carryUSDC}} = \max(0, 400 - 600) = 0 \text{ USDC}$$
     $$\text{Carry}_{\text{USDC}} = 0 \text{ USDC}$$
     $$\text{Carry}_{\text{token}} = 0 \text{ tokens}$$
   - **Net Payout:** Investor receives $400 - 0 = 400 \text{ tokens}$ (market value **\$4,000**).
   - **Loss:** Deal Lead and Platform receive **0 tokens** instead of **68 tokens**.
   - **Net Stolen Performance Fee:**
     $$\Delta \text{Carry} = 68 \text{ tokens} = \$680.00 \text{ USDC (100\% evasion)}$$

---

## 2. Concrete Real-World Exploit Scenario

### 2.1 The Coinbase Echo Syndicate Context

Coinbase Echo operates as an on-chain syndication platform enabling SPV managers (deal leads) to pool capital on Base mainnet to invest in high-growth Web3 protocols.
- **Example SPV:** Echo SPV Syndicate Alpha
- **Total SPV Capital:** \$1,000,000 USDC
- **Underlying Deal:** 10,000,000 Protocol Governance Tokens acquired at Seed valuation (\$0.10/token).
- **Deal Lead Terms:** 20% carry (`totalCarryBPS = 2000`) on net profits.
- **Vesting Schedule:** 2-year linear vesting unlocked in tranches via Echo Unlocker contracts.

### 2.2 Chronological Exploit Walkthrough

```
Timeline of Events in Real-World Exploit:
───────────────────────────────────────────────────────────────────────────
[Month 0]   Token Listing: Token lists at $0.10.
            Investor Mallory has 10,000 SPV shares (1% = $10,000 capital).
            Unlocker releases Tranche 1 (10% = 100,000 tokens for Mallory).

[Month 1]   Mallory receives legitimate EIP-712 voucher for 50,000 tokens at $0.10.
            Voucher validity: valid for 90 days (expiresAt = block.timestamp + 90 days).
            Mallory claims Tranche 1:
            - Face Value: $5,000
            - Hurdle remaining: $10,000 - $5,000 = $5,000
            - Carry deducted: $0
            - Mallory receives: 50,000 tokens.

[Month 2]   Major Protocol Catalyst: Token price appreciates 10x to $1.00.
            Unlocker releases Tranche 2 (another 100,000 tokens for Mallory).
            Platform backend prepares honest voucher: 50,000 tokens at $1.00.
            Honest Carry owed: ($50,000 - $5,000) * 20% = $9,000 (9,000 tokens).

[Month 2.1] EXPLOITATION:
            Mallory bypasses frontend.
            Mallory takes Month 1 voucher calldata (still unexpired, valid for 60 more days).
            Mallory executes Distributor.claimTokens(voucher_tranche_1).
            Contract checks:
            - EIP-712 user signature: VALID
            - EIP-712 platform signature: VALID
            - Claimable balance: 50,000 tokens available (shares permit it)
            - Digest tracking: NONE (missing nullifier check)
            - Valuation: Evaluated at $0.10 instead of current $1.00!
            - Hurdle calculation: $5,000 <= remaining hurdle ($5,000) -> Carry = $0!
            Mallory receives: 50,000 tokens (actual market value $50,000).
            Carry generated: 0 tokens (expected 9,000 tokens = $9,000).

[Month 2.2] FINANCIAL DAMAGE:
            - Deal lead loses 9,000 tokens ($9,000 USD) permanently.
            - Mallory defrauds 100% of performance fees owed to syndicate managers.
            - Contract internal accounting (amountClaimedUSDC) permanently desynchronizes.
───────────────────────────────────────────────────────────────────────────
```

### 2.3 Secondary Exploit: Unauthorized Carry Pool Liquidation

A distinct, severe vulnerability exists in [`withdrawCarry`](https://github.com/portarj482-lang/Cantina/blob/main/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol#L393-L442):
1. **Public Execution Vector:** The function is completely public (`external onlyIf(isEnabled)`):
   > *"There is no additional access control on the function, which allows anyone to execute a claim as long as the signatures are valid."*
2. **Replay Condition:** Neither `CarryWithdrawalData` nor `Distributor` checks digest reuse or caller identity.
3. **Mempool Exploitation:**
   - Deal lead Bob has accumulated 50,000 tokens in carry fees.
   - Bob signs a partial withdrawal voucher for 10,000 tokens (e.g. to cover quarterly operational expenses).
   - An MEV searcher or malicious observer copies `data`, `userSignature`, and `platformSignature` from the mempool or transaction receipt.
   - The observer submits 4 additional transactions replaying the exact same calldata.
   - Each transaction executes successfully, draining 10,000 tokens per call until `_carryWithdrawable` reaches 0.
   - **Consequence:** Bob's accrued carry is forcibly, prematurely liquidated. If Bob's receiver address is an operational multisig, tax-sensitive wallet, or exchange deposit address, this causes irrevocable tax consequences, gas griefing, and liquidity dislocation.

---

## 3. Strict Boundary Analysis: What Cannot Be Stolen

To maintain strict evidentiary integrity, we explicitly define the boundaries of the exploit:

1. **Other Investors' Principal Is Safe:**
   - The contract verifies `claimableAmount = _claimable(entityUUID, user.distributionShares, false)`.
   - `_claimable` computes `Math.mulDiv(totalReceived, distributionShares, totalDistributionShares) - amountClaimed`.
   - An attacker cannot claim more tokens than their pro-rata share of total unlocked SPV tokens.
   - Therefore, the exploit does **not** drain principal tokens allocated to innocent investors.

2. **Gross Claim vs. Net Theft:**
   - If an attacker replays a voucher for 400 tokens twice, the total gross tokens transferred to the attacker is 800 tokens.
   - However, the attacker was legitimately entitled to 800 tokens from their SPV share balance.
   - The **actual net economic loss** is strictly the performance fee (`amountCarry`) that was evaded ($680 USDC = 68 tokens in test harness; $9,000 in syndicate example).

3. **Total Impact Ceiling:**
   - The maximum financial impact across an SPV is bounded by:
     $$\text{Max Protocol Loss} = \sum_{i \in \text{Claimers}} \text{MaxEvadableCarry}_i \le \text{Total Unlocked Tokens} \times \text{totalCarryBPS}$$
   - On a \$10,000,000 SPV with 20% carry, the theoretical aggregate carry at risk is up to **\$2,000,000 USD**.

---

## 4. Summary Table of Economic Impacts

| Impact Vector | Description | Affected Party | Permanence | Recoverability | Verified in PoC |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Carry Fee Evasion** | Claimant replays stale low-valuation voucher to avoid high-water mark performance fee | Deal Lead / SPV Sponsor | Permanent | Non-recoverable on-chain | **YES** (`test_PropertyC`) |
| **Carry Pool Draining** | Bot replays partial carry withdrawal voucher until carry pool is emptied | Deal Lead | Immediate | Non-recoverable without off-chain recovery | **YES** (`test_withdrawCarry`) |
| **Accounting Desync** | `amountClaimedUSDC` under-records real value distributed, distorting future fee hurdles | Echo SPV State | Permanent | Corrupts all downstream tranches | **YES** (`test_PropertyB/C`) |
| **Principal Capital Drain** | Theft of other users' deposited tokens | Other Investors | Prevented | N/A (Guarded by `_claimable`) | **NO (Guarded)** |
