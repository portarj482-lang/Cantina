# 08 — Cantina Submission Package: Coinbase Echo Distributor Signature Replay

**Submission ID:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Bounty Program:** Coinbase / Base Bug Bounty Program (Cantina)  
**Program Scope Classification:** Tier 1 In-Scope Product (`bounties/base/scope.md#L176` under `### Echo`)  
**Target Contract:** `Distributor.sol`  
**Primary Implementation Address (Base Mainnet):** `0x1798D23f29968b4fff7A60A90645B0939d04f47E`  
**Secondary Implementation Address (Base Mainnet):** `0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF`  
**Factory Address:** `0x3002aadad07ab12e5bb8098de3542bee2ad44fed`  
**Severity Recommendation:** **HIGH**  
**Submission Status:** **READY FOR HUMAN REVIEW**  

---

## 1. Executive Summary

A critical authorization and fee accounting flaw exists in Coinbase Echo's `Distributor` implementation contract on Base mainnet. In the Echo architecture, token releases to syndicate investors and performance fee withdrawals to deal leads require dual EIP-712 cryptographic authorization from the user/claimer and the Echo platform (`SIGNER_ROLE`).

However, neither [`ClaimData`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Types.sol#L32-L39) nor [`CarryWithdrawalData`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Types.sol#L91-L97) incorporates a `nonce` or unique identifier, and `Distributor.sol` maintains zero tracking of consumed typed-data digests. Consequently, any signed voucher remains reusable indefinitely until its timestamp expiration (`expiresAt`).

This flaw creates two distinct, high-impact exploit vectors:
1. **Performance Fee (Carry) Evasion:** An investor with unlocked tokens can replay an unexpired low-valuation voucher issued during an earlier distribution tranche when market prices appreciate. The contract evaluates the capital hurdle against the stale, depressed token price, reducing the computed performance fee to **zero** and defrauding the deal lead and platform of 100% of earned carried interest.
2. **Unauthorized Carry Pool Draining:** Because [`withdrawCarry()`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol#L393-L441) has no caller restrictions, any third party or MEV bot observing a legitimate partial carry withdrawal can replay the identical calldata in rapid succession, forcibly draining the deal lead's accrued carry pool.

---

## 2. Root Cause and Exact Code Locations

In [`Distributor.sol:305-318`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol#L305-L318):
```solidity
bytes32 digest = ClaimDataLib.digestTypedData(claimData, _domainSeparatorV4());

if (
    !isForcedDistributionModeEnabled
        && !SignatureChecker.isValidSignatureNow(user.signer, digest, claimSignatureUser)
) {
    address signer = ECDSA.recover(digest, claimSignatureUser);
    revert UnauthorizedUserSigner(signer, user.signer);
}

address signerPlatform = ECDSA.recover(digest, claimSignaturePlatform);
if (!hasRole(SIGNER_ROLE, signerPlatform)) {
    revert UnauthorizedPlatformSigner(signerPlatform);
}
```
And in [`Distributor.sol:412-426`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol#L412-L426):
```solidity
bytes32 digest = CarryWithdrawalLib.digestTypedData(data, _domainSeparatorV4());

if (
    !isForcedDistributionModeEnabled
        && !SignatureChecker.isValidSignatureNow(user.signer, digest, userSignature)
) {
    address signer = ECDSA.recover(digest, userSignature);
    revert UnauthorizedUserSigner(signer, user.signer);
}

address signerPlatform = ECDSA.recover(digest, platformSignature);
if (!hasRole(SIGNER_ROLE, signerPlatform)) {
    revert UnauthorizedPlatformSigner(signerPlatform);
}
```

**The Vulnerability:** The contract verifies cryptographic validity but never marks `digest` as consumed. It possesses no nullifier mapping (`mapping(bytes32 => bool) private _consumedDigests`). Once a voucher is validly signed by the user and platform, it remains valid for repeated execution until `block.timestamp >= expiresAt`.

---

## 3. Real-World Scenario & Quantified Economic Impact

### 3.1 Real-World Syndicate Exploit Scenario

- **Context:** An Echo SPV syndicates \$1,000,000 USDC into early-stage Seed tokens at \$0.10 per token (10,000,000 tokens total). Deal lead terms specify 20% carry (`totalCarryBPS = 2000`) on profits once principal is returned.
- **Tranche 1 (Token price \$0.10):**
  - Investor Alice holds \$10,000 in SPV capital. 100,000 tokens unlock.
  - Alice receives an authorized voucher for 50,000 tokens at \$0.10 (valid for 60 days).
  - Claim evaluation: 50,000 tokens * \$0.10 = \$5,000 USDC.
  - Hurdle: \$10,000 capital - \$5,000 claimed = \$5,000 remaining capital hurdle. Carry = \$0.
  - Alice receives 50,000 tokens.
- **Tranche 2 (Token price skyrockets to \$1.00):**
  - Another 50,000 tokens unlock for Alice.
  - **Honest Settlement:** At \$1.00, 50,000 tokens = \$50,000 USDC.
    Hurdle remaining is \$5,000. Amount subject to carry: \$50,000 - \$5,000 = \$45,000.
    Carry fee (20%): \$9,000 USDC -> 9,000 tokens. Alice gets 41,000 tokens; Deal Lead gets 9,000 tokens.
  - **Exploit via Replay:** Alice ignores the frontend and resubmits her Tranche 1 voucher (which still has 30 days before expiration).
    The contract processes the claim using the Tranche 1 price (\$0.10):
    Valuation = 50,000 * \$0.10 = \$5,000 <= \$5,000 hurdle -> **Carry = 0!**
  - **Damage:** Alice receives **all 50,000 tokens**. The deal lead loses **9,000 tokens (\$9,000 USD)** permanently.
  - Across a \$10M syndicate, millions of dollars in performance fees can be evaded.

### 3.2 Unauthorized Carry Pool Draining

- Deal lead Bob signs a voucher to withdraw 10,000 tokens of accrued carry for operational expenses out of 50,000 tokens accrued.
- An observer replays the calldata 4 times.
- Because `withdrawCarry` is permissionless, all 50,000 tokens are forcibly drained to Bob's address in one transaction bundle, causing tax crystallization, cash-flow disruption, and griefing.

---

## 4. Deterministic Proof of Concept & Evidence

The vulnerability has been proven deterministically in Foundry against the exact deployed contracts.

### Execution Commands:
```bash
export PATH="/home/nova/.foundry/bin:$PATH"
cd /home/nova/projects/cantina/bounties/base/eip-7702-proxy
forge test --match-path "test/EchoDistributorReplayPoC.t.sol" -vvv
forge test --match-path "test/EchoDistributorRegression.t.sol" -vvv
```

### Foundry PoC Results (`EchoDistributorReplayPoC.t.sol`):
```
Ran 7 tests for test/EchoDistributorReplayPoC.t.sol:EchoDistributorReplayPoCTest
[PASS] test_PropertyA_SignatureUniqueness_Falsified() (gas: 408817)
[PASS] test_PropertyB_AllocationCapEnforced_SignatureCapViolated() (gas: 491436)
[PASS] test_PropertyC_CarryAccounting_HonestBaseline() (gas: 504279)
[PASS] test_PropertyC_CarryAccounting_ReplayEvasionExploit() (gas: 409707)
[PASS] test_PropertyD_AuthorizationBinding_Enforced() (gas: 260405)
[PASS] test_PropertyE_StateTransitionConsistency() (gas: 407097)
[PASS] test_withdrawCarry_SignatureReplayExploit() (gas: 844714)
Suite result: ok. 7 passed; 0 failed; 0 skipped; finished in 2.34s
```

### Foundry Regression Results (`EchoDistributorRegression.t.sol`):
```
Ran 3 tests for test/EchoDistributorRegression.t.sol:EchoDistributorRegressionTest
[PASS] test_Regression_PatchedGate_AllowsFreshVoucher() (gas: 588508)
[PASS] test_Regression_PatchedGate_BlocksCarryWithdrawalReplay() (gas: 662231)
[PASS] test_Regression_PatchedGate_BlocksClaimReplay() (gas: 429464)
Suite result: ok. 3 passed; 0 failed; 0 skipped; finished in 2.10s
```

---

## 5. Storage Layout & Remediation

`Distributor.sol` does not contain a `__gap` storage array. Its existing state variables occupy slots 0 through 12.
Appending `mapping(bytes32 => bool) private _consumedDigests;` places the new mapping cleanly at **Slot 13**:

```diff
--- a/src/unlock/v1/Distributor.sol
+++ b/src/unlock/v1/Distributor.sol
@@ -69,6 +69,9 @@ contract Distributor is Initializable, AccessControlEnumerableUpgradeable, EIP7
     bytes16 internal constant PLATFORM_ENTITY_UUID = bytes16(0);
 
+    error SignatureAlreadyConsumed(bytes32 digest);
+
@@ -169,6 +172,9 @@ contract Distributor is Initializable, AccessControlEnumerableUpgradeable, EIP7
     bytes16[] private _carryWithdrawerUUIDs;
 
+    mapping(bytes32 => bool) private _consumedDigests;
+
@@ -306,6 +312,10 @@ contract Distributor is Initializable, AccessControlEnumerableUpgradeable, EIP7
             bytes32 digest = ClaimDataLib.digestTypedData(claimData, _domainSeparatorV4());
 
+            if (_consumedDigests[digest]) {
+                revert SignatureAlreadyConsumed(digest);
+            }
+            _consumedDigests[digest] = true;
```

This patch is 100% backward-compatible with deployed proxies and introduces zero storage collisions.

---

## 6. Duplicate & Overlap Disclosure

- **Screening Against Cantina Finding #1736:** Finding #1736 pertained to the Base EIP-7702 proxy delegation layer. Finding F-003 is strictly located in `Distributor.sol` within the Echo SPV unlock/carry subsystem.
- **Root Cause & Impact Discrepancy:** F-003 exhibits zero technical, causal, or impact overlap with #1736. It is a completely distinct, novel vulnerability.

---

## 7. Working GitHub Repository & Contract References

- Repository Root: [https://github.com/portarj482-lang/Cantina](https://github.com/portarj482-lang/Cantina)
- Target Source Code: [`Distributor.sol`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/tier1_sources/echo_Distributor_Impl/src/unlock/v1/Distributor.sol)
- PoC Harness: [`EchoDistributorReplayPoC.t.sol`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/eip-7702-proxy/test/EchoDistributorReplayPoC.t.sol)
- Regression Harness: [`EchoDistributorRegression.t.sol`](https://github.com/portarj482-lang/Cantina/blob/bf53b4f70ee62bbc369607efd4bc90a6a650e5a8/bounties/base/eip-7702-proxy/test/EchoDistributorRegression.t.sol)
- Primary Deployed Proxy: [0x1798D23f29968b4fff7A60A90645B0939d04f47E on Basescan](https://basescan.org/address/0x1798D23f29968b4fff7A60A90645B0939d04f47E#code)
- Secondary Deployed Proxy: [0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF on Basescan](https://basescan.org/address/0x1B4fA4F9BDd13Bfdec49DA85750Ab38387EE4DCF#code)
- Proxy Factory: [0x3002aadad07ab12e5bb8098de3542bee2ad44fed on Basescan](https://basescan.org/address/0x3002aadad07ab12e5bb8098de3542bee2ad44fed#code)
