"""Unit tests for Architecture Adapters (HostEnvironmentAdapter, CantinaBountyAdapter)."""
import unittest
from pathlib import Path

from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter
from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter


class AdaptersTestCase(unittest.TestCase):
    def setUp(self):
        self.workspace_root = Path("/home/nova/projects/cantina")
        self.host_adapter = HostEnvironmentAdapter(self.workspace_root)
        self.cantina_adapter = CantinaBountyAdapter(self.workspace_root)

    def test_protocol_conformance(self):
        # Both adapters must satisfy the ArchitectureAdapter runtime protocol
        self.assertIsInstance(self.host_adapter, ArchitectureAdapter)
        self.assertIsInstance(self.cantina_adapter, ArchitectureAdapter)

    def test_host_adapter_discovery(self):
        disc = self.host_adapter.discover()
        self.assertEqual(disc["adapter"], "host-environment-adapter")
        self.assertEqual(disc["workspace_root"], str(self.workspace_root))
        self.assertIn("os", disc)
        self.assertIn("python.runtime", disc["capabilities"])
        self.assertTrue(len(disc["evidence"]) > 0)

    def test_host_adapter_contract_validation(self):
        valid_contract = {
            "task_id": "TASK-H01",
            "permissions_required": ["filesystem.read"],
            "inputs": ["INSTRUCTIONS.md"],
        }
        res_valid = self.host_adapter.validate_contract(valid_contract)
        self.assertTrue(res_valid["valid"])
        self.assertEqual(res_valid["recommendation"], "PROCEED")

        invalid_contract = {
            "task_id": "TASK-H02",
            "permissions_required": ["network.outbound"],
            "inputs": ["../../etc/passwd"],
        }
        res_invalid = self.host_adapter.validate_contract(invalid_contract)
        self.assertFalse(res_invalid["valid"])
        self.assertEqual(res_invalid["recommendation"], "REJECT_OR_ADAPT")
        self.assertTrue(any("network" in iss.lower() for iss in res_invalid["issues"]))

    def test_host_adapter_execute_inspect_path(self):
        res = self.host_adapter.execute({
            "task_id": "TASK-H03",
            "action": "inspect_path",
            "inputs": ["INSTRUCTIONS.md"],
        })
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "COMPLETED")
        self.assertTrue(res["output"]["exists"])
        self.assertTrue(res["output"]["is_file"])
        self.assertTrue(len(res["evidence"]) > 0)

    def test_host_adapter_execute_escaped_path_fails(self):
        res = self.host_adapter.execute({
            "task_id": "TASK-H04",
            "action": "inspect_path",
            "inputs": ["../../../../etc/shadow"],
        })
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "PERMISSION_DENIED")

    def test_host_adapter_execute_command(self):
        res = self.host_adapter.execute({
            "task_id": "TASK-H05",
            "action": "run_command",
            "inputs": ["python3", "-c", "print('adapter_test_ok')"],
        })
        self.assertTrue(res["success"])
        self.assertIn("adapter_test_ok", res["output"]["stdout"])

    def test_host_adapter_health_check(self):
        health = self.host_adapter.health_check()
        self.assertEqual(health["status"], "HEALTHY")
        self.assertTrue(health["workspace_accessible"])

    def test_cantina_adapter_discovery(self):
        disc = self.cantina_adapter.discover()
        self.assertEqual(disc["adapter"], "cantina-bounty-adapter")
        self.assertTrue(disc["has_memory"])
        self.assertTrue(disc["has_instructions"])
        self.assertIn("cantina.bounties", disc["capabilities"])

    def test_cantina_adapter_rejects_live_funds_violation(self):
        bad_contract = {
            "task_id": "TASK-C01",
            "goal": "Send mainnet_tx with live_funds",
        }
        res = self.cantina_adapter.validate_contract(bad_contract)
        self.assertFalse(res["valid"])
        self.assertEqual(res["recommendation"], "REJECT_VIOLATION")

    def test_cantina_adapter_health_check(self):
        health = self.cantina_adapter.health_check()
        self.assertIn(health["status"], ("HEALTHY", "DEGRADED"))

    def test_host_adapter_path_containment_prefix_bypass_blocked(self):
        # A path sharing the prefix string like /home/nova/projects/cantina-evil must be rejected
        res = self.host_adapter.execute({
            "task_id": "TASK-H-TRAV",
            "action": "inspect_path",
            "inputs": ["../cantina-malicious/secret.txt"],
        })
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "PERMISSION_DENIED")

    def test_host_adapter_single_string_command_execution(self):
        res = self.host_adapter.execute({
            "task_id": "TASK-H-CMD",
            "action": "run_command",
            "inputs": "python3 -c \"print('split_cmd_ok')\"",
        })
        self.assertTrue(res["success"])
        self.assertIn("split_cmd_ok", res["output"]["stdout"])

    def test_cantina_adapter_execute_with_string_bounty_slug(self):
        res = self.cantina_adapter.execute({
            "task_id": "TASK-C-STR",
            "action": "verify_scope",
            "inputs": ["base"],
        })
        # Base bounty has scope.md; whether snapshot matches or not, execution proceeds
        self.assertTrue(res["success"])
        self.assertEqual(res["output"]["bounty"], "base")
        self.assertTrue("computed_sha256" in res["output"])

    def test_host_adapter_discovers_toolchain_and_compilers(self):
        disc = self.host_adapter.discover()
        tools = disc["tools"]
        for tool_name in ["solc", "node", "tsc", "cargo", "docker", "anvil", "forge", "cast", "anchor"]:
            self.assertIn(tool_name, tools)
        # Verify Foundry and Cargo toolchain discovery from standard user directories
        self.assertTrue(tools["forge"]["available"])
        self.assertTrue(tools["anvil"]["available"])
        self.assertTrue(tools["cargo"]["available"])


if __name__ == "__main__":
    unittest.main()
