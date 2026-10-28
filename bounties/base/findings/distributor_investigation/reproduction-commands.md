# Deterministic Reproduction Commands: Coinbase Echo Distributor (F-003)

To execute the verified test suites independently from any shell environment:

```bash
# 1. Ensure Foundry binary is in PATH
export PATH="/home/nova/.foundry/bin:$PATH"

# 2. Navigate to test repository
cd /home/nova/projects/cantina/bounties/base/eip-7702-proxy

# 3. Execute Exploit PoC Suite (7 tests)
forge test --match-path "test/EchoDistributorReplayPoC.t.sol" -vvv

# 4. Execute Remediation Regression Suite (3 tests)
forge test --match-path "test/EchoDistributorRegression.t.sol" -vvv

# 5. Execute with full transaction call tracing
forge test --match-test "test_PropertyC_CarryAccounting_ReplayEvasionExploit" -vvvv
forge test --match-test "test_withdrawCarry_SignatureReplayExploit" -vvvv
```
