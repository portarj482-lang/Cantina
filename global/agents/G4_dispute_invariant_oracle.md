# G4 — Dispute Invariant Oracle

**Slug:** `dispute-invariant-oracle`  
**SKILL.md:** `.agents/skills/dispute-invariant-oracle/SKILL.md`  
**Domain:** `bounties/base/contracts/src/L1/` (`OptimismPortal2.sol`, `DisputeGameFactory.sol`, `AnchorStateRegistry.sol`)  
**Supervised Invariant:** `INV-DISPUTE-01` (Withdrawal Finalization Monotonicity)  
**Privilege:** Read-Write on dispute invariant test harnesses; Read-Only on canonical protocol source.

---

## Purpose

The Dispute Invariant Oracle (G4) is the authoritative coordinator for verifying the formal invariants of the Base Fault Dispute System. It guarantees that withdrawal transactions from L2 to L1 cannot be finalized unless the associated dispute game has resolved in favor of the canonical state root tracked by `AnchorStateRegistry`.

---

## Supervised Agents

```mermaid
flowchart TD
    G4["G4 — Dispute Invariant Oracle<br/>Invariant: INV-DISPUTE-01"] --> SO1["Target Sub-Oracle #1<br/>dispute-prove-agent<br/>(proveWithdrawalTransaction)"]
    G4 --> SO2["Target Sub-Oracle #2<br/>dispute-finalize-agent<br/>(finalizeWithdrawalTransaction)"]
    G4 --> SA1["Sub-Surface Agent<br/>game-resolution-agent<br/>(Game Resolution & Anchor)"]
    G4 --> SA2["Sub-Surface Agent<br/>blacklist-maturity-agent<br/>(Blacklist & Delay Timing)"]
    
    VER["verification-agent (#9)<br/>(Independent Audit Gate)"] -.->|Audit Check| G4
```

| Agent | Level | Domain / Role |
|---|---|---|
| `dispute-prove-agent` | Target Sub-Oracle #1 | Verifies proof submission, storage root proofs, and output root commitments. |
| `dispute-finalize-agent` | Target Sub-Oracle #2 | Verifies withdrawal finalization gating, state transition assertions, and reentrancy locks. |
| `game-resolution-agent` | Sub-Surface Attestation | Verifies game resolution status (`DEFENDER_WINS`), game type whitelist, and anchor root matching. |
| `blacklist-maturity-agent` | Sub-Surface Attestation | Enforces `proofMaturityDelaySeconds`, dispute game blacklist lookups, and time manipulation bounds. |
| `verification-agent` | Audit Gate (#9) | Independently verifies all falsification claims against raw L1 contract bytecode. |

---

## Decision Authority

G4 has authority on:
- Formulating, testing, and verifying hypotheses targeting `OptimismPortal2` and `DisputeGameFactory`.
- Directing Target Sub-Oracles to construct targeted Forge fuzz and invariant harnesses.
- Signing off on whether a dispute finalization invariant is mathematically preserved or broken.
