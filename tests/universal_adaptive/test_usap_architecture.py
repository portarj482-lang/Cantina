"""Test suite for Universal Skill Adaptation Protocol (USAP) and Architecture Awareness."""
from __future__ import annotations
import os
import tempfile
import unittest
import yaml
from pathlib import Path

from universal_adaptive_engine.models.target_context import (
    TargetContext,
    TargetResultStatus,
    TargetFinding,
    TargetContextResolver,
)
from universal_adaptive_engine.adapters.discovery import TargetDiscoveryAdapter
from universal_adaptive_engine.adapters.evm_adapter import EVMArchitectureAdapter
from universal_adaptive_engine.adapters.solana_adapter import SolanaArchitectureAdapter


class TestUSAPArchitecture(unittest.TestCase):
    """Exhaustive tests covering USAP governance, schema validation, and architecture portability."""

    def setUp(self):
        self.workspace_root = Path("/home/nova/projects/cantina").resolve()
        self.skills_dir = self.workspace_root / ".agents" / "skills"

    def test_all_39_skills_inventory_and_schema(self):
        """Discover all skill manifests dynamically and validate required frontmatter."""
        skills = sorted(list(self.skills_dir.glob("*/SKILL.md")))
        self.assertGreaterEqual(len(skills), 39, f"Expected at least 39 skills, found {len(skills)}")

        for skill_path in skills:
            content = skill_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---"), f"Skill {skill_path.parent.name} missing frontmatter delimiter")
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"Malformed frontmatter in {skill_path.parent.name}")

            fm = yaml.safe_load(parts[1])
            self.assertIsInstance(fm, dict, f"Frontmatter not a dict in {skill_path.parent.name}")
            self.assertIn("name", fm, f"Missing 'name' in {skill_path.parent.name}")
            self.assertIn("description", fm, f"Missing 'description' in {skill_path.parent.name}")
            self.assertTrue(len(fm["name"].strip()) > 0)
            self.assertTrue(len(fm["description"].strip()) > 0)

    def test_path_coupling_analysis_group_a_and_b(self):
        """Verify that Group A (9 Oracles) and Group B (7 sub-surface) have no hardcoded bounties/base paths."""
        decoupled_skills = [
            "dispute-invariant-oracle",
            "dispute-prove-agent",
            "dispute-finalize-agent",
            "delayed-weth-invariant-oracle",
            "weth-unlock-agent",
            "weth-withdraw-agent",
            "multiproof-tee-invariant-oracle",
            "tee-register-agent",
            "tee-validity-agent",
            "attestation-timestamp-agent",
            "blacklist-maturity-agent",
            "delay-bypass-agent",
            "game-resolution-agent",
            "inverse-hint-integrity-agent",
            "signer-lifecycle-agent",
            "weth-solvency-agent",
        ]

        for s_name in decoupled_skills:
            skill_file = self.skills_dir / s_name / "SKILL.md"
            self.assertTrue(skill_file.exists(), f"Skill file {skill_file} missing")
            content = skill_file.read_text(encoding="utf-8")
            # Must not contain unparameterized hardcoded file paths
            self.assertNotIn(
                "`bounties/base/contracts/",
                content,
                f"Skill {s_name} contains hardcoded `bounties/base/contracts/` path",
            )
            # Must contain TargetContext reference or target resolution pattern
            self.assertIn(
                "TargetContext",
                content,
                f"Skill {s_name} must reference TargetContext for dynamic resolution",
            )

    def test_target_context_resolver_explicit_precedence(self):
        """Test that explicit context arguments take highest precedence over environment and memory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            target_a = tmp_path / "custom_target_a"
            target_a.mkdir()
            (target_a / "scope.md").write_text("# Target A Scope\n", encoding="utf-8")

            target_b = tmp_path / "custom_target_b"
            target_b.mkdir()

            # Set environment variable pointing to Target B
            os.environ["CANTINA_TARGET_ROOT"] = str(target_b)

            try:
                # Explicit context points to Target A
                tc = TargetContextResolver.resolve(
                    context={"target_root": str(target_a), "session_id": "session-test-01"},
                    workspace_root=tmp_path,
                )
                self.assertEqual(tc.target_root, target_a)
                self.assertEqual(tc.session_id, "session-test-01")
                self.assertIsNotNone(tc.scope_manifest)
                self.assertTrue(tc.is_valid)
            finally:
                os.environ.pop("CANTINA_TARGET_ROOT", None)

    def test_target_context_resolver_environment_precedence(self):
        """Test that environment variables take precedence over MEMORY.md."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bounties_dir = tmp_path / "bounties"
            bounties_dir.mkdir()

            target_env = bounties_dir / "target_from_env"
            target_env.mkdir()

            target_mem = bounties_dir / "target_from_mem"
            target_mem.mkdir()

            (tmp_path / "MEMORY.md").write_text("Active bounty: target_from_mem\n", encoding="utf-8")
            os.environ["CANTINA_BOUNTY"] = "target_from_env"

            try:
                tc = TargetContextResolver.resolve(context={}, workspace_root=tmp_path)
                self.assertEqual(tc.bounty_slug, "target_from_env")
                self.assertEqual(tc.target_root, target_env)
            finally:
                os.environ.pop("CANTINA_BOUNTY", None)

    def test_target_context_resolver_memory_fallback(self):
        """Test that MEMORY.md is consulted when no explicit or environment target is provided."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            bounties_dir = tmp_path / "bounties"
            bounties_dir.mkdir()

            target_mem = bounties_dir / "target_from_mem"
            target_mem.mkdir()

            (tmp_path / "MEMORY.md").write_text("Active bounty: target_from_mem\n", encoding="utf-8")
            tc = TargetContextResolver.resolve(context={}, workspace_root=tmp_path)
            self.assertEqual(tc.bounty_slug, "target_from_mem")
            self.assertEqual(tc.target_root, target_mem)

    def test_cross_architecture_evm_discovery(self):
        """Test EVM / Foundry manifest discovery and capability mapping."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "foundry.toml").write_text("[profile.default]\nsrc = 'src'\n", encoding="utf-8")
            (tmp_path / "src").mkdir()
            (tmp_path / "test").mkdir()

            tc = TargetContextResolver.resolve(context={"target_root": str(tmp_path)})
            self.assertEqual(tc.architecture, "evm")
            self.assertIn("solidity", tc.languages)
            self.assertIn("foundry", tc.runtimes)
            self.assertTrue(tc.has_capability("evm.foundry"))
            self.assertTrue(tc.has_capability("tests.forge"))

            adapter = EVMArchitectureAdapter(tc)
            disc = adapter.discover()
            self.assertTrue(disc["has_foundry"])
            self.assertIn("evm.forge.fuzz", disc["capabilities"])

    def test_cross_architecture_solana_discovery(self):
        """Test Solana / Anchor manifest discovery and capability mapping."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "Anchor.toml").write_text("[programs.localnet]\nmy_prog = '11111111111111111111111111111111'\n", encoding="utf-8")
            (tmp_path / "Cargo.toml").write_text("[workspace]\nmembers = ['programs/*']\n", encoding="utf-8")
            (tmp_path / "programs").mkdir()
            (tmp_path / "tests").mkdir()

            tc = TargetContextResolver.resolve(context={"target_root": str(tmp_path)})
            self.assertEqual(tc.architecture, "solana")
            self.assertIn("rust", tc.languages)
            self.assertIn("anchor", tc.runtimes)
            self.assertTrue(tc.has_capability("solana.anchor"))

            adapter = SolanaArchitectureAdapter(tc)
            disc = adapter.discover()
            self.assertTrue(disc["has_anchor"])
            self.assertIn("solana.signers", disc["capabilities"])

    def test_heterogeneous_nonstandard_directory_layout(self):
        """Test discovery of a target with non-standard layout (no bounties/<slug> structure)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            standalone_target = tmp_path / "standalone_defi_core"
            standalone_target.mkdir()
            (standalone_target / "crates").mkdir()
            (standalone_target / "Cargo.toml").write_text("[package]\nname = 'defi-core'\n", encoding="utf-8")
            (standalone_target / "scope.md").write_text("# Core Scope\n", encoding="utf-8")

            adapter = TargetDiscoveryAdapter(workspace_root=tmp_path, target_root=standalone_target)
            disc = adapter.discover()
            tc = disc["target_context"]

            self.assertTrue(tc.is_valid)
            self.assertEqual(tc.architecture, "rust")
            self.assertEqual(tc.target_root, standalone_target)
            self.assertIn(standalone_target / "crates", tc.source_roots)
            self.assertIsNotNone(tc.scope_manifest)

    def test_session_isolation_concurrent_targets(self):
        """Test that two concurrent sessions maintain independent target contexts without cross-contamination."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_a = tmp_path / "repo_a"
            repo_b = tmp_path / "repo_b"
            repo_a.mkdir()
            repo_b.mkdir()

            session_a_id = "session-alpha-123"
            session_b_id = "session-beta-456"

            tc_a = TargetContextResolver.resolve(
                context={"target_root": str(repo_a), "session_id": session_a_id},
                workspace_root=tmp_path,
            )
            tc_b = TargetContextResolver.resolve(
                context={"target_root": str(repo_b), "session_id": session_b_id},
                workspace_root=tmp_path,
            )

            self.assertNotEqual(tc_a.session_id, tc_b.session_id)
            self.assertNotEqual(tc_a.target_root, tc_b.target_root)
            self.assertEqual(tc_a.target_id, "repo_a")
            self.assertEqual(tc_b.target_id, "repo_b")

    def test_result_taxonomy_and_finding_record(self):
        """Test the 5-state result taxonomy and structured evidence finding."""
        statuses = [
            TargetResultStatus.PASS,
            TargetResultStatus.FAIL,
            TargetResultStatus.BLOCKED,
            TargetResultStatus.NOT_APPLICABLE,
            TargetResultStatus.NOT_VERIFIED,
        ]
        self.assertEqual(len(statuses), 5)

        finding = TargetFinding(
            finding_id="FINDING-USAP-001",
            target_id="target-test",
            architecture="evm",
            property_violated="INV-DISPUTE-01",
            affected_artifact="OptimismPortal2.sol:finalizeWithdrawalTransaction",
            status=TargetResultStatus.FAIL,
            summary="Early finalization allowed under simulated time-travel",
            evidence_refs=("EVID-CHALLENGE-001",),
        )
        self.assertEqual(finding.status, TargetResultStatus.FAIL)
        self.assertEqual(finding.property_violated, "INV-DISPUTE-01")


if __name__ == "__main__":
    unittest.main()
