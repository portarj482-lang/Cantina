"""Unit tests for central execution policy and capability authorization (policies/execution_policy.py)."""
from __future__ import annotations

import unittest

from universal_adaptive_engine.policies.execution_policy import (
    ExecutionPolicy,
    ExecutionMode,
)


class CantinaExecutionPolicyTestCase(unittest.TestCase):
    """Test suite evaluating execution policy constraints and capability authorization."""

    def test_default_execution_policy_valid(self):
        policy = ExecutionPolicy()
        self.assertEqual(policy.mode, ExecutionMode.FORK_ONLY)
        self.assertFalse(policy.allow_broadcast)
        self.assertFalse(policy.allow_private_key_access)
        self.assertFalse(policy.allow_live_funds)
        # Default policy must validate cleanly
        policy.validate()

    def test_policy_rejects_allow_broadcast(self):
        policy = ExecutionPolicy(allow_broadcast=True)
        with self.assertRaises(ValueError) as ctx:
            policy.validate()
        self.assertIn("Transaction broadcasting is prohibited", str(ctx.exception))

    def test_policy_rejects_allow_private_key_access(self):
        policy = ExecutionPolicy(allow_private_key_access=True)
        with self.assertRaises(ValueError) as ctx:
            policy.validate()
        self.assertIn("Private-key access is prohibited", str(ctx.exception))

    def test_policy_rejects_allow_live_funds(self):
        policy = ExecutionPolicy(allow_live_funds=True)
        with self.assertRaises(ValueError) as ctx:
            policy.validate()
        self.assertIn("Live-funds access is prohibited", str(ctx.exception))

    def test_authorize_capability_denies_prohibited_tools(self):
        policy = ExecutionPolicy()
        prohibited_capabilities = [
            "broadcast",
            "forge_broadcast",
            "cast_send",
            "private_key_read",
            "private_key_export",
            "live_funds",
            "FORGE_BROADCAST",  # case-insensitive check
            " CAST_SEND ",     # whitespace trimming check
        ]
        for cap in prohibited_capabilities:
            with self.assertRaises(PermissionError) as ctx:
                policy.authorize_capability(cap)
            self.assertIn("Execution policy denies capability", str(ctx.exception))

    def test_authorize_capability_allows_safe_tools(self):
        policy = ExecutionPolicy()
        safe_capabilities = [
            "static_analysis",
            "compile",
            "read_file",
            "fork_test",
            "local_simulation",
        ]
        for cap in safe_capabilities:
            # Should not raise
            policy.authorize_capability(cap)


if __name__ == "__main__":
    unittest.main()
