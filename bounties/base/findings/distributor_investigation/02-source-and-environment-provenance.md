# 02 — Source and Environment Provenance: Coinbase Echo Distributor (F-003)

**Document ID:** `02-SOURCE-ENVIRONMENT-PROVENANCE`  
**Target:** Coinbase Echo — `Distributor.sol`  
**Authoring Authority:** `MQ-RAE-001`  
**Timestamp:** 2026-10-28T06:57:30Z  

---

## 1. Pinned Source Code Identification

- **Git Repository:** `https://github.com/portarj482-lang/Cantina.git`
- **Pinned Commit:** `main`
- **Source Paths & Hashes:**
  - `Distributor.sol`: `1b43b7bd18de6b9a6c9fa8e7a11659967e10a214c600bfc78c3ffc69e9f68b6f`
  - `Types.sol`: `8f6f8607ab65090d10dac3db544a24abe4688b073c29329a27d5810a3b1ee42a`
  - `UnlockerLib.sol`: `000c48b59b06d7c534ba3b1bf18c18dc4934259a6e3790a35f3698b2a1fa0738`

---

## 2. Verified Toolchain and Build Configuration

- **Solidity Compiler:** `solc 0.8.23`, `optimizer: true`, `runs: 200`, `viaIR: true`
- **Foundry Framework:** `forge 1.8.5` (commit `51a52c59cffd940f76eddd0b4bb1791aa4b5ac7f`, build profile `dist`)
- **Execution Environment:** Linux x86_64, Node.js `v18.19.1`
- **Target Network:** Base Mainnet (`8453`)
