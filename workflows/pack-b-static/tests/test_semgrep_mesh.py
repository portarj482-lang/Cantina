"""
Pytest suite for Semgrep Governed Agentic Mesh Orchestrator & Glassbox Mirror Plane.
Tests canonical contracts, path containment, state machine transitions,
specialist agents, independent finding verification, coverage reconciliation,
gate decisions G1-G8, and standard evidence envelope compliance.
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
    MeshTaskEnvelope,
    StageResult,
    TaskContract,
    ToolContract,
    load_schema,
)
from semgrep_orchestrator import (
    CoverageReconciliationAgent,
    FindingVerificationAgent,
    GovernanceGateAdjudicator,
    ScopeRepositoryAgent,
    SemgrepConfigAgent,
    SemgrepMetaAgentOrchestrator,
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
    scans_dir = bounty_dir / "scans" / "semgrep"
    scans_dir.mkdir(parents=True)

    # Minimal contract source
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
        "}\n",
        encoding="utf-8",
    )

    # Contract with inline nosec comment
    (contracts_dir / "IgnoredVault.sol").write_text(
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract IgnoredVault {\n"
        "    function doCall(address target) external {\n"
        "        // nosec\n"
        "        (bool s, ) = target.call('');\n"
        "        require(s);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    # Tooling registry
    global_dir = repo_root / "global"
    global_dir.mkdir(parents=True)
    tooling_md = global_dir / "tooling.md"
    tooling_md.write_text(
        "| Tool | Use | Install | Version check | Status (2026-10-23) | Version | Command | Notes |\n"
        "| semgrep | Static analysis | pip | semgrep --version | OK | 1.182.1 | semgrep scan --json -o report.json | OK |\n",
        encoding="utf-8",
    )

    schema_path = WORKFLOW_DIR / "schemas" / "evidence_envelope.schema.json"
    schema_data = json.loads(schema_path.read_text(encoding="utf-8"))
    real_adapter = WORKFLOW_DIR.parents[1] / ".agents" / "skills" / "qrpe" / "adapters" / "semgrep_adapter.py"

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
        task_id="task-test-semgrep-01",
        objective="Execute Semgrep scan on base",
        target_scope={
            "slug": "base",
            "repository_root": "/repo",
            "target_path": "bounties/base/contracts",
            "output_dir": "bounties/base/scans/semgrep",
        },
        prerequisites=["semgrep"],
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
        tool_id="semgrep",
        name="Semgrep Static Analysis",
        version="1.182.1",
        description="Lightweight static analysis and pattern-matching engine",
        capabilities=["static_analysis", "pattern_matching"],
        effects={"writes_filesystem": False, "network_access": False, "subprocesses": True, "idempotent": True},
        restrictions={"timeout_seconds": 300, "sandbox_level": "CONTAINED_WORKSPACE"},
        verification_status="VERIFIED",
    )
    tool.validate()


def test_evidence_contract_validation():
    ev = EvidenceContract(
        schema_version="1.0",
        evidence_id="ev-semgrep-01",
        evidence_type="STATIC_ANALYSIS_SCAN",
        source="bounties/base/scans/semgrep/semgrep.json",
        revision="b1c19f8",
        digest={"algorithm": "sha256", "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        acquisition_method="semgrep_static_analysis",
        timestamp="2026-10-23T12:00:00Z",
        provenance={"tool": "semgrep", "tool_version": "1.182.1", "run_id": "run-001"},
        state="OBSERVED",
    )
    ev.validate()


def test_finding_contract_validation():
    fc = FindingContract(
        schema_version="1.0",
        finding_id="finding-001",
        source_revision="b1c19f8",
        detector={"name": "semgrep", "rule_id": "solidity.security.reentrancy", "tool_version": "1.182.1"},
        classification="candidate",
        verification="unverified",
        evidence_refs=["ev-semgrep-01"],
        counterevidence_refs=[],
        limitations=[],
    )
    fc.validate()


def test_gate_decision_contract_validation():
    gd = GateDecisionContract(
        schema_version="1.0",
        gate_id="G1",
        gate_name="AUTHORIZATION_GATE",
        required_checks=["policy_permitted_scope", "authorization_mode_valid"],
        passed_checks=["policy_permitted_scope", "authorization_mode_valid"],
        failed_checks=[],
        decision="ACCEPTED",
        rationale="All authorization checks passed",
        proposer="SCOPE_REPOSITORY_AGENT",
        evaluator="INDEPENDENT_GOVERNANCE_GATE",
        audit_reference="run-001",
        timestamp="2026-10-23T12:00:00Z",
    )
    gd.validate()


def test_mesh_task_envelope_validation():
    mte = MeshTaskEnvelope(
        schema_version="1.0.0",
        task_id="scope-inspect-001",
        run_id="run-001",
        agent_id="scope-agent",
        capability="repository.scope.inspect",
        state="COMPLETED",
        scope={
            "repository_revision": "abc1234",
            "target": "bounties/base",
            "slug": "base",
        },
        inputs=[{"artifact_id": "scope-request", "digest": "sha256:000"}],
        outputs=[{"artifact_id": "inputs.inventory.json", "digest": "sha256:111", "media_type": "application/json"}],
        claims=[{
            "claim": "Target is within the authorized repository boundary",
            "evidence_refs": ["inputs.inventory.json"],
            "status": "SUPPORTED",
        }],
        limitations=[],
    )
    mte.validate()


def test_invalid_slug_traversal_blocked(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug="../escape",
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_target_escape_blocked(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=Path("/etc"),
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_output_inside_target_blocked(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
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
    orch = SemgrepMetaAgentOrchestrator(
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
    # Zero files must be created in output directory
    assert list(mesh_env["scans_dir"].glob("*")) == []


def test_schema_valid_evidence_envelope_clean(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
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
    envelope_data = json.loads(envelope_file.read_text(encoding="utf-8"))

    # Validate against formal schema
    jsonschema.validate(instance=envelope_data, schema=mesh_env["schema"])
    assert envelope_data["terminal_status"] == STATUS_COMPLETED_CLEAN
    assert envelope_data["findings_summary"]["total_findings"] == 0
    assert envelope_data["validation_results"]["digest_verified"] is True

    # Validate Glassbox run directory layout
    runs = list((mesh_env["scans_dir"] / "runs").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]
    assert (run_dir / "request.normalized.json").exists()
    assert (run_dir / "inputs.inventory.json").exists()
    assert (run_dir / "execution.plan.json").exists()
    assert (run_dir / "provenance.manifest.json").exists()
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "raw" / "semgrep.json").exists()
    assert (run_dir / "raw" / "receipt.json").exists()
    assert (run_dir / "validation" / "coverage-report.json").exists()
    assert (run_dir / "governance" / "admission.decision.json").exists()


def test_corrupt_report_causes_validation_failure(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
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
    orch = SemgrepMetaAgentOrchestrator(
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
    orch = SemgrepMetaAgentOrchestrator(
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


def test_timeout_propagates_execution_failed(mesh_env):
    orch = SemgrepMetaAgentOrchestrator(
        repo_root=mesh_env["repo_root"],
        slug=mesh_env["slug"],
        target_dir=mesh_env["contracts_dir"],
        output_dir=mesh_env["scans_dir"],
        dry_run=False,
        confirm=True,
        timeout_sim=True,
        adapter_path=mesh_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_EXECUTION_FAILED


def test_finding_verification_agent_detects_ignore_comments(mesh_env):
    agent = FindingVerificationAgent(mesh_env["contracts_dir"])
    raw_results = [
        {
            "check_id": "solidity.call.low-level-call",
            "path": "src/IgnoredVault.sol",
            "start": {"line": 6},
            "end": {"line": 6},
            "extra": {"message": "Low level call", "severity": "WARNING"},
        },
        {
            "check_id": "solidity.call.low-level-call",
            "path": "src/Vault.sol",
            "start": {"line": 8},
            "end": {"line": 8},
            "extra": {"message": "Low level call", "severity": "WARNING"},
        },
    ]
    contracts, counts, env = agent.verify_findings(raw_results, "run-test", "rev-test", "1.182.1")
    assert len(contracts) == 2
    # First contract has inline // nosec -> rejected / refuted
    assert contracts[0].classification == "rejected"
    assert contracts[0].verification == "refuted"
    assert len(contracts[0].counterevidence_refs) > 0

    # Second contract has no inline comment -> independently_verified / verified
    assert contracts[1].classification == "independently_verified"
    assert contracts[1].verification == "verified"


def test_coverage_reconciliation_agent(mesh_env):
    inventory_files = ["src/Vault.sol", "src/IgnoredVault.sol", "src/Extra.sol"]
    agent = CoverageReconciliationAgent(mesh_env["contracts_dir"], inventory_files)
    semgrep_data = {
        "paths": {
            "scanned": [
                str(mesh_env["contracts_dir"] / "src" / "Vault.sol"),
                str(mesh_env["contracts_dir"] / "src" / "IgnoredVault.sol"),
            ]
        }
    }
    report, env = agent.reconcile_coverage(semgrep_data, "run-test", "rev-test")
    assert report["total_target_files"] == 3
    assert report["target_files_covered"] == 2
    assert report["target_files_missing"] == 1
    assert "src/Extra.sol" in report["discrepancies"][0]
    assert report["coverage_ratio"] == pytest.approx(2 / 3)


def test_governance_gate_adjudicator_fail_closed():
    adjudicator = GovernanceGateAdjudicator()
    decision = adjudicator.evaluate_gate(
        gate_id="G1",
        gate_name="AUTHORIZATION_GATE",
        required_checks=["check_a", "check_b"],
        check_results={"check_a": True, "check_b": False},
        proposer="AGENT_TEST",
        audit_reference="run-001",
    )
    assert decision.decision == "BLOCKED"
    assert "check_b" in decision.failed_checks
    assert decision.evaluator == "INDEPENDENT_GOVERNANCE_GATE"
