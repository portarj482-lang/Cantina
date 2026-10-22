# G6 — Multiproof TEE Invariant Oracle

**Slug:** `multiproof-tee-invariant-oracle`  
**SKILL.md:** `.agents/skills/multiproof-tee-invariant-oracle/SKILL.md`  
**Domain:** `bounties/base/contracts/src/L1/proofs/tee/` & `bounties/base/base/crates/proof/tee/`  
**Supervised Invariant:** `INV-MULTIPROOF-03` (TEE Prover Signer Authenticity & Attestation Gating)  
**Privilege:** Read-Write on TEE prover invariant test harnesses; Read-Only on canonical protocol source.

---

## Purpose

The Multiproof TEE Invariant Oracle (G6) governs invariant verification across the AWS Nitro Enclave proving pipeline. It ensures that only signers possessing valid hardware-enforced attestation documents signed by the pinned AWS Nitro root CA with matching PCR0 hashes can register and participate in Base multi-proof dispute games.

---

## Supervised Agents

```mermaid
flowchart TD
    G6["G6 — Multiproof TEE Invariant Oracle<br/>Invariant: INV-MULTIPROOF-03"] --> SO1["Target Sub-Oracle #1<br/>tee-register-agent<br/>(registerSigner)"]
    G6 --> SO2["Target Sub-Oracle #2<br/>tee-validity-agent<br/>(isValidSigner)"]
    G6 --> SA1["Sub-Surface Agent<br/>attestation-timestamp-agent<br/>(Drift & Expiry Bounds)"]
    G6 --> SA2["Sub-Surface Agent<br/>inverse-hint-integrity-agent<br/>(P-384 Hint Verification)"]
    G6 --> SA3["Sub-Surface Agent<br/>signer-lifecycle-agent<br/>(Rotation & Health Latching)"]
    
    VER["verification-agent (#9)<br/>(Independent Audit Gate)"] -.->|Audit Check| G6
```

| Agent | Level | Domain / Role |
|---|---|---|
| `tee-register-agent` | Target Sub-Oracle #1 | Verifies `TEEProverRegistry.registerSigner` calldata, certificate chain inputs, and signature verification. |
| `tee-validity-agent` | Target Sub-Oracle #2 | Verifies `isValidSigner`, `isRegisteredSigner`, and game type PCR0 matching logic. |
| `attestation-timestamp-agent` | Sub-Surface Attestation | Probes time boundaries: `AttestationFromFuture` vs `AttestationTooOld`, certificate expiration, and clock drift. |
| `inverse-hint-integrity-agent` | Sub-Surface Attestation | Probes P-384 affine arithmetic, modular inverse hint tampering, and `P384Verifier` malleability. |
| `signer-lifecycle-agent` | Sub-Surface Attestation | Verifies prover image rotation, deregistration, and health endpoint latching semantics. |
| `verification-agent` | Audit Gate (#9) | Independently audits all attestation claims against raw COSE/CBOR test vectors. |

---

## Decision Authority

G6 has authority on:
- Formulating, testing, and verifying hypotheses targeting `TEEProverRegistry.sol`, `CertManager.sol`, and `P384Verifier.sol`.
- Coordinating with `base-proof-tee-nitro-verifier` and `base-proof-tee-registrar` Rust crates.
- Signing off on whether hardware attestation guarantees cannot be forged or replayed.
