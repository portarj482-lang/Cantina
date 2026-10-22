# Kill Taxonomy & Pre-PoC Checklist

Before investing time in writing a full Foundry PoC, run candidate leads through these 8 kill questions. If any check fails, **kill the hypothesis immediately** and record the kill reason.

---

## The 8 Top Kill Questions

1. **Unprivileged Actor Test**: Can an unprivileged, untrusted caller actually invoke this function path with arbitrary parameters? Or is it blocked by `onlyOwner`, `onlyRole`, `internal`, or `private`?
2. **Reentrancy Guard Verification**: Does a modifier (`nonReentrant`, `lock`, `tstore` guard) surround the execution path? Check if re-entering the state reverts with the guard's specific error.
3. **Legal State Bounds**: Can the required preconditions (e.g. zero reserve, mismatched tick, uninitialized state) actually exist in production with real external tokens and contracts?
4. **Economic Profitability (Gas & Fees)**: Does the extracted value strictly exceed the transaction fees, flash loan fees, swap slippage, and protocol exit taxes? If the gain is bounded to dust (<$10), the severity is at best Informational.
5. **Clearable State / Permissionless Reset**: Can another honest actor or keeper easily neutralize the intermediate attack state via standard permissionless calls (e.g. `sync()`, `poke()`, `repay()`, `liquidate()`)?
6. **Known Issue / Excluded Assumption**: Is this behavior explicitly listed in the program rules, protocol documentation, README, or previous audits as an "accepted risk" or "design decision"?
7. **Cross-Contract Assumption Validity**: If the claim assumes an external token or dependency returns a specific value or fails, does the actual deployed contract on that chain (e.g. WETH9, USDT, Uniswap Pool) behave that way?
8. **Permanent vs Temporary Impact**: If claiming Denial of Service, does it cause permanent freezing of funds or unbounded degradation? Temporary delays that resolve naturally after a cooldown period are generally Low/Informational under standard bug bounty scales.

---

## Kill Logging Standard

When killing a lead, always record:
- **Hypothesis ID**: `H-###`
- **Kill Category**: e.g., `access-control-blocked`, `reentrancy-guard-active`, `illegal-state-dependency`, `dust-bounded-loss`, `known-design-decision`
- **Kill Reason**: Exact file, line, and code guard that invalidates the exploit path
- **Evidence**: Source line reference `[SRC: path:line @commit]` or command output
