---
name: weth-unlock-agent
description: >-
  Target Sub-Oracle #1 for Delayed Withdrawal Vaults. Specializes in verifying the
  correctness and security of unlock state transitions (e.g. DelayedWETH.unlock).
  Adapts dynamically to the active target architecture via TargetContext. Supervised
  by DelayedWETH Invariant Oracle (G5).
---

# Target Sub-Oracle — weth-unlock-agent

## 1. Role Overview
The `weth-unlock-agent` specializes in verifying the security and invariant enforcement of the `unlock` function in delayed withdrawal vaults. It evaluates caller authorization, sub-account balance debits, unlock timestamp assignment, and successive unlock delay resets.

---

## 2. Invariant Specifications (INV-WETH-UNLOCK)
1. **Authorization & Allowance**: Caller must be authorized or have sufficient allowance to initiate unlock on the specified sub-account.
2. **Timestamp Monotonicity**: Initiating unlock records $t_{\text{unlock}} = \text{block.timestamp}$.
3. **Successive Delay Reset**: Calling unlock again at $t_2 > t_1$ must update $t_{\text{unlock}} = t_2$, preventing an earlier unlock from permitting immediate withdrawals of newly deposited funds.
4. **Zero-Amount Guard**: Attempting to unlock zero balance or unlocking without sufficient balance must fail closed.

---

## 3. Architecture Specializations
- **EVM**: `DelayedWETH.unlock(address,uint256)`, timestamp mapping updates, allowance checks.
- **Solana**: Initialization of escrow timelock PDA with current slot / clock sysvar.

---

## 4. Target Implementation Binding
Dynamic path discovery via `TargetContext`:
- Vault contract discovered in `context.source_roots`
- Unlock unit tests discovered in `context.test_roots`

---

## 5. Result Taxonomy
- `PASS`: Unlock authorization and timestamp reset integrity verified with passing negative controls.
- `FAIL`: Successive unlock fails to reset timelock or unauthorized account unlocked.
- `BLOCKED`: Target vault contract not found.
- `NOT_APPLICABLE`: Target does not use two-step unlock/withdraw patterns.
- `NOT_VERIFIED`: Analysis incomplete.
