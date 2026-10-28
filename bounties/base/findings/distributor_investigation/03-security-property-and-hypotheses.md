# 03 — Security Properties and Hypotheses: Coinbase Echo Distributor (F-003)

**Document ID:** `03-SECURITY-PROPERTIES-HYPOTHESES`  
**Target:** Coinbase Echo — `Distributor.sol`  
**Authoring Authority:** `MQ-RAE-001`  
**Timestamp:** 2026-10-28T06:57:50Z  

---

## 1. Formal Invariant Specifications

- **`INV-SIG-01` (Signature Consumption):** An authorized EIP-712 voucher must authorize at most one state transition. Repeated execution must revert.
- **`INV-CARRY-01` (Performance Fee Monotonicity):** Carry deducted upon token release must reflect fair valuation at the time of claim against the unrecovered capital hurdle. Replay must not evade carry.
- **`INV-WITHDRAW-01` (Withdrawal Authorization Bound):** Cumulative carry withdrawals executed must not exceed the amount authorized in the signed voucher.
- **`INV-ALLOC-01` (Principal Share Cap):** Cumulative claims must not exceed `user.distributionShares`.

---

## 2. Tested Hypotheses

- **`F003-H1`:** Unexpired claim vouchers can be reused within their expiration window. (**CONFIRMED**)
- **`F003-H2`:** Replaying earlier vouchers causes carry calculation using stale prices, evading performance fees. (**CONFIRMED**)
- **`F003-H3`:** Replaying carry withdrawal vouchers forcibly drains the deal lead carry pool. (**CONFIRMED**)
- **`F003-H4`:** Replay violates investor share caps. (**REFUTED_BOUNDED**; share caps hold).
- **`F003-H5`:** Remediation via Slot 13 digest nullifier is safe and upgrade-compatible. (**CONFIRMED**)
- **`F003-H6`:** Scope and novelty eligibility under Cantina rules. (**CONFIRMED**)
