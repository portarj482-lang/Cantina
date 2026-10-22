# Smart Contract Security Field Guide: Vulnerability Patterns

> **Attribution & Provenance:**
> Conceptual reference based on the *Smart Contract Security Field Guide* by Dominik Muhs (Zensical). All explanations, code snippets, and PoC templates below are original clean-room implementations for Solidity >=0.8.20 and Foundry.
>
> **Triage Rule:** Pattern tiers listed below represent **starting hypotheses only**. In bug bounty practice (Immunefi, Cantina), final severity is never determined by vulnerability category alone; it is determined exclusively by demonstrated economic impact, prerequisite attacker permissions, and program-specific rules in `scope.md`.

---

## Pattern Index

1. [ABI Hash Collisions](#1-abi-hash-collisions)
2. [Ambiguous Evaluation Order](#2-ambiguous-evaluation-order)
3. [Unexpected Ether Transfers (Force-Feeding)](#3-unexpected-ether-transfers-force-feeding)
4. [Exposed Data & On-Chain Privacy](#4-exposed-data--on-chain-privacy)
5. [Frontrunning & MEV (Displacement, Insertion, Suppression)](#5-frontrunning--mev)
6. [Griefing & Denial of Service](#6-griefing--denial-of-service)
7. [Inline Assembly & Yul Hazards](#7-inline-assembly--yul-hazards)
8. [Oracle Manipulation Attacks](#8-oracle-manipulation-attacks)
9. [Reentrancy Spectrum (Single, Cross-Function, Read-Only)](#9-reentrancy-spectrum)
10. [Signature-Related Attacks](#10-signature-related-attacks)
11. [Unprotected Swaps & Slippage](#11-unprotected-swaps--slippage)
12. [Use of tx.origin & Fragile EOA Detection](#12-use-of-txorigin--fragile-eoa-detection)

---

## 1. ABI Hash Collisions

### Root Cause
`abi.encodePacked` packs elements consecutively without length prefixes or type padding. When hashing multiple dynamic arguments (such as `bytes`, `string`, or dynamic arrays `T[]`), shifting data across adjacent elements yields identical packed byte sequences and hash digests.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; depends on whether the hash controls permissions, minting, or payout storage).

### Vulnerable Code Pattern
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VulnerableRegistry {
    mapping(bytes32 => bool) public executedClaims;

    // Vulnerable: two consecutive dynamic arrays in encodePacked
    function claimReward(address[] calldata recipients, uint256[] calldata amounts) external {
        bytes32 claimHash = keccak256(abi.encodePacked(recipients, amounts));
        require(!executedClaims[claimHash], "Already claimed");
        executedClaims[claimHash] = true;
        // Payout logic...
    }
}
```

### Mitigated Code Pattern
```solidity
// Use abi.encode instead of abi.encodePacked
bytes32 claimHash = keccak256(abi.encode(recipients, amounts));
```

### Detection Signals
- **Slither:** `abi-encode-packed-collision`
- **Semgrep:** `solidity.security.abi-encode-packed-collision`

### Foundry PoC Blueprint
```solidity
function test_PoC_ABIHashCollision() public {
    // Array A1 + A2 produce identical bytes to B1 + B2 under encodePacked
    bytes memory packed1 = abi.encodePacked(new address[](1), new address[](2));
    bytes memory packed2 = abi.encodePacked(new address[](2), new address[](1));
    // Verify collision
    assertEq(keccak256(packed1), keccak256(packed2));
}
```

---

## 2. Ambiguous Evaluation Order

### Root Cause
Solidity's expression evaluation order is not fully specified by the language. Expressions that read and mutate state within the same statement (e.g., `x * x++` or `f(g(x), h(x))`) produce unspecified order-of-evaluation behavior across compiler versions and optimizer configurations.

### Starting Severity Hypothesis
- **Tier:** Medium to High (Hypothesis only; depends on whether evaluation order alters balance or access state).

### Vulnerable Code Pattern
```solidity
function computeFee(uint256 balance) external returns (uint256) {
    // Vulnerable: reading and incrementing state in the same arithmetic expression
    return balance * balance++;
}
```

### Mitigated Code Pattern
```solidity
function computeFee(uint256 balance) external returns (uint256) {
    uint256 initial = balance;
    balance += 1;
    return initial * balance;
}
```

### Detection Signals
- **Slither:** `order-of-evaluation`

---

## 3. Unexpected Ether Transfers (Force-Feeding)

### Root Cause
Smart contracts cannot refuse incoming Ether delivered via `selfdestruct(payable(target))` or coinbase block rewards. In addition, address calculation via `CREATE` or `CREATE2` allows sending Ether to a contract address before its bytecode is deployed. Invariants relying on exact balance equality (`address(this).balance == totalDeposits`) can be broken by any caller.

### Starting Severity Hypothesis
- **Tier:** Medium to High (Hypothesis only; depends on whether balance mismatch freezes funds or bricks contract logic).

### Vulnerable Code Pattern
```solidity
// Vulnerable: strict balance equality
require(address(this).balance == totalShares * sharePrice, "Balance invariant broken");
```

### Mitigated Code Pattern
```solidity
// Track internal deposit accounting rather than trusting raw balance
require(internalTrackedBalance >= requiredAmount, "Insufficient funds");
```

### Detection Signals
- **Slither:** `incorrect-equality`, `suicidal`

---

## 4. Exposed Data & On-Chain Privacy

### Root Cause
All data on a public blockchain (including `private` variables) is transparent and readable via storage slot inspection or historical event calldata. Storing user emails, IP addresses, or KYC hashes on-chain breaks pseudonymity, enables targeted infrastructure phishing/DoS, and risks GDPR non-compliance.

### Starting Severity Hypothesis
- **Tier:** Typically **Out of Scope / Informational** in bug bounty programs unless accompanied by a demonstrable cryptographic exploit or direct fund drain.

### Detection Signals
- **Manual review:** Inspect storage variables and event definitions for plain strings, emails, or server hostnames.

---

## 5. Frontrunning & MEV

### Root Cause
Transactions in the public mempool can be observed, reordered, or censored by searchers and validators before inclusion. Three primary attack variants:
1. **Displacement:** Attacker bids higher priority gas to execute their transaction first (e.g., claiming a public challenge).
2. **Insertion (Sandwich):** Attacker buys before a target swap and sells immediately after, exploiting slippage tolerance.
3. **Suppression (Block Stuffing):** Attacker floods the block gas limit to delay time-critical liquidation or oracle update calls.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; depends on extractable value, fee theft, or bad debt accumulation).

### Mitigated Code Pattern
- Use commit-reveal schemes with secret nonces.
- Enforce strict deadline timestamps and non-zero `amountOutMinimum` parameters.
- Direct sensitive transactions through private mempools / MEV protection builders (e.g., Flashbots Protect).

### Detection Signals
- **Slither:** `arbitrary-send-erc20`, `timestamp`

---

## 6. Griefing & Denial of Service

### Root Cause
An attacker expends negligible capital (e.g. 1 wei) to prevent legitimate users from accessing functionality, withdrawing funds, or executing liquidations.
- **Timestamp Reset Griefing:** Unbounded micro-deposits resetting a global `lastDepositTime`.
- **EIP-150 63/64 Gas Griefing:** Relayers forwarding insufficient gas to an untrusted external call, causing the child call to fail while the outer transaction succeeds, burning user execution quotas without completing state changes.

### Starting Severity Hypothesis
- **Tier:** Medium to High (Hypothesis only; depends on temporary vs permanent freeze of user capital).

### Detection Signals
- **Slither:** `calls-loop`, `uninitialized-state`

---

## 7. Inline Assembly & Yul Hazards

### Root Cause
Yul assembly bypasses Solidity's type safety, overflow checks, memory management, and ABI decoding protections. Common hazards:
1. **Free Memory Pointer (`0x40`) Corruption:** Writing past allocated memory without bumping the free memory pointer causes subsequent `abi.encode` calls to overwrite data.
2. **Dirty Bits:** Assembly loads 32-byte words from calldata without masking unused high-order bits for types smaller than 32 bytes (such as `address` which occupies 20 bytes, or `uint16`).
3. **Manual Calldata Decoding:** Using `calldataload` without validating `calldatasize()` silently reads zeroes for out-of-bounds offsets.
4. **Transient Storage (`tstore`/`tload`) Leaks:** Transient slots persist across all calls within the same transaction. Failing to clear transient state at the end of execution allows subsequent re-entrant calls or multicalls to inherit stale flags.
5. **Return Data Expansion Bomb:** Using `returndatacopy` without bounding `returndatasize()` allows a malicious callee to return megabytes of memory, forcing the caller to exhaust gas.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; depends on memory corruption consequences).

### Detection Signals
- **Slither:** `assembly`, `controlled-delegatecall`

---

## 8. Oracle Manipulation Attacks

### Root Cause
Relying on instantaneous spot prices from decentralized exchanges (e.g. `UniswapV3Pool.slot0` or V2 reserves) allows an attacker to manipulate the reported price within a single transaction using flash loans, triggering undercollateralized borrowing or fraudulent liquidations.

### Starting Severity Hypothesis
- **Tier:** Critical (Hypothesis only; direct protocol reserve drain).

### Mitigated Code Pattern
- Enforce multi-period Time-Weighted Average Prices (TWAP) with sufficient window length.
- Query decentralized oracle networks (Chainlink, RedStone) with heartbeat and round completeness checks.
- Enforce maximum price deviation thresholds against secondary fallback oracles.

### Detection Signals
- **Slither:** `dex-pair-oracle`, `divide-before-multiply`

---

## 9. Reentrancy Spectrum

### Root Cause
External calls hand execution control over to the recipient contract before state mutations are finalized.
- **Single-Function:** Classic DAO-style recursive withdrawal.
- **Cross-Function:** Invoking a second function sharing the unupdated storage variable.
- **Cross-Contract / Read-Only:** A view function in contract A returns stale balance/price state during an external call from contract B, allowing contract C to execute invalid trades based on stale view data.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; depends on whether reentrancy can alter balances or pricing).

### Mitigated Code Pattern
- Apply the **Checks-Effects-Interactions (CEI)** pattern unconditionally.
- Use OpenZeppelin's `ReentrancyGuard` or transient storage locks.
- For read-only reentrancy, ensure view functions expose reentrancy guards or query non-reentrant state.

### Detection Signals
- **Slither:** `reentrancy-eth`, `reentrancy-no-eth`, `reentrancy-benign`, `reentrancy-events`

---

## 10. Signature-Related Attacks

### Root Cause
Cryptographic signatures on Ethereum are susceptible to:
1. **Zero-Address Recovery:** If `ecrecover` fails, it returns `address(0)`. If uninitialized admin state is `address(0)`, arbitrary signatures validate as admin.
2. **Signature Replay:** Signatures lacking a unique `nonce` can be re-executed repeatedly.
3. **Cross-Chain Replay:** Signatures lacking `block.chainid` (e.g. non-EIP-712 envelopes) can be replayed across forks or L2s.
4. **Signature Malleability:** Given a valid $(r, s, v)$, $(r, -s \pmod n, v \oplus 1)$ is also valid. OpenZeppelin's `ECDSA` restricts $s \le n/2$.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; depends on unauthorized fund transfer or role takeover).

### Mitigated Code Pattern
- Always use OpenZeppelin `ECDSA.recover` or verify `signer != address(0)`.
- Use EIP-712 structured typed data with domain separator including `block.chainid` and `verifyingContract`.

### Detection Signals
- **Slither:** `missing-zero-check`, `signature-malleability`

---

## 11. Unprotected Swaps & Slippage

### Root Cause
Decentralized swaps executed with `amountOutMinimum: 0` or missing deadline checks allow MEV bots to sandwich the trade, forcing 100% slippage loss on the protocol or user.

### Starting Severity Hypothesis
- **Tier:** High to Critical (Hypothesis only; directly extractable token loss).

### Mitigated Code Pattern
```solidity
// Require caller or off-chain quoter to specify minimum acceptable return
require(amountOutMinimum > 0, "Zero slippage protection disallowed");
ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
    tokenIn: tokenIn,
    tokenOut: tokenOut,
    fee: poolFee,
    recipient: address(this),
    amountIn: amountIn,
    amountOutMinimum: amountOutMinimum,
    sqrtPriceLimitX96: 0
});
```

### Detection Signals
- **Slither:** `arbitrary-send-erc20`, `unchecked-lowlevel`

---

## 12. Use of tx.origin & Fragile EOA Detection

### Root Cause
`tx.origin` represents the original sender of the transaction, while `msg.sender` represents the immediate caller.
1. **Phishing Authentication:** Checking `require(tx.origin == owner)` allows an attacker to trick the owner into calling a malicious contract, which forwards the call to the protected function.
2. **Fragile EOA Detection:** Using `require(tx.origin == msg.sender)` to restrict callers to EOAs breaks with EIP-7702 (delegated accounts) and ERC-4337 account abstraction wallets.

### Starting Severity Hypothesis
- **Tier:** Medium to High (Hypothesis only; depends on whether phishing can trigger privileged operations).

### Mitigated Code Pattern
- Never use `tx.origin` for authorization; use `msg.sender` or explicit role registries.
- Avoid discriminating between EOAs and smart contract accounts; use ERC-1271 for signature verification.

### Detection Signals
- **Slither:** `tx-origin`
