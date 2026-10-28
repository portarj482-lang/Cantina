# 02 — Invariant and Callgraph Specification: Coinbase Echo Distributor

**Finding Reference:** `F-003 / CANTINA-ECHO-DISTRIBUTOR-001`  
**Target:** `Distributor.sol` (`0x1798D23f29968b4fff7A60A90645B0939d04f47E`)  
**Network:** Base Mainnet (`8453`)  

---

## 1. Full Claim Lifecycle Execution Trace

The lifecycle of an Echo token distribution claim and performance fee settlement operates through eight distinct stages:

```
[1. Voucher Creation]
       │
       ▼
[2. Dual EIP-712 Signing]  (Claimant + Platform SIGNER_ROLE)
       │
       ▼
[3. Distribution Identification]  (tokenDistributionUUID matching)
       │
       ▼
[4. Signature Verification]  (SignatureChecker.isValidSignatureNow for both keys)
       │
       ▼
[5. Allocation & Quota Check]  (_claimable() >= claimData.amount)
       │
       ▼
[6. Valuation & Carry Computation]  (price.convertTokenToUSDC & _calculateCarryAmount)
       │
       ▼
[7. Accounting Mutation]  (state.amountClaimed += amount; state.amountClaimedUSDC += amountUSDC)
       │
       ▼
[8. Token Settlement]  (token.safeTransfer to receiver; carry added to pool)
```

---

## 2. Callgraph Reconstruction

### 2.1 Token Claim Callgraph (`claim`)
```solidity
Distributor.claim(ClaimData claimData, bytes sigUser, bytes sigPlatform, Claimer user, bytes32[] proof, bool pullUnlocked)
 ├── _checkSender(claimData.entityUUID, user.signer)
 ├── _verifyClaimerInMerkleTree(user, proof)
 └── _release(claimData, sigUser, sigPlatform, user, pullUnlocked)
      ├── ClaimDataLib.digestTypedData(claimData, _domainSeparatorV4())
      ├── SignatureChecker.isValidSignatureNow(user.signer, digest, sigUser)
      ├── SignatureChecker.isValidSignatureNow(platformSigner, digest, sigPlatform)
      ├── _claimable(claimData.entityUUID, user.distributionShares, pullUnlocked)
      │    └── unlocker.unlocked() - state.amountClaimed
      ├── claimData.price.convertTokenToUSDC(claimData.amount)
      ├── _calculateCarryAmount(...)
      │    └── evaluated against user.amountInvestedUSDC hurdle
      ├── state.amountClaimed += claimData.amount;           <-- VULNERABLE ADDITIVE STATE
      ├── state.amountClaimedUSDC += uint64(amountUSDC);     <-- VULNERABLE ADDITIVE VALUATION
      ├── totalClaimed += claimData.amount;
      ├── totalCarryGenerated += amountCarry;
      └── token.safeTransfer(claimData.receiver, claimData.amount - amountCarry)
```

### 2.2 Carry Withdrawal Callgraph (`withdrawCarry`)
```solidity
Distributor.withdrawCarry(CarryWithdrawalData data, bytes userSig, bytes platformSig)
 ├── CarryWithdrawalDataLib.digestTypedData(data, _domainSeparatorV4())
 ├── SignatureChecker.isValidSignatureNow(withdrawer.signer, digest, userSig)
 ├── SignatureChecker.isValidSignatureNow(platformSigner, digest, platformSig)
 ├── _carryWithdrawable(data.entityUUID, totalCarryWithdrawn)
 ├── _carryWithdrawn[data.entityUUID] += data.amount;        <-- VULNERABLE ADDITIVE STATE
 ├── totalCarryWithdrawn += data.amount;
 └── token.safeTransfer(data.receiver, data.amount)
```

---

## 3. Formal Security Invariants

### INV-DISTRIB-01: Signature Digest Monotonic Consumption
$$\forall d = \text{digestTypedData}(C), \quad \text{Executions}(d) \le 1$$
**Formal Statement:** An authenticated voucher digest $d$ signed by claimant and platform must be consumed upon first execution and cannot be replayed.  
**Observed Violation:** The contract does not store consumed digests in any mapping or nullifier bitmap. Replaying the identical calldata succeeds for any subsequent block timestamp $T < \text{expiresAt}$ as long as additional tokens have unlocked.

### INV-DISTRIB-02: Valuation Timing Consistency
$$\text{Valuation}(T_{\text{claim}}) = P(T_{\text{claim}})$$
**Formal Statement:** The USD valuation used to calculate hurdle recovery and performance fees (carried interest) must reflect the economic conditions at the time of claim, not an arbitrary historical snapshot from an earlier tranche.  
**Observed Violation:** When market prices surge from \$1.00 to \$10.00, replaying the \$1.00 voucher forces the contract to evaluate the new claim at \$1.00 USDC, completely resetting carry generation to 0.

### INV-DISTRIB-03: Carried Interest Conservation
$$\text{TotalCarryCollected} = \max\left(0, \left(\sum \text{ValueClaimed} - \text{Hurdle}\right) \times \text{CarryBPS}\right)$$
**Formal Statement:** Deal leads and the platform must receive their legally entitled percentage of investment profits above the capital return hurdle.  
**Observed Violation:** By replaying low-valuation vouchers, claimants extract 100% of unlocked tokens gross, reducing $\text{TotalCarryCollected}$ by 100% of the deal lead's earned carry.

### INV-DISTRIB-04: Non-Interactive Withdrawal Authorization
$$\forall W \in \text{WithdrawalEvents}, \quad \text{AuthorizedAmount}(W) = \text{SignedAmount}(W)$$
**Formal Statement:** A deal lead's accrued carry balance may only be reduced by the exact amounts authorized for distribution.  
**Observed Violation:** Replaying a 50-token withdrawal signature allows an external caller to liquidate 150 tokens from the deal lead's pool without authorization.
