# 04 — Authenticated Test Results: Coinbase Echo Distributor (F-003)

**Document ID:** `04-AUTHENTICATED-TEST-RESULTS`  
**Execution Receipt ID:** `EXEC-FOUNDRY-ECHO-20261028-001`  
**Runner:** Foundry 1.8.5  
**Raw Log Reference:** `raw-test-output.log` (`6a8814083549d541...`)  

---

## 1. Suite 1: `EchoDistributorReplayPoC.t.sol` (7 Tests)

| Test Case | Invariant | Result | Gas Used | Telemetry / Observation |
| :--- | :--- | :---: | :---: | :--- |
| `test_PropertyA_SignatureUniqueness_Falsified` | `INV-SIG-01` | **PASS** | 408,817 | Replayed voucher accepted twice |
| `test_PropertyB_AllocationCapEnforced_SignatureCapViolated` | Boundary | **PASS** | 491,436 | Exceeds single voucher limit up to share cap |
| `test_PropertyC_CarryAccounting_HonestBaseline` | Baseline | **PASS** | 504,279 | \$10 market claim yields 68 tokens carry |
| `test_PropertyC_CarryAccounting_ReplayEvasionExploit` | `INV-CARRY-01` | **PASS** | 409,707 | \$1 valuation voucher yields 0 carry (68 tokens stolen) |
| `test_PropertyD_AuthorizationBinding_Enforced` | Control | **PASS** | 260,405 | Altered receiver reverts `UnauthorizedUserSigner` |
| `test_PropertyE_StateTransitionConsistency` | `INV-ALLOC-01` | **PASS** | 407,097 | Excess claim reverts `AmountExceedsClaimable` |
| `test_withdrawCarry_SignatureReplayExploit` | `INV-WITHDRAW-01` | **PASS** | 844,714 | Replayed 3x, draining 150 tokens from carry pool |

---

## 2. Suite 2: `EchoDistributorRegression.t.sol` (3 Tests)

| Test Case | Invariant | Result | Gas Used | Observation |
| :--- | :--- | :---: | :---: | :--- |
| `test_Regression_PatchedGate_AllowsFreshVoucher` | Safety | **PASS** | 588,508 | Unconsumed voucher executes normally |
| `test_Regression_PatchedGate_BlocksCarryWithdrawalReplay` | `INV-WITHDRAW-01` | **PASS** | 662,231 | Reverts `SignatureAlreadyConsumed` |
| `test_Regression_PatchedGate_BlocksClaimReplay` | `INV-SIG-01` | **PASS** | 429,464 | Reverts `SignatureAlreadyConsumed` |
