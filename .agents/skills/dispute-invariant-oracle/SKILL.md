---
name: dispute-invariant-oracle
description: >-
  Oracle G4 — Dispute Invariant Oracle. Governs and orchestrates invariant
  verification for Dispute and Withdrawal Finalization Monotonicity (INV-DISPUTE-01).
  Adapts dynamically to the active target architecture and bounty scope via TargetContext.
  Supervises dispute-prove-agent, dispute-finalize-agent, game-resolution-agent,
  and blacklist-maturity-agent, consulting verification-agent (#9) as independent gate.
---

# Oracle G4 — Dispute Invariant Oracle

## 1. Role & Governance Overview
The Dispute Invariant Oracle governs withdrawal finalization monotonicity and dispute settlement invariants. It enforces that L2-to-L1 or cross-domain withdrawal transactions cannot be finalized out of order, under unfinalized roots, against challenged/invalid dispute games, or before proof maturity delays expire.

---

## 2. Invariant Law (INV-DISPUTE-01: Withdrawal Finalization Monotonicity)

### Universal Mathematical Formulation
$$\forall w \in \text{Withdrawals}, \text{finalized}(w) \implies \left( \text{status}(G_w) = \text{VALID\_RESOLVED} \land \text{claim}(G_w) = \text{root}_{\text{canonical}}(L2_{\text{block}}) \land t \ge t_{\text{proven}} + \Delta_{\text{maturity}} \land \neg \text{blacklisted}(G_w) \right)$$

### Universal Preconditions & Invariant Rules
1. **Resolution Authenticity**: The associated dispute or settlement game $G_w$ must be permanently resolved in favor of the valid state claim (e.g., `DEFENDER_WINS` in fault dispute games).
2. **Canonical Root Binding**: The root claim committed by $G_w$ must match the canonical verified output root in the anchor state registry.
3. **Maturity Delay Enforcement**: Current timestamp $t$ must exceed the proof submission timestamp by at least the required maturity delay ($\Delta_{\text{maturity}}$).
4. **Non-Blacklisted**: The dispute game instance must not be blacklisted by emergency guardians.
5. **Replay Monotonicity**: Once finalized, $\text{finalized}(w)$ is permanently immutable; re-finalization attempts must revert.

---

## 3. Architecture Specialization Profiles

### A. EVM / Optimism Fault Dispute Games (e.g. Base, Optimism, OP Stack)
- **Portal Contract**: `OptimismPortal2.sol` (`finalizeWithdrawalTransaction`, `provenWithdrawals`)
- **Factory Contract**: `DisputeGameFactory.sol` (`games`, `gameAtIndex`)
- **Anchor Registry**: `AnchorStateRegistry.sol` (`getAnchorRoot`)
- **Verification Tooling**: Foundry `forge test`, invariant fuzzing.

### B. EVM / AggLayer & Polygon Pessimistic Proofs
- **Settlement Contract**: `RollupManager.sol`, `PessimisticConsensus.sol`
- **Root Tracking**: Local exit root vs Global exit root synchronization.

### C. Solana / Cross-Chain Settlement
- **Program ID & PDAs**: Withdrawal receipt state accounts, settlement verification programs.
- **Verification Tooling**: Anchor test runner, account constraint validation.

---

## 4. Target Implementation Binding & Dynamic Context
Context is dynamically injected via `TargetContext`:
- **Target Root**: `context.target_root`
- **Scope Manifest**: `context.scope_manifest` (`scope.md`)
- **Contract Sources**: Discovered dynamically in `context.source_roots`
- **Journal**: Appended to target's `journal.md` or session-isolated artifact directory.

| Artifact Role | Discovery / Path Binding | Access |
|---|---|---|
| Dispute Portal | Discovered in `context.source_roots` (e.g. `*Portal*.sol`) | Read-Only |
| Dispute Factory | Discovered in `context.source_roots` (e.g. `*Factory*.sol`) | Read-Only |
| State Registry | Discovered in `context.source_roots` (e.g. `*Registry*.sol`) | Read-Only |
| Invariant Record | `context.target_root / hypotheses/H-DISPUTE-01.md` | Read-Write |
| Audit Journal | `context.target_root / journal.md` | Append |

---

## 5. Result Taxonomy & Evidence Standards
- `PASS`: All 5 invariant conditions verified with reproducible test traces and unbreached negative controls.
- `FAIL`: Counterexample generated (e.g. early finalization accepted, blacklisted game finalized).
- `BLOCKED`: Target contract, manifest, or scope missing (`MISSING_CONTEXT`).
- `NOT_APPLICABLE`: Target architecture does not employ dispute games or asynchronous settlement.
- `NOT_VERIFIED`: Verification incomplete due to unsupported prover toolchain or insufficient fuzz depth.
