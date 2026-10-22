# Tier 0 Fault Dispute & Multiproof Invariant Playbook

**Playbook Version:** `2.0.0`  
**Slug:** `tier0-fault-dispute-playbook`  
**Domain:** Tier 0 Settlement Layer (dynamic resolution via `TargetContext`, e.g. EVM/Foundry contracts & Rust crates)  
**Target Contracts:** Dynamically discovered via `architecture-adapter` (`OptimismPortal2.sol`, `DelayedWETH.sol`, `DisputeGameFactory.sol`, `AnchorStateRegistry.sol`, `TEEProverRegistry.sol`)  
**Max Payout:** $5,000,000 (Tier 0 Critical)

---

## 1. Architecture Overview

This playbook operationalizes the Multi-Agent Invariant Architecture engineered for Base Tier 0 contracts. It coordinates 3 Invariant Orchestration Oracles (G4, G5, G6), 6 Target Sub-Oracles, and 7 Sub-Surface Attestation/Invariant Agents under the independent audit supervision of `verification-agent` (#9).

```mermaid
flowchart TD
    O1["G1 — Global Admin Oracle"] --> G4["G4 — Dispute Invariant Oracle<br/>(INV-DISPUTE-01)"]
    O1 --> G5["G5 — DelayedWETH Invariant Oracle<br/>(INV-DELAYED-WETH-02)"]
    O1 --> G6["G6 — Multiproof TEE Oracle<br/>(INV-MULTIPROOF-03)"]

    subgraph Dispute_Cluster ["Fault Dispute Cluster"]
        G4 --> SO1["Target Sub-Oracle #1: dispute-prove-agent"]
        G4 --> SO2["Target Sub-Oracle #2: dispute-finalize-agent"]
        G4 --> SA1["Sub-Surface: game-resolution-agent"]
        G4 --> SA2["Sub-Surface: blacklist-maturity-agent"]
    end

    subgraph WETH_Cluster ["DelayedWETH Cluster"]
        G5 --> SO3["Target Sub-Oracle #1: weth-unlock-agent"]
        G5 --> SO4["Target Sub-Oracle #2: weth-withdraw-agent"]
        G5 --> SA3["Sub-Surface: weth-solvency-agent"]
        G5 --> SA4["Sub-Surface: delay-bypass-agent"]
    end

    subgraph TEE_Cluster ["Multiproof TEE Cluster"]
        G6 --> SO5["Target Sub-Oracle #1: tee-register-agent"]
        G6 --> SO6["Target Sub-Oracle #2: tee-validity-agent"]
        G6 --> SA5["Sub-Surface: attestation-timestamp-agent"]
        G6 --> SA6["Sub-Surface: inverse-hint-integrity-agent"]
        G6 --> SA7["Sub-Surface: signer-lifecycle-agent"]
    end

    V9["#9: verification-agent<br/>(Independent Audit Gate)"] -.->|Audit Check| G4
    V9 -.->|Audit Check| G5
    V9 -.->|Audit Check| G6
```

---

## 2. Invariant Specifications

### A. Invariant INV-DISPUTE-01: Withdrawal Finalization Monotonicity
Governed by **Oracle G4 — Dispute Invariant Oracle**

$$\forall w \in \text{Withdrawals}, \text{finalized}(w) \implies \left( \text{status}(G_w) = \text{DEFENDER\_WINS} \land \text{claim}(G_w) = \text{root}_{\text{anchor}}(L2_{\text{block}}) \land t \ge t_{\text{proven}} + \Delta_{\text{maturity}} \right)$$

- **Core Condition**: A withdrawal cannot be finalized unless its dispute game $G_w$ resolved as `DEFENDER_WINS`, the game's root claim equals the finalized root recorded in `AnchorStateRegistry`, and `proofMaturityDelaySeconds` has elapsed.
- **Target Sub-Oracles**:
  - `dispute-prove-agent`: Storage trie inclusion proofs and dispute game proxy bindings.
  - `dispute-finalize-agent`: Reentrancy locks, finalization status, value transfer.
- **Sub-Surface Agents**:
  - `game-resolution-agent`: Checks `DEFENDER_WINS` and anchor root matching.
  - `blacklist-maturity-agent`: Enforces game blacklist and proof maturity delays.

### B. Invariant INV-DELAYED-WETH-02: DelayedWETH Sub-Account Solvency
Governed by **Oracle G5 — DelayedWETH Invariant Oracle**

$$\text{balanceOf}(\text{address}(DelayedWETH)) \ge \sum_{a \in \text{Accounts}} \text{subAccounts}[a] + \sum_{u \in \text{Unlocks}} \text{pendingAmount}(u)$$

- **Core Condition**: Total contract WETH reserves must strictly cover all sub-account bonded balances plus pending unlock requests. Withdrawals must strictly enforce the `delay()` parameter.
- **Target Sub-Oracles**:
  - `weth-unlock-agent`: Evaluates `unlock` scheduling and timestamp assignment.
  - `weth-withdraw-agent`: Evaluates `withdraw` execution and state zeroing.
- **Sub-Surface Agents**:
  - `weth-solvency-agent`: Probes conservation of WETH across concurrent sub-account operations.
  - `delay-bypass-agent`: Probes timelock integrity, front-running, and duplicate unlock handling.

### C. Invariant INV-MULTIPROOF-03: TEE Prover Signer Authenticity
Governed by **Oracle G6 — Multiproof TEE Invariant Oracle**

$$\forall s \in \text{Signers}, \text{isValidSigner}(s) \implies \left( \exists \text{doc} \in \text{Attestations} : \text{pubKey}(\text{doc}) = s \land \text{pcr0}(\text{doc}) = \text{TEE\_IMAGE\_HASH} \land \text{verifyCertChain}(\text{doc.certs}) \right)$$

- **Core Condition**: Only addresses whose public keys were signed by a valid AWS Nitro Enclave key with an unexpired certificate chain matching the expected `TEE_IMAGE_HASH` can be registered as valid signers.
- **Target Sub-Oracles**:
  - `tee-register-agent`: Evaluates `registerSigner` calldata, hints, and signatures.
  - `tee-validity-agent`: Evaluates `isValidSigner` and `isRegisteredSigner` queries.
- **Sub-Surface Agents**:
  - `attestation-timestamp-agent`: Probes `AttestationFromFuture` and `AttestationTooOld` limits.
  - `inverse-hint-integrity-agent`: Probes P-384 modular inverse hint transcripts and affine schedules.
  - `signer-lifecycle-agent`: Evaluates image rotation, deregistration, and health latching.

---

## 3. Operational Workflows & Commands

All operations are executed through the **Universal Adaptive Engineering Framework (USAP)** and mapped to the **8-Stage Glassbox Mirror Plane Orchestration** lifecycle. Direct path navigation (`cd`) and unisolated tool invocations are prohibited.

### 8-Stage Glassbox Mirror Plane Lifecycle Mapping

1. **Stage 1: Perception Filtering**
   - Resolve `TargetContext` dynamically via `TargetContextResolver` (respecting explicit context, environment, and `MEMORY.md`).
   - Validate target root containment, architecture identification (`evm`, `solana`, etc.), and scope manifest SHA-256 digest integrity (`scope.md`).
2. **Stage 2: Parsing & Tokenization**
   - Parse project manifests (`foundry.toml`, `Cargo.toml`), contract ASTs, and ABI signatures via `architecture-adapter`.
3. **Stage 3: Preceptive Feature Interpretation**
   - Bind target contracts to canonical invariant specifications:
     - Dispute & withdrawal finalization monotonicity (`INV-DISPUTE-01`).
     - Delayed withdrawal vault & sub-account solvency (`INV-DELAYED-WETH-02`).
     - TEE attestation & prover signer authenticity (`INV-MULTIPROOF-03`).
4. **Stage 4: Thinking & Planning**
   - Build task ledger dependency graphs with strict execution bounds, rollback recipes, and acceptance criteria.
5. **Stage 5: Reasoning & Verification**
   - Execute non-destructive verification passes in local isolated sandboxes.
   - If `TargetContext` indicates the target does not implement the supervised contracts or runtime, emit `NOT_APPLICABLE` and short-circuit cleanly without false claims.
6. **Stage 6: Context & Scope Modeling**
   - Enforce subdirectory path containment, boundary checks, and scope lock verification.
7. **Stage 7: Awareness & Semantic Interpretation (Adversarial Negative Controls)**
   - Run independent challenger falsification suites. Falsification tests MUST fail against canonical invariants (proving invariant robustness) or expose true violations.
   - If negative control falsification fails or divergence is detected, the run state transitions strictly to `FAILED`.
8. **Stage 8: Meta-Governance & Executive Authorization**
   - Independent verification gate check by `verification-agent` (#9).
   - Require human approval before any stage promotion.
   - Emit an honest, transparent completion report: accurately declare `COMPLETED_WITH_LIMITATIONS` whenever contract tests are checklists, fixtures, or unexecuted.

### Canonical USAP CLI Invocations

All domain operations adapt dynamically to the active target environment:

```bash
# 1. Fault Dispute Finalization Invariant Verification (INV-DISPUTE-01)
python3 -m universal_adaptive_engine.cli operation --name dispute

# 2. DelayedWETH Solvency Invariant Verification (INV-DELAYED-WETH-02)
python3 -m universal_adaptive_engine.cli operation --name delayed-weth

# 3. TEE Prover Registry Attestation Invariant Verification (INV-MULTIPROOF-03)
python3 -m universal_adaptive_engine.cli operation --name multiproof-tee

# 4. Vertical Slice Execution with Independent Challenger Gate
python3 -m universal_adaptive_engine.cli vertical-slice --target bounties/base/contracts/src/L1/OptimismPortal2.sol --slice dispute-finalization
```

---

## 4. Verification & Audit Protocol

1. **Independent Verification & Gate Enforcement**: No finding or hypothesis state transition (`ACTIVE` → `PROVEN` or `HOLD`) is approved without independent replication by `verification-agent` (#9).
2. **Negative Control Requirement**: Invariant verification is incomplete without adversarial negative controls. If challenger falsification fails to execute or asserts invalid state, the run outcome is marked `FAILED`.
3. **Honest Result Taxonomy**: Operations must report outcomes strictly under the 5-state taxonomy (`PASS`, `FAIL`, `BLOCKED`, `NOT_APPLICABLE`, `NOT_VERIFIED`). Never emit a checklist stub as evidence of deployed contract compliance.
4. **Provenance & Attestation**: Every claim must cite specific source references (`[SRC: path#Lxx]`), execution tools (`[TOOL: forge/cargo]`), and reproducible proof files (`[POC: path]`) verified against computed SHA-256 digests.
5. **Safety Compliance**: All tests run strictly within the local container or sandbox with zero live-fund or external network interactions.
