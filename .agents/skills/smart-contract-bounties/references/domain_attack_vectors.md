# Domain Attack Vectors & Checklists

## 1. EIP-7702 Delegated Accounts
- [ ] **ERC-1271 Validation Fallback**: Proxy catches implementation failure and falls back to `ECDSA.tryRecover(...) == address(this)`. When ownership rotates in a smart account, the revoked EOA key retains permanent signing power over Permit2/Seaport.
- [ ] **Cross-Chain Replay Tuples**: Authorization tuples signed with `chainId = 0` replayed across networks where nonce tracking or bytecode differs.
- [ ] **Bytecode Length & Aliasing**: Code checking `_account.code.length == 0` misclassifying 7702 accounts. Ensure bridge aliasing or `onlyEOA` accounts for `isDelegated(msg.sender)`.
- [ ] **Storage Collisions on Delegation Change**: Delegating to implementation A, mutating storage, revoking, and delegating to implementation B without namespaced storage (ERC-7201).
- [ ] **Execution Context Reentrancy**: Calls execute in context of EOA (`address(this) == EOA`). Verify internal `msg.sender` validation.

---

## 2. ERC-4337 Account Abstraction & Paymasters
- [ ] **validatePaymasterUserOp Invariants**: Paymaster validation logic must not rely on mutable global state that can change between simulation and execution.
- [ ] **PostOp Gas Accounting & Griefing**: Unbounded gas consumed in `postOp` causing reverted transactions charged to the paymaster.
- [ ] **Signature Replay & Hash Mismatches**: UserOp hash calculation omitting entrypoint address, chain ID, or paymaster data.
- [ ] **MagicSpend / Allowance Draining**: Paymaster allowance withdrawal without strict nonce tracking or expiration checks.
- [ ] **Bundler Reputation Attacks**: Exploiting storage access rules (accessing third-party storage during validation) causing bundlers to ban honest paymasters.

---

## 3. EIP-1153 Transient Storage (TSTORE / TLOAD)
- [ ] **Missing End-of-Transaction Cleanup**: Transient storage persists across all calls within the same transaction. If values (e.g. reentrancy locks, transient allowances, fee accumulators) are not explicitly zeroed out at the end of the root call, subsequent calls within multicall or batch operations inherit stale values.
- [ ] **Reentrancy Guard Reset Inconsistencies**: A modifier using `tstore(SLOT, 1)` that reverts without resetting or fails to handle cross-contract calls cleanly.
- [ ] **Transient Allowance Leaks**: Contracts implementing temporary ERC-20 allowances via `tstore` permitting attackers to drain unused allowances in subsequent calls of the same bundle.

---

## 4. Uniswap v4 & Hook Architecture
- [ ] **Hook Return Delta Mismatches**: Hooks implementing `beforeSwap` or `afterSwap` returning `BeforeSwapDelta` or taking fees without settling deltas via `poolManager.settle()` or `poolManager.take()`.
- [ ] **Unlocked Callback Reentrancy**: Exploiting `unlock()` callback to perform state modifications or re-enter the PoolManager before pending deltas are cleared.
- [ ] **Dynamic Fee Manipulation**: Volatile swap fee hooks manipulable via sandwiching or flash swaps.
- [ ] **Hook Permission Flags**: Hooks registered with incorrect flag masks (e.g. claiming `BEFORE_SWAP_RETURNS_DELTA_FLAG` but not implementing proper settlement).

---

## 5. Lending, Vaults & Collateral Ratios
- [ ] **Share Price Inflation (First Depositor Attack)**: Vault donating dust assets or manipulating exchange rate between asset and share tokens to dilute subseqent depositors.
- [ ] **Bad Debt Socialization**: Underwater loans unable to be liquidated due to strict tick ranges, price divergence, or dust thresholds.
- [ ] **Liquidation Frontrunning & Health Factor Timing**: Borrowers frontrunning liquidation calls with minimal repayments or price adjustments to cause liquidator transactions to revert.
- [ ] **Collateral Valuation & Decimal Normalization**: Inconsistent scaling when computing borrowing capacity across assets with differing decimal precisions (e.g. USDC 6 decimals vs WETH 18 decimals).

---

## 6. Oracles & Pricing Feeds
- [ ] **Staleness & Sequencer Uptime**: Chainlink `latestRoundData()` missing checks for `updatedAt == 0`, `answeredInRound < roundId`, timestamp older than heartbeat, or L2 sequencer downtime.
- [ ] **Min/Max Circuit Breaker Clamping**: Aggregator returning `minAnswer` or `maxAnswer` during extreme market crashes, causing overvalued collateral.
- [ ] **Spot Price / Single-Block TWAP Manipulation**: Reading spot reserves from AMMs or short-period TWAPs vulnerable to flash-loan skewing.
