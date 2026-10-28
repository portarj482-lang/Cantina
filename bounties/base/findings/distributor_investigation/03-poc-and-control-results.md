# 03 — PoC and Control Results: Coinbase Echo Distributor

**Finding Reference:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Target Contract:** `Distributor.sol` (`0x1798D23f29968b4fff7A60A90645B0939d04f47E`)  
**Harness Location:** `bounties/base/eip-7702-proxy/test/EchoDistributorReplayPoC.t.sol`  
**Regression Location:** `bounties/base/eip-7702-proxy/test/EchoDistributorRegression.t.sol`  

---

## 1. Test Harness Architecture & Methodology

The reproduction suite evaluates the deployed `Distributor` bytecode under isolated, reproducible Foundry execution using the exact deployed contract interfaces and real cryptographic signatures.

### Cryptographic Signers in Test Harness:
- **Claimant Key:** User private key (`0xA11CE`), signer address `0x976EA74026E726554dB657fA54763abd0C3a0aa9`
- **Platform Key:** Platform private key (`0xB0B`), signer address `0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65`
- **Domain Separator:** `__EIP712_init("Distributor", "1")` matching deployed mainnet instance

---

## 2. Test Execution Results Matrix

All 10 tests across both suites execute deterministically with 100% passing results:

| Test Identifier | Category | Tested Scenario / Invariant | Result | Gas Used | Telemetry / Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `test_PropertyA_SignatureUniqueness_Falsified` | **Positive Exploit** | Resubmission of identical `ClaimData` voucher | **PASS** | 408,817 | Voucher replayed; both claims succeed |
| `test_PropertyB_AllocationCapEnforced_SignatureCapViolated` | **Boundary Check** | Claims exceed voucher `amount` (800 vs 400) | **PASS** | 491,436 | Exceeds signed voucher cap while respecting share cap |
| `test_PropertyC_CarryAccounting_HonestBaseline` | **Honest Baseline** | Honest voucher at \$10.00 market price | **PASS** | 504,279 | Generates **68 tokens carry** for deal lead |
| `test_PropertyC_CarryAccounting_ReplayEvasionExploit` | **Positive Exploit** | Replay of \$1.00 voucher at \$10.00 market price | **PASS** | 409,707 | Generates **0 tokens carry**; **68 tokens carry stolen** |
| `test_PropertyD_AuthorizationBinding_Enforced` | **Negative Control** | Forged signature / altered receiver | **PASS** | 260,405 | Reverts with `UnauthorizedUserSigner` |
| `test_PropertyE_StateTransitionConsistency` | **Negative Control** | Attempt to claim beyond investor's SPV shares | **PASS** | 407,097 | Reverts with `AmountExceedsClaimable` |
| `test_withdrawCarry_SignatureReplayExploit` | **Positive Exploit** | 3x replay of 50-token carry withdrawal | **PASS** | 844,714 | Drains 150 tokens from deal lead carry pool |
| `test_Regression_PatchedGate_BlocksClaimReplay` | **Remediation Control** | Replay against patched `_consumedDigests` gate | **PASS** | 429,464 | Reverts with `SignatureAlreadyConsumed` |
| `test_Regression_PatchedGate_BlocksCarryWithdrawalReplay` | **Remediation Control** | Carry replay against patched gate | **PASS** | 662,231 | Reverts with `SignatureAlreadyConsumed` |
| `test_Regression_PatchedGate_AllowsFreshVoucher` | **Remediation Control** | Fresh quote at \$10.00 after patch | **PASS** | 588,508 | Claim succeeds; generates 68 tokens carry |

---

## 3. Raw Execution Transcript

```text
export PATH="/home/nova/.foundry/bin:$PATH"
cd /home/nova/projects/cantina/bounties/base/eip-7702-proxy
forge test --match-path "test/EchoDistributorReplayPoC.t.sol" -vvv

Ran 7 tests for test/EchoDistributorReplayPoC.t.sol:EchoDistributorReplayPoCTest
[PASS] test_PropertyA_SignatureUniqueness_Falsified() (gas: 408817)
[PASS] test_PropertyB_AllocationCapEnforced_SignatureCapViolated() (gas: 491436)
[PASS] test_PropertyC_CarryAccounting_HonestBaseline() (gas: 504279)
Logs:
  Honest pricing total carry generated: 68

[PASS] test_PropertyC_CarryAccounting_ReplayEvasionExploit() (gas: 409707)
Logs:
  Exploitative replay total carry generated: 0
  Carry defrauded from deal lead: 68

[PASS] test_PropertyD_AuthorizationBinding_Enforced() (gas: 260405)
[PASS] test_PropertyE_StateTransitionConsistency() (gas: 407097)
[PASS] test_withdrawCarry_SignatureReplayExploit() (gas: 844714)
Logs:
  Total carry generated in pool: 180
  Carry successfully drained via replays: 150

Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 2.34s (1.77s CPU time)
```

```text
forge test --match-path "test/EchoDistributorRegression.t.sol" -vvv

Ran 3 tests for test/EchoDistributorRegression.t.sol:EchoDistributorRegressionTest
[PASS] test_Regression_PatchedGate_AllowsFreshVoucher() (gas: 588508)
[PASS] test_Regression_PatchedGate_BlocksCarryWithdrawalReplay() (gas: 662231)
[PASS] test_Regression_PatchedGate_BlocksClaimReplay() (gas: 429464)

Suite result: ok. 3 passed; 0 failed; 0 skipped; finished in 2.10s (452.39ms CPU time)
```

---

## 4. Key Takeaways & Falsification Verdict
1. **Hypothesis Confirmed:** Replaying unexpired `ClaimData` vouchers is technically unimpeded by the contract logic.
2. **Impact Boundary Confirmed:** Replay cannot breach the user's allocated SPV shares (`_claimable`). It does, however, falsify the valuation accounting, destroying carried interest calculations.
3. **Negative Controls Confirmed:** Forged signatures revert; attempts to exceed allocation revert.
4. **Remediation Confirmed:** Adding `_consumedDigests` eliminates replay while fully preserving legitimate claims and updated price discovery.
