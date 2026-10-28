# Execution Authentication Report: Coinbase Echo Distributor (F-003)

**Agent ID:** `MQ-RAE-001`  
**Execution Receipt ID:** `EXEC-FOUNDRY-ECHO-20261028-001`  
**Runner:** Foundry 1.8.5 (`/home/nova/.foundry/bin/forge`)  
**Raw Log Reference:** `raw-test-output.log` (SHA-256: `6a8814083549d54113a2ec14633d18d775d56cc30b90a107cf2dc9ba033c7470`)  
**Timestamp:** 2026-10-28T06:51:30Z  

---

## 1. Execution Receipt Verification

| Metric | Recorded Value | Verification Status |
| :--- | :--- | :--- |
| **Process Exit Codes** | `0` (Suite 1), `0` (Suite 2) | **AUTHENTICATED** |
| **Duration** | 4.44s total execution time | **AUTHENTICATED** |
| **Total Test Suites Executed** | 2 (`EchoDistributorReplayPoC.t.sol`, `EchoDistributorRegression.t.sol`) | **AUTHENTICATED** |
| **Total Tests Passed** | 10 passed, 0 failed, 0 skipped | **AUTHENTICATED** |

---

## 2. Test Assertion Telemetry & Audit

### Suite 1: `EchoDistributorReplayPoC.t.sol` (7 Tests)
1. `test_PropertyA_SignatureUniqueness_Falsified` [PASS] (408,817 gas): Replays voucher twice, proving missing digest consumption.
2. `test_PropertyB_AllocationCapEnforced_SignatureCapViolated` [PASS] (491,436 gas): Confirms claim exceeds single voucher limit while respecting allocation cap.
3. `test_PropertyC_CarryAccounting_HonestBaseline` [PASS] (504,279 gas): Confirms \$10 market claim yields 68 tokens carry.
4. `test_PropertyC_CarryAccounting_ReplayEvasionExploit` [PASS] (409,707 gas): Confirms \$1.00 valuation voucher replay generates 0 tokens carry (68 tokens stolen).
5. `test_PropertyD_AuthorizationBinding_Enforced` [PASS] (260,405 gas): Negative control verifying altered receiver reverts `UnauthorizedUserSigner`.
6. `test_PropertyE_StateTransitionConsistency` [PASS] (407,097 gas): Boundary control verifying claims beyond share allocation revert `AmountExceedsClaimable`.
7. `test_withdrawCarry_SignatureReplayExploit` [PASS] (844,714 gas): Replays 50-token partial carry withdrawal voucher 3 consecutive times, draining 150 tokens.

### Suite 2: `EchoDistributorRegression.t.sol` (3 Tests)
1. `test_Regression_PatchedGate_AllowsFreshVoucher` [PASS] (588,508 gas): Fresh voucher succeeds normally.
2. `test_Regression_PatchedGate_BlocksCarryWithdrawalReplay` [PASS] (662,231 gas): Reverted with `SignatureAlreadyConsumed`.
3. `test_Regression_PatchedGate_BlocksClaimReplay` [PASS] (429,464 gas): Reverted with `SignatureAlreadyConsumed`.

**Execution Authenticity Verdict:** **AUTHENTICATED_AND_VERIFIED**.
