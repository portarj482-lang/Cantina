// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SyntheticVaultPatched
 * @notice Patched negative control for SyntheticVault.
 * Follows Checks-Effects-Interactions and includes a reentrancy guard.
 */
contract SyntheticVaultPatched {
    mapping(address => uint256) public shares;
    uint256 public totalShares;
    uint256 public totalAssets;
    bool private _locked;

    modifier nonReentrant() {
        require(!_locked, "ReentrancyGuard: reentrant call");
        _locked = true;
        _;
        _locked = false;
    }

    function deposit() external payable {
        require(msg.value > 0, "Zero deposit");
        shares[msg.sender] += msg.value;
        totalShares += msg.value;
        totalAssets += msg.value;
    }

    function withdraw(uint256 amount) external nonReentrant {
        require(shares[msg.sender] >= amount, "Insufficient shares");
        // Effect before interaction
        shares[msg.sender] -= amount;
        totalShares -= amount;
        totalAssets -= amount;

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
    }
}
