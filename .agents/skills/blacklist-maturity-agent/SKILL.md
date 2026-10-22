---
name: blacklist-maturity-agent
description: >-
  Sub-Surface Invariant Agent #7. Evaluates dispute game blacklisting, proof maturity
  delay parameters, and time manipulation bounds in withdrawal portals. Derives maturity
  rules and emergency authority models from target protocol specifications via TargetContext.
  Supervised by Dispute Invariant Oracle (G4).
---

# Sub-Surface Invariant Agent — blacklist-maturity-agent

## 1. Role Overview
The `blacklist-maturity-agent` analyzes dispute game blacklisting and proof maturity delay enforcement. It verifies that withdrawals cannot be finalized before the protocol's challenge and maturity windows have elapsed, and that blacklisted dispute games are immediately and permanently barred from finalizing transactions.

---

## 2. Invariant Specifications (INV-BLACKLIST-MATURITY)

### Parameter Derivation
Extract target-specific governance parameters from the active contract:
- $\Delta_{\text{maturity}}$: Proof maturity delay in seconds (e.g. `proofMaturityDelaySeconds()`).
- $\Delta_{\text{game}}$: Game challenge window duration.
- $\text{GuardianRole}$: Authority address with blacklisting permission.

### Formal Verification Invariants
1. **Maturity Delay Enforcement**:
   $$\forall w, \text{finalize}(w, t) \implies t \ge t_{\text{proven}}(w) + \Delta_{\text{maturity}}$$
   Finalization attempts prior to this threshold must revert (e.g. `OptimismPortal2: withdrawal proof not mature`).
2. **Blacklist Integrity**:
   $$\forall G, \text{isBlacklisted}(G) \implies \neg \text{canFinalize}(G)$$
   If emergency guardian blacklists game $G$, all withdrawals proved against $G$ must be blocked.
3. **Emergency Guardian Access Control**:
   Only authorized multisig or guardian address may invoke `blacklistDisputeGame(address)`. Unauthorized callers must revert.
4. **Respected Game Type Timelocks**:
   Changes to respected game types or maturity delay parameters must follow timelock procedures without retroactive finalization bypass.

---

## 3. Directory / Artifact Ownership & Access
Context resolved via `TargetContext`:
- Portal and factory contracts discovered in `context.source_roots`
- Upstream maturity tests discovered in `context.test_roots`

| Artifact | Access | Purpose |
|---|---|---|
| Dispute Portal | Read-Only | Inspect maturity delay and blacklist mappings |
| Factory Contract | Read-Only | Verify game tracking and blacklist propagation |
| Blacklist Journal | Append | Document emergency authority audit findings |

---

## 4. Verification Procedures & Negative Controls
1. **Derive Target Parameters**: Read `proofMaturityDelaySeconds` and `disputeGameBlacklist` mappings.
2. **Execute Premature Finalization Attack**:
   - Set $t = t_{\text{proven}} + \Delta_{\text{maturity}} - 1$ (Expect FAIL/Revert).
   - Set $t = t_{\text{proven}} + \Delta_{\text{maturity}}$ (Expect PASS if game resolved).
3. **Execute Blacklisted Game Attack**:
   - Flag dispute game as blacklisted in mock or test state.
   - Attempt finalization (Expect FAIL/Revert with `BadTarget` or `BlacklistedGame`).
4. **Execute Unauthorized Blacklist Call**:
   - Invoke blacklisting from non-guardian address (Expect FAIL/Revert).

---

## 5. Result Taxonomy
- `PASS`: Maturity delays and blacklisting access controls verified with passing negative controls.
- `FAIL`: Premature finalization allowed or blacklisted game bypasses check.
- `BLOCKED`: Portal or factory contracts missing.
- `NOT_APPLICABLE`: Target does not use dispute games or maturity delays.
- `NOT_VERIFIED`: Analysis incomplete.
