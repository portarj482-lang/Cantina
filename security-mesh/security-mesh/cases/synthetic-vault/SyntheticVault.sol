// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SyntheticVault
 * @notice Synthetic fixture demonstrating an accounting invariant vulnerability for Security Mesh testing.
 * Invariant: Total recorded assets must equal or exceed total user share balance.
 * Vulnerability: Flawed share redemption allows redeeming shares before updating internal share balance.
 */
contract SyntheticVault {
    mapping(address => uint256) public shares;
    uint256 public totalShares;
    uint256 public totalAssets;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);

    function deposit() external payable {
        require(msg.value > 0, "Zero deposit");
        shares[msg.sender] += msg.value;
        totalShares += msg.value;
        totalAssets += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    // Vulnerable function: transfers before updating shares
    function withdraw(uint256 amount) external {
        require(shares[msg.sender] >= amount, "Insufficient shares");
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        shares[msg.sender] -= amount;
        totalShares -= amount;
        totalAssets -= amount;
        emit Withdrawn(msg.sender, amount);
    }
}
