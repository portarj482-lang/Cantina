# 06 — Economic Impact Evidence: Coinbase Echo Distributor (F-003)

**Document ID:** `06-ECONOMIC-IMPACT-EVIDENCE`  
**Target:** Coinbase Echo — `Distributor.sol`  
**Authoring Authority:** `MQ-RAE-001`  

---

## 1. Verified Contract Fee Formulas

$$\text{Remaining Hurdle } R_{\text{free}} = \max(0, I_{\text{USDC}} - C_{\text{claimedUSDC}})$$

$$\text{Amount with Carry } A_{\text{carryUSDC}} = \max(0, A_{\text{claimUSDC}} - R_{\text{free}})$$

$$\text{Carry Fee } F_{\text{USDC}} = \left\lfloor \frac{A_{\text{carryUSDC}} \times \text{totalCarryBPS}}{10000} \right\rfloor$$

$$\text{Carry Tokens } F_{\text{token}} = \text{PriceLib.convertUSDCToToken}(F_{\text{USDC}})$$

---

## 2. Quantified Economic Divergence

- **Honest Settlement ($10 Market Price):** Carry Fee = 68 tokens (\$680 USDC).
- **Replayed Settlement ($1 Stale Price):** Carry Fee = 0 tokens (\$0 USDC).
- **Direct Financial Delta:** **68 tokens (\$680 USDC, 100% carry evasion)**.
- **Affected Parties:** Deal Leads and Echo Platform lose 100% of earned carried interest.
- **Solvency Boundary:** Innocent investor principal is guarded by `_claimable()`.
