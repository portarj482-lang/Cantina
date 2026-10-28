# Forensic Test Evidence Catalog: Coinbase Echo Distributor (F-003)

**Agent ID:** `MQ-RAE-001`  
**Investigation ID:** `F-003`  
**Execution Receipt:** `EXEC-FOUNDRY-ECHO-20261028-001`  
**Reproduction Receipt:** `REPRO-RUN-01-20261028`  
**Source Commit:** `main`  

---

## Catalog Index of Evaluated Security Tests

### Test 1: `test_PropertyA_SignatureUniqueness_Falsified`
- **Purpose:** Falsify the EIP-712 single-use signature invariant in `Distributor.claimTokens`.
- **Security Property:** `INV-SIG-01` (Signature Single-Use Uniqueness).
- **Test File & Hash:** `EchoDistributorReplayPoC.t.sol` (SHA-256: `ab6b7d319f4a0a67f8d987dc846762fcd3b84b0c71feb27e4c2c8b96a7f4fce5`).
- **Preconditions & Initial State:** SPV with 1,000 shares; claimant Alice has 800 shares; valid voucher for 400 tokens signed by Alice and platform.
- **Suite & Execution ID:** `ECHO-DISTRIBUTOR-FULL-VERIFICATION-V1` / `EXEC-FOUNDRY-ECHO-20261028-001`.
- **Expected Behavior:** Second submission with identical calldata must revert (`SignatureAlreadyConsumed`).
- **Observed Behavior:** Second call executes successfully; gas used: 408,817. Total claimed reaches 800 tokens.
- **Raw Evidence Ref:** `raw-test-output.log:8-16`.
- **State & Balance Deltas:** `state.amountClaimed` increases from 0 -> 400 -> 800. Alice token balance increases by 800.
- **Reproduction Result:** Identical behavior in `REPRO-RUN-01-20261028`.
- **Limitations:** Only functions while `block.timestamp < expiresAt`.
- **Conclusion:** Confirms missing signature digest consumption. Confidence: **100%**.
- **Reviewer Status:** **ACCEPTED**.

---

### Test 2: `test_PropertyC_CarryAccounting_ReplayEvasionExploit`
- **Purpose:** Demonstrate performance fee (carry) evasion via replay of stale valuation vouchers.
- **Security Property:** `INV-CARRY-01` (Performance Fee Hurdle Consistency).
- **Test File & Hash:** `EchoDistributorReplayPoC.t.sol` (SHA-256: `ab6b7d31...`).
- **Preconditions & Initial State:** Investor Alice invested \$1,000 USDC; 20% carry; Tranche 1 issued at \$1.00; Tranche 2 market price is \$10.00.
- **Suite & Execution ID:** `ECHO-DISTRIBUTOR-FULL-VERIFICATION-V1` / `EXEC-FOUNDRY-ECHO-20261028-001`.
- **Expected Behavior:** Honest claim at \$10.00 generates 68 tokens carry for deal lead; Alice receives 332 tokens.
- **Observed Behavior:** Replaying Tranche 1 voucher evaluates valuation at \$1.00, reducing carry to 0 tokens; Alice receives 400 tokens.
- **Raw Evidence Ref:** `raw-test-output.log:24-32`.
- **State & Balance Deltas:** Deal lead carry balance delta = 0 tokens (expected +68 tokens); Alice balance delta = +400 tokens.
- **Reproduction Result:** Identical behavior in `REPRO-RUN-01-20261028`.
- **Limitations:** Requires price appreciation before expiration.
- **Conclusion:** Proves 100% carry evasion and direct permanent financial loss to deal lead. Confidence: **100%**.
- **Reviewer Status:** **ACCEPTED**.

---

### Test 3: `test_withdrawCarry_SignatureReplayExploit`
- **Purpose:** Demonstrate involuntary carry pool liquidation via public `withdrawCarry` replay.
- **Security Property:** `INV-WITHDRAW-01` (Carry Withdrawal Authorization Monotonicity).
- **Test File & Hash:** `EchoDistributorReplayPoC.t.sol` (SHA-256: `ab6b7d31...`).
- **Preconditions & Initial State:** Deal lead accrued 200 tokens carry; signs voucher for 50 tokens.
- **Suite & Execution ID:** `ECHO-DISTRIBUTOR-FULL-VERIFICATION-V1` / `EXEC-FOUNDRY-ECHO-20261028-001`.
- **Expected Behavior:** Only 50 tokens can be extracted per voucher.
- **Observed Behavior:** Calldata replayed 3x, extracting 150 tokens from carry pool; gas used: 844,714.
- **Raw Evidence Ref:** `raw-test-output.log:40-48`.
- **State & Balance Deltas:** Deal lead pool decreases from 200 -> 50 tokens; receiver balance increases by 150 tokens.
- **Reproduction Result:** Identical behavior in `REPRO-RUN-01-20261028`.
- **Limitations:** Extracted tokens go to deal lead receiver address, causing tax/cash-flow griefing.
- **Conclusion:** Confirms unauthenticated replay drains accrued carry pool. Confidence: **100%**.
- **Reviewer Status:** **ACCEPTED**.

---

### Test 4: `test_Regression_PatchedGate_BlocksClaimReplay`
- **Purpose:** Verify defensive patch invalidates claim replay.
- **Security Property:** `INV-SIG-01` under patched implementation.
- **Test File & Hash:** `EchoDistributorRegression.t.sol` (SHA-256: `21105b13...`).
- **Preconditions & Initial State:** Deployed contract with `_consumedDigests` mapping at Slot 13.
- **Suite & Execution ID:** `ECHO-DISTRIBUTOR-FULL-VERIFICATION-V1` / `EXEC-FOUNDRY-ECHO-20261028-001`.
- **Expected Behavior:** Second submission reverts `SignatureAlreadyConsumed`.
- **Observed Behavior:** Reverts with `SignatureAlreadyConsumed(digest)` as expected; gas used: 429,464.
- **Raw Evidence Ref:** `raw-test-output.log:58-64`.
- **State & Balance Deltas:** Second call produces 0 balance change; state reverts atomically.
- **Reproduction Result:** Identical behavior in `REPRO-RUN-01-20261028`.
- **Limitations:** Requires contract upgrade.
- **Conclusion:** Confirms remediation effectiveness. Confidence: **100%**.
- **Reviewer Status:** **ACCEPTED**.
