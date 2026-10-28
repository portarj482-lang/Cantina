# 01 — Target and Scope Manifest: Coinbase Echo Distributor

**Finding Reference:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Authoring Persona:** `META-QUALIA: CANTINA EXECUTION-BUILDING AGENT (MQ-CANTINA-DISTRIBUTOR-001)`  
**Timestamp:** 2026-10-28T02:55:00Z  
**Verification Mode:** Fail-Closed Fork Execution & Source Bytecode Matching  

---

## 1. Executive Program Identification

- **Bounty Program:** Coinbase / Base Smart Contract Bug Bounty Program (Cantina)
- **Reward Program Scope Reference:** `bounties/base/scope.md#L176` (Tier 1 In-Scope Products: Echo)
- **Total Program Reward Pool:** Up to $5,000,000 USD (across entire on-chain program)
- **Tier 1 High Maximum Reward:** Up to $50,000 USD
- **Program Terms Note:** In July 2026, Coinbase publicly clarified changes to Web2 bounty tiers while explicitly maintaining Web3 on-chain Cantina terms. Payouts are not guaranteed and are subject to Cantina triage adjudication, demonstrable economic loss, and eligible TVL.

---

## 2. In-Scope Target Deployment & Source Mapping

| Target Dimension | Authoritative Ground Truth Record | Verification Status |
| :--- | :--- | :--- |
| **Contract Name** | `Distributor.sol` | **CONFIRMED** |
| **Asset Designation** | Distributor Implementation (Coinbase Echo SPV) | **CONFIRMED** (`scope.md#L176`) |
| **Target Chain** | Base Mainnet (Chain ID `8453`) | **CONFIRMED** |
| **Primary Implementation Address** | `0x1798D23f29968b4fff7A60A90645B0939d04f47E` | **CONFIRMED** |
| **Secondary Implementation Address** | `0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF` | **CONFIRMED** |
| **Distributor Factory Address** | `0x3002aadad07ab12e5bb8098de3542bee2ad44fed` | **CONFIRMED** (`scope.md#L175`) |
| **Generic Registry Address** | `0x73612914c81a9c072333ea9ea71a9b26a5b9a707` | **CONFIRMED** (`scope.md#L177`) |
| **Runtime Bytecode Keccak** | `0x46283d0f37828a42b00fbd0ce6f0ecca94ca8ba05f4c34f95a8c00d50ca7da0f` | **CONFIRMED** |
| **Compiler & Optimizer** | Solidity `0.8.23`, `viaIR: true`, `runs: 200` | **CONFIRMED** |
| **Source File Location** | `bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol` | **CONFIRMED** |
| **Source File SHA-256** | `1b43b7bd18de6b9a6c9fa8e7a11659967e10a214c600bfc78c3ffc69e9f68b6f` | **CONFIRMED** |
| **Proxy Pattern** | `TransparentUpgradeableProxy` via `DistributorFactory` | **CONFIRMED** |

---

## 3. Scope Eligibility Verification (Gate A)

### Authoritative Entry in `bounties/base/scope.md` (Lines 172–176):
```markdown
### Echo
| Asset | Chain | Description | Contracts |
|---|---|---|---|
| DistributorFactory | Base, BNB Smart Chain, Ethereum, Optimism, ZKSync Era | Factory contract for deploying token distributor proxies. Creates customizable distribution contracts for token vesting and airdrops. | 0x3002aadad07ab12e5bb8098de3542bee2ad44fed (Base), ... |
| Distributor Implementation | Base, BNB Smart Chain, Ethereum, Optimism, ZKSync Era | Core implementation contract for token distribution logic. | 0x1798D23f29968b4fff7A60A90645B0939d04f47E (Base), 0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF (Base), ... |
```

### Gate A Verdict: **PASSED (Scope Authenticated)**
1. The contract address `0x1798D23f29968b4fff7A60A90645B0939d04f47E` is explicitly listed under Tier 1 assets on Base Mainnet.
2. The runtime bytecode matches the compiled source from `tier1_sources/echo_Distributor_Impl/`.
3. The investigation proceeds under authorized fork-only bounds without live network interaction.
