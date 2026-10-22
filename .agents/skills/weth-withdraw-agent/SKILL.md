---
name: weth-withdraw-agent
description: >-
  Target Sub-Oracle #2 for Delayed Withdrawal Vaults. Specializes in verifying the
  correctness and security of withdrawal execution (e.g. DelayedWETH.withdraw).
  Adapts dynamically to the active target architecture via TargetContext. Supervised
  by DelayedWETH Invariant Oracle (G5).
---

# Target Sub-Oracle — weth-withdraw-agent

## 1. Role Overview
The `weth-withdraw-agent` specializes in verifying the correctness and security of final withdrawal execution after the delay period has elapsed. It evaluates timelock completion, token transfer exactness, sub-account balance deltas, and reentrancy resistance.

---

## 2. Invariant Specifications (INV-WETH-WITHDRAW)
1. **Delay Timelock Expiration**:
   $$\text{block.timestamp} \ge t_{\text{unlock}} + \Delta_{\text{delay}}$$
   Withdrawal attempts before this condition must strictly revert.
2. **Balance Conservation & Exactness**:
   Withdrawn amount must be deducted from the user's unlocked balance, and the exact token amount must be transferred to the recipient.
3. **Reentrancy Protection**:
   CEI ordering and non-reentrant guards must prevent reentering the vault during external token transfers.
4. **Deficit Prevention**:
   Vault must never allow withdrawing more than the bonded or deposited collateral.

---

## 3. Architecture Specializations
- **EVM**: `DelayedWETH.withdraw(address,uint256)`, ERC20 transfer calls, CEI storage updates.
- **Solana**: CPI transfer instruction from vault PDA to recipient token account.

---

## 4. Target Implementation Binding
Dynamic path discovery via `TargetContext`:
- Vault contract discovered in `context.source_roots`
- Withdrawal tests discovered in `context.test_roots`

---

## 5. Result Taxonomy
- `PASS`: Timelock expiration check and exact token conservation verified with negative controls.
- `FAIL`: Early withdrawal succeeds or token transfer fails to debit internal balance.
- `BLOCKED`: Target vault missing.
- `NOT_APPLICABLE`: Target does not use delayed withdrawals.
- `NOT_VERIFIED`: Transfer verified without reentrancy testing.
