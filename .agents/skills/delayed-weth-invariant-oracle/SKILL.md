---
name: delayed-weth-invariant-oracle
description: >-
  Oracle G5 — DelayedWETH Invariant Oracle. Governs and orchestrates invariant
  verification for Delayed Withdrawal Vaults, Bonded Collateral, and Sub-Account Solvency
  (INV-DELAYED-WETH-02). Adapts dynamically to target architecture via TargetContext.
  Supervises weth-unlock-agent, weth-withdraw-agent, weth-solvency-agent, and delay-bypass-agent.
---

# Oracle G5 — DelayedWETH Invariant Oracle

## 1. Role & Governance Overview
The DelayedWETH Invariant Oracle is the invariant governance authority for delayed withdrawal vaults, escrow contracts, and bonded collateral mechanisms. It governs total collateral conservation, sub-account solvency accounting, and timelock enforcement across unlock and withdrawal lifecycles.

---

## 2. Invariant Law (INV-DELAYED-WETH-02: Sub-Account Solvency & Delay Integrity)

### Universal Mathematical Formulation
1. **Collateral Solvency**:
   $$\text{VaultBalance}_{\text{token}} \ge \sum_{a \in \text{SubAccounts}} \text{balance}(a)$$
2. **Timelock Monotonicity**:
   $$\forall a \in \text{SubAccounts}, \text{withdraw}(a, t) \implies \left( t_{\text{unlock}}(a) > 0 \land t \ge t_{\text{unlock}}(a) + \Delta_{\text{delay}} \right)$$
3. **Successive Unlock Monotonicity**:
   When unlock is called successively at $t_2 > t_1$, the delay window MUST reset to $t_2 + \Delta_{\text{delay}}$ to prevent front-running delayed claims. Same-block unlocks ($t_2 = t_1$) must maintain timestamp without rewinding.
4. **Cross-Caller Isolation**:
   An unauthorized principal $p \neq a$ cannot debit or withdraw from sub-account $a$.

---

## 3. Architecture Specialization Profiles

### A. EVM / Delayed Collateral Vaults (e.g. DelayedWETH, Liquity Troves)
- **Solidity Target**: `DelayedWETH.sol`, `TroveManager.sol`
- **Accounting Model**: Internal mapping `mapping(address => mapping(address => uint256)) public subAccountBalance`
- **Timelock Mapping**: `mapping(address => mapping(address => uint256)) public unlockTimestamp`

### B. Solana / Escrow & Bonding Curves (e.g. Pump.fun, Raydium)
- **Account Model**: PDA vault token account, user bonding token account.
- **Timelock Model**: Slot or Unix timestamp clock constraints in instruction accounts.

---

## 4. Target Implementation Binding
Dynamic path discovery via `TargetContext`:
- Vault contract discovered in `context.source_roots`
- Solvency fuzz tests discovered in `context.test_roots`
- Invariant analysis logged in `context.target_root / hypotheses/H-DELAYED-WETH-02.md`

| Artifact Role | Discovery / Path Binding | Access |
|---|---|---|
| Delayed Vault | Discovered in `context.source_roots` (e.g. `*Delayed*.sol`, `*Escrow*.sol`) | Read-Only |
| Token Interface | Discovered in `context.source_roots` (e.g. `IWETH.sol`, `IERC20.sol`) | Read-Only |
| Invariant Record | `context.target_root / hypotheses/H-WETH-02.md` | Read-Write |
| Audit Journal | `context.target_root / journal.md` | Append |

---

## 5. Result Taxonomy & Evidence Standards
- `PASS`: Vault solvency, timelock monotonicity, and authorization proven with test assertions and adversarial negative controls.
- `FAIL`: Early withdrawal permitted, successive unlock rewound, or balance deficit uncovered.
- `BLOCKED`: Vault or token contract missing from target.
- `NOT_APPLICABLE`: Target does not implement timelocked or bonded collateral withdrawals.
- `NOT_VERIFIED`: Invariant partially modeled but high-concurrency reentrancy fuzzing unavailable.
