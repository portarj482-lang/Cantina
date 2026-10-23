// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VaultFuzzHarness {
    uint256 public totalAssets;
    uint256 public totalLiabilities;
    address public owner;

    constructor() {
        owner = msg.sender;
        totalAssets = 1000;
        totalLiabilities = 500;
    }

    function deposit(uint256 amount) external payable {
        totalAssets += amount;
    }

    function borrow(uint256 amount) external {
        totalLiabilities += amount;
    }

    function liquidate() external {
        if (totalLiabilities > totalAssets) {
            totalAssets = 0;
            totalLiabilities = 0;
        }
    }

    // Echidna Invariant 1: Total assets should always back liabilities
    function echidna_test_solvency() public view returns (bool) {
        return totalAssets >= totalLiabilities;
    }

    // Echidna Invariant 2: Contract owner should never be address(0)
    function echidna_test_owner_retained() public view returns (bool) {
        return owner != address(0);
    }
}
