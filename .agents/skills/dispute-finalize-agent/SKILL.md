---
name: dispute-finalize-agent
description: >-
  Target Sub-Oracle #2 for Dispute Systems. Specializes in verifying the correctness
  and security of withdrawal finalization (e.g. finalizeWithdrawalTransaction).
  Adapts dynamically to the active target architecture via TargetContext. Supervised
  by Dispute Invariant Oracle (G4).
---

# Target Sub-Oracle — dispute-finalize-agent

## 1. Role Overview
The `dispute-finalize-agent` evaluates the finalization and token transfer execution of withdrawal transactions. It verifies reentrancy locks, CEI (Checks-Effects-Interactions) ordering, finalization status flags, call target execution, and external value transfer safety.

---

## 2. Invariant Specifications (INV-DISPUTE-FINALIZE)
1. **Checks-Effects-Interactions (CEI)**: Finalization flag $\text{finalized}[H(w)] = \text{true}$ must be updated BEFORE external message or value execution.
2. **Reentrancy Protection**: Withdrawal finalization must be guarded by a non-reentrant mutex.
3. **External Call Boundaries**: Value transfers and execution targets must match the proven withdrawal parameters exactly without mutation.
4. **Permanent Immutability**: Subsequent finalization attempts on already-finalized withdrawals must revert.

---

## 3. Architecture Specializations
- **EVM**: `OptimismPortal2.finalizeWithdrawalTransaction`, `Address.alias`, `SafeCall.send`.
- **Solana**: Cross-Program Invocation (CPI) to token programs with signer seeds.
- **Move**: Resource extraction and transfer with linear capability consumption.

---

## 4. Target Implementation Binding
Dynamic path discovery via `TargetContext`:
- Portal contract discovered in `context.source_roots`
- Finalization tests discovered in `context.test_roots`
- Verification journal logged in `context.target_root / journal.md`

---

## 5. Result Taxonomy
- `PASS`: CEI ordering, reentrancy guards, and single-execution monotonicity verified with negative control replay tests.
- `FAIL`: Reentrancy possible or replay finalization accepted.
- `BLOCKED`: Missing portal implementation or test harness.
- `NOT_APPLICABLE`: Target does not perform onchain finalization transfers.
- `NOT_VERIFIED`: Transfer verified statically but symbolic execution inconclusive.
