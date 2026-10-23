"""
Pytest suite for Slither Refractor Mesh Orchestrator & Glassbox Evidence Plane.
Tests canonical contracts, path containment, state machine transitions,
independent challenger logic, gate decision evaluation, and standard evidence envelope compliance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import jsonschema
import pytest

WORKFLOW_DIR = Path(__file__).resolve().parents[1]
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from mesh_contracts import (
    EvidenceContract,
    FindingContract,
    GateDecisionContract,
    StageResult,
    TaskContract,
    ToolContract,
    load_schema,
)
from slither_orchestrator import (
    GovernanceGateAdjudicator,
    SlitherIndependentChallenger,
    SlitherRefractorMeshOrchestrator,
    STATUS_BLOCKED,
    STATUS_COMPLETED_CLEAN,
    STATUS_COMPLETED_WITH_FINDINGS,
    STATUS_DRY_RUN_COMPLETE,
    STATUS_EXECUTION_FAILED,
    STATUS_VALIDATION_FAILED,
    compute_sha256,
)


@pytest.fixture
def mesh_env(tmp_path: Path):
    repo_root = tmp_path / "cantina"
    repo_root.mkdir()
    bounty_dir = repo_root / "bounties" / "test_slug"
    contracts_dir = bounty_dir / "contracts" / "src"
    contracts_dir.mkdir(parents=True)
    scans_dir = bounty_dir / "scans" / "slither"
    scans_dir.mkdir(parents=True)

    # Minimal contract
    (contracts_dir / "Vault.sol").write_text(
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract Vault {\n"
        "    mapping(address => uint256) public balances;\n"
        "    function withdraw() external {\n"
        "        uint256 bal = balances[msg.sender];\n"
        "        (bool s, ) = msg.sender.call{value: bal}('');\n"
        "        require(s);\n"
        "        balances[msg.sender] = 0;\n"
        "    }\n"
        "}\n"
    )

    # Tooling registry
    global_dir = repo_root / "global"
    global_dir.mkdir(parents=True)
    tooling_md = global_dir / "tooling.md"
    tooling_md.write_text(
        "| Tool | Use | Install | Version check | Status (2026-10-23) | Version | Command | Notes |\n"
        "| slither | Static analysis | pip | slither --version | OK | 0.11.6 | slither . --sarif report.sarif | OK |\n"
    )

    schema_path = WORKFLOW_DIR / "schemas" / "evidence_envelope.schema.json"
    schema_data = json.loads(schema_path.read_text())
    real_adapter = WORKFLOW_DIR.parents[1] / ".agents" / "skills" / "qrpe" / "adapters" / "slither_adapter.py"

    return {
        "repo_root": repo_root,
        "bounty_dir": bounty_dir,
        "contracts_dir": bounty_dir / "contracts",
        "scans_dir": scans_dir,
        "slug": "test_slug",
        "adapter_path": real_adapter,
        "schema": schema_data,
    }


def test_task_contract_validation():
    tc = TaskContract(
        schema_version="1.0",
        task_id="task-test-01",
        objective="Execute Slither scan on base",
        target_scope={
            "slug": "base",
            "repository_root": "/repo",
            "target_path": "bounties/base/contracts",
            "output_dir": "bounties/base/scans/slither",
        },
        prerequisites=["slither", "foundry"],
        permissions={
            "execution_mode": "DRY_RUN",
            "write_allowed": False,
            "allow_network": False,
            "allow_subprocesses": True,
        },
        budget={"timeout_seconds": 300},
        acceptance_criteria=["Zero writes in dry run", "Schema conformance"],
        status="READY",
    )
    tc.validate()


def test_tool_contract_validation():
    tool = ToolContract(
        schema_version="1.0",
        tool_id="slither",
        name="Slither Static Analyzer",
        version="0.11.6",
        description="Static analysis engine for Solidity",
        capabilities=["reentrancy", "dataflow"],
        effects={"writes_filesystem": False, "network_access": False, "subprocesses": True, "idempotent": True},
        restrictions={"timeout_seconds": 300, "sandbox_level": "CONTAINED_WORKSPACE"},
        verification_status="VERIFIED",
    )
    tool.validate()


def test_evidence_contract_validation():
    ev = EvidenceContract(
        schema_version="1.0",
        evidence_id="ev-sarif-01",
        evidence_type="SARIF_REPORT",
        source="bounties/base/scans/slither/slither.sarif",
        revision="b1c19f8",
        digest={"algorithm": "sha256", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        acquisition_method="slither_static_analysis",
        timestamp="2026-10-23T12:00:00Z",
        provenance={"tool": "slither", "tool_version": "0.11.6", "run_id": "run-001"},
        state="OBSERVED",
    )
    ev.validate()


def test_finding_contract_validation():
    fc = FindingContract(
        schema_version="1.0",
        finding_id="finding-001",
        source_revision="b1c19f8",
        detector={"name": "slither", "rule_id": "0-1-reentrancy-eth", "tool_version": "0.11.6"},
        classification="candidate",
        verification="unverified",
        evidence_refs=["ev-sarif-01"],
        counterevidence_refs=[],
        limitations=[],
    )
    fc.validate()


def test_gate_decision_contract_validation():
    gd = GateDecisionContract(
        schema_version="1.0",
        gate_id="gate-01-policy",
        gate_name="POLICY_GATE",
        required_checks=["slug_valid", "target_contained"],
        passed_checks=["slug_valid", "target_contained"],
        failed_checks=[],
        decision="ACCEPTED",
        rationale="All policy checks passed",
        proposer="ORCHESTRATOR",
        evaluator="INDEPENDENT_GOVERNANCE_GATE",
        audit_reference="run-001",
        timestamp="2026-10-23T12:00:00Z",
    )
    gd.validate()


def test_invalid_slug_traversal_blocked(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug="../escape",
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_target_escape_blocked(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=Path("/etc"),
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_output_inside_target_blocked(mesh_env):
    # Output inside target violates least-privilege output isolation
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["contracts_dir"] / "scans",
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_dry_run_zero_mutation(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=True,
        confirm=True,  # dry-run must strictly override confirm
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 0
    assert orch.terminal_status == STATUS_DRY_RUN_COMPLETE
    # Zero files must be created
    assert list(mesh_env["scans_dir"].glob("*")) == []


def test_schema_valid_evidence_envelope_clean(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 0
    assert orch.terminal_status == STATUS_COMPLETED_CLEAN

    envelope_file = mesh_env["scans_dir"] / "evidence_envelope.json"
    assert envelope_file.exists()
    envelope_data = json.loads(envelope_file.read_text())

    # Validate against formal schema
    jsonschema.validate(instance=envelope_data, schema=mesh_env["schema"])
    assert envelope_data["terminal_status"] == STATUS_COMPLETED_CLEAN
    assert envelope_data["findings_summary"]["total_findings"] == 0
    assert envelope_data["validation_results"]["digest_verified"] is True
    assert "mesh_evidence" in envelope_data
    assert len(envelope_data["mesh_evidence"]["stage_results"]) > 0


def test_corrupt_report_causes_validation_failure(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        corrupt_report_sim=True,
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_VALIDATION_FAILED


def test_digest_mismatch_causes_validation_failure(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        digest_mismatch_sim=True,
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_VALIDATION_FAILED


def test_scanner_failure_propagates_execution_failed(mesh_env):
    orch = SlitherRefractorMeshOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=False,
        confirm=True,
        scanner_fail_sim=True,
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_EXECUTION_FAILED


def test_independent_challenger_verifies_reentrancy(mesh_env):
    challenger = SlitherIndependentChallenger(mesh_env["contracts_dir"], mesh_env["repo_root"])
    finding = {
        "rule_id": "0-1-reentrancy-eth",
        "detector_name": "reentrancy-eth",
        "title": "Reentrancy vulnerabilities",
        "description": "Reentrancy in withdraw()",
        "location": {
            "path": "src/Vault.sol",
            "start_line": 5,
            "end_line": 11,
        },
        "severity": {"scanner_severity": "warning", "assessed_severity": "HIGH"},
        "tool_version": "0.11.6",
    }
    contract = challenger.challenge_finding(finding, "HEAD")
    assert contract.classification == "independently_verified"
    assert contract.verification == "verified"
    assert len(contract.evidence_refs) > 0


def test_independent_challenger_falsifies_guarded_reentrancy(mesh_env):
    # Create guarded contract
    guarded_sol = mesh_env["contracts_dir"] / "GuardedVault.sol"
    guarded_sol.write_text(
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract GuardedVault {\n"
        "    bool locked;\n"
        "    modifier nonReentrant() { require(!locked); locked = true; _; locked = false; }\n"
        "    function withdraw() external nonReentrant {\n"
        "        (bool s, ) = msg.sender.call{value: 10}('');\n"
        "        require(s);\n"
        "    }\n"
        "}\n"
    )
    challenger = SlitherIndependentChallenger(mesh_env["contracts_dir"], mesh_env["repo_root"])
    finding = {
        "rule_id": "0-1-reentrancy-eth",
        "detector_name": "reentrancy-eth",
        "title": "Reentrancy vulnerabilities",
        "description": "Reentrancy in withdraw()",
        "location": {
            "path": "GuardedVault.sol",
            "start_line": 6,
            "end_line": 9,
        },
        "severity": {"scanner_severity": "warning", "assessed_severity": "HIGH"},
        "tool_version": "0.11.6",
    }
    contract = challenger.challenge_finding(finding, "HEAD")
    # Must flag that contract is protected by reentrancy guard
    assert contract.verification == "unverified"
    assert len(contract.counterevidence_refs) > 0
    assert "reentrancy guard" in contract.limitations[0].lower()


def test_governance_gate_blocks_on_check_failure():
    adj = GovernanceGateAdjudicator()
    decision = adj.evaluate_gate(
        gate_id="gate-test",
        gate_name="TEST_GATE",
        required_checks=["check_a", "check_b"],
        check_results={"check_a": True, "check_b": False},
        proposer="PROPOSER_ROLE",
        audit_reference="audit-123",
    )
    assert decision.decision == "BLOCKED"
    assert "check_b" in decision.failed_checks
    assert decision.proposer != decision.evaluator
