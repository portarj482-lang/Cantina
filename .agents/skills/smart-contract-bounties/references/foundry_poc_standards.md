# Foundry Proof-of-Concept Engineering Standards

A PoC that passes for the wrong reason is worse than none. Every PoC written or judged must strictly satisfy the **8 Non-Negotiables**.

---

## The 8 Non-Negotiables

1. **Right Reason Assertions**:
   - Assert the precise intermediate state that causes the failure before calling `vm.expectRevert`.
   - Never use a bare `vm.expectRevert();`. Always specify the exact error selector (e.g. `abi.encodeWithSelector(CustomError.selector, arg)`) or standard error panic (`stdError.divisionError`, `stdError.arithmeticError`).
2. **Real Entrypoint Only**:
   - The test must call the exact public/external function an attacker would call (`vault.withdraw`, `pool.swap`, `liquidate`), never an internal mock helper or an isolated test-only hook.
3. **Legal State Only**:
   - Mocks and setup must never produce an impossible state (e.g. impossible TWAP cumulatives, negative oracle prices, out-of-order nonces, ticks outside bounds).
4. **No Disabled Protections**:
   - Never artificially raise slippage limits (`maxPoolPriceDifference = 100%`) or bypass access controls unless the vulnerability specifically breaks that protection.
5. **Unprivileged Attacker**:
   - The attacker address must be initialized via `makeAddr("attacker")` with no default balances, approvals, or roles beyond what any permissionless on-chain actor can obtain.
6. **Exact Numerical Deltas**:
   - Assert `balanceBefore`, `balanceAfter`, and `delta = balanceAfter - balanceBefore`.
   - Never rely solely on loose inequalities like `assertGt(delta, 0)`.
7. **Four-Test Suite Structure**:
   - `test_Benign()`: Demonstrates standard honest protocol behavior without attack.
   - `test_Exploit()`: Executes attack and proves fund drain or permanent freeze.
   - `test_Boundary()`: Proves that input 1 unit outside exploit boundary fails or behaves safely.
   - `test_PostPatch()`: Shows that the proposed mitigation prevents the exploit without breaking benign behavior.
8. **Deterministic Fork Pinning**:
   - Always pin `--fork-block-number` or `vm.createSelectFork(rpc, blockNumber)`.
   - Run the exploit 5 times consecutively to prove zero non-determinism.

---

## Canonical PoC Skeleton

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Test, console2} from "forge-std/Test.sol";
import {IVault} from "../src/interfaces/IVault.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract PoC_Exploit_Template is Test {
    IVault public targetVault;
    IERC20 public assetToken;

    address public attacker = makeAddr("attacker");
    address public victim = makeAddr("victim");

    uint256 public constant FORK_BLOCK = 21000000;

    function setUp() public {
        // Deterministic fork setup
        string memory rpc = vm.envOr("RPC_URL", string("https://eth.llamarpc.com"));
        vm.createSelectFork(rpc, FORK_BLOCK);

        targetVault = IVault(0x1111111111111111111111111111111111111111);
        assetToken = IERC20(targetVault.asset());
    }

    /// @notice 1. Benign Control Test
    function test_BenignDepositAndWithdraw() public {
        deal(address(assetToken), victim, 100 ether);
        vm.startPrank(victim);
        assetToken.approve(address(targetVault), 100 ether);
        targetVault.deposit(100 ether, victim);
        targetVault.withdraw(100 ether, victim, victim);
        vm.stopPrank();

        assertEq(assetToken.balanceOf(victim), 100 ether, "Honest user balance restored");
    }

    /// @notice 2. Exploit Test
    function test_Exploit() public {
        uint256 attackerStart = assetToken.balanceOf(attacker);
        uint256 vaultStart = assetToken.balanceOf(address(targetVault));

        vm.startPrank(attacker);
        // Execute attack vector through real entrypoint
        // ...
        vm.stopPrank();

        uint256 attackerEnd = assetToken.balanceOf(attacker);
        uint256 vaultEnd = assetToken.balanceOf(address(targetVault));

        uint256 stolenAmount = attackerEnd - attackerStart;
        assertEq(stolenAmount, 50 ether, "Exact stolen amount matches calculation");
        assertEq(vaultStart - vaultEnd, stolenAmount, "Vault funds drained exactly");
    }
}
```
