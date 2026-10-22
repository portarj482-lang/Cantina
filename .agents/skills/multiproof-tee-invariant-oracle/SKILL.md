---
name: multiproof-tee-invariant-oracle
description: >-
  Oracle G6 — Multiproof TEE Invariant Oracle. Governs and orchestrates invariant
  verification for Trusted Execution Environment (TEE) and ZK Multi-Proof Systems
  (INV-MULTIPROOF-03: TEE Prover Signer Authenticity and Attestation Gating).
  Adapts dynamically to active target architecture via TargetContext.
  Supervises tee-register-agent, tee-validity-agent, attestation-timestamp-agent,
  inverse-hint-integrity-agent, and signer-lifecycle-agent.
---

# Oracle G6 — Multiproof TEE Invariant Oracle

## 1. Role & Governance Overview
The Multiproof TEE Invariant Oracle governs attestation verification, enclave measurement binding, and cryptographic signer authorization across multi-proof systems (AWS Nitro enclaves, Intel SGX, or ZK coprocessors). It ensures that only provably authentic enclaves executing canonical container images can submit dispute game claims or state assertions.

---

## 2. Invariant Law (INV-MULTIPROOF-03: Signer Authenticity & Attestation Gating)

### Universal Mathematical Formulation
$$\forall s \in \text{Signers}, \text{authorized}(s, \text{image}) \implies \left( \text{attestationValid}(s) \land \text{measurement}(s) = \text{image} \land \text{fresh}(s, t) \land \neg \text{nullified}(s) \land \neg \text{deregistered}(s) \right)$$

### Universal Invariant Rules
1. **Cryptographic Attestation Verification**: Enclave attestation document (COSE Sign1, X.509 chain, or ZK proof) must be verified against root trust anchors.
2. **Measurement Binding**: Enclave PCR measurements (e.g. PCR0 image hash) must match the registered canonical image.
3. **Freshness Window**: Timestamp $t_{\text{doc}}$ must fall within valid bounds $[t - \Delta_{\text{max\_age}}, t + \Delta_{\text{max\_skew}}]$ derived from target protocol specifications.
4. **Signer Key Binding**: Public key embedded in attestation document must match the claimed signer address.
5. **Fail-Closed Nullification**: Revoked or nullified attestations immediately invalidate signer authorization.

---

## 3. Architecture Specialization Profiles

### A. AWS Nitro Enclaves / P-384 Precompile Architecture (e.g. Base TEE Prover)
- **Registry Contract**: `TEEProverRegistry.sol`
- **Validator Contract**: `INitroValidator.sol`, `P384Verifier.sol`
- **Cryptographic Algorithms**: ES384 (-35), NIST P-384 ECDSA, SHA-384.

### B. Intel SGX / DCAP Attestation Architecture
- **ECDSA Quote Verification**: P-256 ECDSA quotes against Intel PCK certificates.

### C. ZK Coprocessor / Multi-Proof Architectures (e.g. SP1, RISC Zero)
- **Groth16 / STARK Verifiers**: Image ID binding to ELF binaries.

---

## 4. Target Implementation Binding
Dynamic path discovery via `TargetContext`:
- Registry and validator contracts discovered in `context.source_roots`
- Rust offchain verifiers or hint engines discovered in `context.source_roots` (e.g. `crates/proof/tee/`)
- Upstream test suites discovered in `context.test_roots`

| Artifact Role | Discovery / Path Binding | Access |
|---|---|---|
| Prover Registry | Discovered in `context.source_roots` (e.g. `*TEE*.sol`, `*Prover*.sol`) | Read-Only |
| Attestation Validator | Discovered in `context.source_roots` (e.g. `*Validator*.sol`, `*Verifier*.sol`) | Read-Only |
| Invariant Record | `context.target_root / hypotheses/H-MULTIPROOF-03.md` | Read-Write |
| Audit Journal | `context.target_root / journal.md` | Append |

---

## 5. Result Taxonomy & Evidence Standards
- `PASS`: Cryptographic signature, certificate chain, PCR0 measurement, freshness window, and lifecycle revocation verified with negative control tests.
- `FAIL`: Tampered signature accepted, stale attestation verified, or deregistered signer permitted to sign.
- `BLOCKED`: Target registry or validator missing.
- `NOT_APPLICABLE`: Target does not use TEE or attestation-gated provers.
- `NOT_VERIFIED`: Signature verified but certificate revocation list check incomplete.
