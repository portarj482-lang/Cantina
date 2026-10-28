# Source and Target Authentication Report: Coinbase Echo Distributor (F-003)

**Agent ID:** `MQ-RAE-001`  
**Investigation ID:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Evaluation Mode:** Source-to-Bytecode Authentication  
**Timestamp:** 2026-10-28T06:55:00Z  

---

## 1. Pinned Source Code Identification

| Attribute | Verified Value | Evidence Ref |
| :--- | :--- | :--- |
| **Repository URL** | `https://github.com/portarj482-lang/Cantina.git` | `source-provenance.json` |
| **Commit SHA** | `bf53b4f70ee62bbc369607efd4bc90a6a650e5a8` | Git tree HEAD |
| **Target Contract** | `bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol` | SHA-256: `1b43b7bd18de6b9a6c9fa8e7a11659967e10a214c600bfc78c3ffc69e9f68b6f` |
| **Types Library** | `bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Types.sol` | SHA-256: `8f6f8607ab65090d10dac3db544a24abe4688b073c29329a27d5810a3b1ee42a` |
| **Unlocker Library** | `bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/UnlockerLib.sol` | SHA-256: `000c48b59b06d7c534ba3b1bf18c18dc4934259a6e3790a35f3698b2a1fa0738` |
| **Compiler Version** | Solidity `0.8.23`, `optimizer: true`, `runs: 200`, `viaIR: true` | `environment-manifest.json` |

---

## 2. On-Chain Target Deployment Authentication

- **Network:** Base Mainnet (Chain ID `8453`)
- **Primary Implementation:** `0x1798D23f29968b4fff7A60A90645B0939d04f47E`
  - Runtime Bytecode Keccak: `0x46283d0f37828a42b00fbd0ce6f0ecca94ca8ba05f4c34f95a8c00d50ca7da0f`
  - Deployment Role: Logic implementation for TransparentUpgradeableProxy
  - Basescan Verification: [0x1798D23f29968b4fff7A60A90645B0939d04f47E](https://basescan.org/address/0x1798D23f29968b4fff7A60A90645B0939d04f47E#code)
- **Secondary Implementation:** `0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF`
  - Runtime Bytecode Keccak: `0xde886f21de4e4d461f6c20d4d84efde81eff08e385044cbb5fcf7c79d5096460`
- **Proxy Factory:** `0x3002aadad07ab12e5bb8098de3542bee2ad44fed` (`DistributorFactory`)
- **Generic Registry:** `0x73612914c81a9c072333ea9ea71a9b26a5b9a707`

---

## 3. Scope Eligibility Verification

- **Program:** Coinbase / Base Bug Bounty Program on Cantina
- **Scope Authority:** `bounties/base/scope.md#L176` under `### Echo`
- **Eligibility Verdict:** **TIER 1 IN-SCOPE PRODUCT**
- **Authorized Operation:** Fork-safe isolated test reproduction without live broadcast transactions.
- **Authentication Status:** **SOURCE_AND_TARGET_AUTHENTICATED**
