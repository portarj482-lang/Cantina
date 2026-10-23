"""
Pytest suite for Echidna Dynamic Fuzzing Meta-Agent Orchestrator & Glassbox Verification Plane.
Tests canonical contracts, schema validation, path containment, dry-run zero-mutation,
falsified property parsing with counterexamples, gate adjudicator decisions, and simulation modes.
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

from echidna_contracts import (
    AuditEvent,
    CampaignManifest,
    EvidenceEnvelope,
    FindingContract,
    GateDecisionContract,
    StageResult,
    TaskContract,
    load_schema,
)
from echidna_orchestrator import (
    EchidnaGlassboxOrchestrator,
    EchidnaGovernanceAdjudicator,
    EchidnaIndependentChallenger,
    STATUS_BLOCKED,
    STATUS_COMPLETED_VERIFIED,
    STATUS_COMPLETED_WITH_FINDINGS,
    STATUS_DRY_RUN_COMPLETE,
    STATUS_EXECUTION_FAILED,
    STATUS_PREFLIGHT_PASSED,
    STATUS_TIMED_OUT,
)


@pytest.fixture
def fuzz_env(tmp_path: Path):
    repo_root = tmp_path / "cantina"
    repo_root.mkdir()
    bounty_dir = repo_root / "bounties" / "test_slug"
    contracts_dir = bounty_dir / "contracts"
    contracts_dir.mkdir(parents=True)
    scans_dir = bounty_dir / "scans" / "echidna"
    scans_dir.mkdir(parents=True)

    # Copy or create minimal contract harness
    harness_src = (
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract VaultFuzzTest {\n"
        "    uint256 public assets = 100;\n"
        "    function echidna_test_solvency() public view returns (bool) {\n"
        "        return assets > 0;\n"
        "    }\n"
        "}\n"
    )
    (contracts_dir / "VaultFuzzTest.sol").write_text(harness_src, encoding="utf-8")

    return {
        "repo_root": repo_root,
        "bounty_dir": bounty_dir,
        "contracts_dir": contracts_dir,
        "scans_dir": scans_dir,
    }


def test_task_contract_validation():
    task = TaskContract(
        task_id="TASK-001",
        goal="Run property fuzzing",
        status="PLANNED",
        owner="FuzzingEngineer",
        dependencies=[],
        inputs={"target": "bounties/test"},
        permissions_required=["READ_TARGET"],
        acceptance_criteria=["All properties pass"],
        expected_artifacts=["manifest.json"],
        attempt_count=1,
        evidence_refs=["ref:1"],
        blocker=None,
        tests=["fuzz_test"],
        limitations=["bounded"],
        next_action="execute",
    )
    task.validate()
    d = task.to_dict()
    assert d["task_id"] == "TASK-001"
    assert d["schema_version"] == "2.0.0"


def test_finding_contract_validation():
    finding = FindingContract(
        finding_id="ECHIDNA-12345678",
        title="Invariant Violation: echidna_test_solvency",
        status="VERIFIED",
        source_refs=["prop:echidna_test_solvency"],
        affected_versions=["1.0.0"],
        locations=[{
            "path": "bounties/test/contracts/Vault.sol",
            "contract": "Vault",
            "function": "echidna_test_solvency",
            "start_line": 10,
            "end_line": 12,
        }],
        security_property="Vault must remain solvent",
        preconditions=["Deposit executed"],
        root_cause="Borrow exceeds assets without collateral check",
        impact="HIGH",
        exploitability="PROVEN",
        reproduction_refs=["trace:001"],
        counterevidence_refs=[],
        fix_refs=[],
        regression_results=[],
        confidence="CERTAIN",
        unresolved_assumptions=[],
    )
    finding.validate()
    d = finding.to_dict()
    assert d["finding_id"] == "ECHIDNA-12345678"
    assert d["impact"] == "HIGH"


def test_campaign_manifest_validation():
    manifest = CampaignManifest(
        run_id="RUN-001",
        repository_revision="abc1234",
        target="bounties/test/contracts",
        echidna_version="Echidna 2.3.3",
        compiler_version="0.8.20",
        configuration_digest="hash123",
        binary_digest="bin123",
        seed=42,
        resource_limits={"timeout_seconds": 60, "test_limit": 1000},
        start_time="2026-10-23T00:00:00Z",
        end_time="2026-10-23T00:01:00Z",
        process_exit_status=0,
        campaign_outcome="COMPLETED_VERIFIED",
        property_results=[{
            "property_name": "echidna_test_solvency",
            "status": "passed",
            "counterexample": None,
            "calls_count": 500,
            "error_message": None,
        }],
        artifact_refs=["stdout.log"],
        verification_status="COMPLETED_VERIFIED",
        limitations=["bounded"],
    )
    manifest.validate()
    d = manifest.to_dict()
    assert d["run_id"] == "RUN-001"
    assert d["seed"] == 42


def test_evidence_envelope_validation():
    envelope = EvidenceEnvelope(
        envelope_id="ENV-001",
        slug="test_slug",
        run_id="RUN-001",
        status="COMPLETED_VERIFIED",
        evidence_type="ECHIDNA_PROPERTY_FUZZING",
        manifest={"run_id": "RUN-001"},
        digests={"payload_sha256": "aabbcc"},
        provenance={"git_commit": "abc", "echidna_version": "2.3.3"},
        timestamp="2026-10-23T00:00:00Z",
    )
    envelope.validate()
    d = envelope.to_dict()
    assert d["envelope_id"] == "ENV-001"


def test_gate_decision_contract_validation():
    gate = GateDecisionContract(
        gate_id="GATE-001",
        gate_name="AuthorizationGate",
        required_checks=["confirm_authorized"],
        passed_checks=["confirm_authorized"],
        failed_checks=[],
        decision="PASS",
        rationale="Authorized via --confirm",
        proposer="Orchestrator",
        evaluator="Auditor",
        audit_reference="audit:001",
        timestamp="2026-10-23T00:00:00Z",
    )
    gate.validate()
    d = gate.to_dict()
    assert d["decision"] == "PASS"


def test_slug_validation_rejects_traversal(fuzz_env):
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="../escape",
        target=str(fuzz_env["contracts_dir"]),
    )
    code = orchestrator.execute()
    assert code == 2


def test_target_escape_blocked(fuzz_env, tmp_path):
    alien_dir = tmp_path / "alien_workspace"
    alien_dir.mkdir()
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(alien_dir),
    )
    code = orchestrator.execute()
    assert code == 2


def test_output_inside_target_blocked(fuzz_env):
    inside_dir = fuzz_env["contracts_dir"] / "scans"
    inside_dir.mkdir()
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(inside_dir),
    )
    code = orchestrator.execute()
    assert code == 2


def test_dry_run_zero_mutation(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "dry_run_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        dry_run=True,
        confirm=True,  # dry-run must override confirm
    )
    code = orchestrator.execute()
    assert code == 0
    assert not out_dir.exists(), "Dry-run must not create output directory or files"


def test_unconfirmed_zero_mutation(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "unconfirmed_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        dry_run=False,
        confirm=False,
    )
    code = orchestrator.execute()
    assert code == 0
    assert not out_dir.exists(), "Unconfirmed run must not create output directory or files"


def test_clean_campaign_sim_verified(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "clean_sim_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        confirm=True,
        clean_sim=True,
    )
    code = orchestrator.execute()
    assert code == 0
    assert (out_dir / "campaign_manifest.json").is_file()
    assert (out_dir / "receipt.json").is_file()
    assert (out_dir / "envelope.json").is_file()

    manifest_data = json.loads((out_dir / "campaign_manifest.json").read_text())
    assert manifest_data["campaign_outcome"] == "COMPLETED_VERIFIED"
    assert manifest_data["verification_status"] == "COMPLETED_VERIFIED"
    assert len(manifest_data["property_results"]) == 2
    assert all(p["status"] == "passed" for p in manifest_data["property_results"])


def test_falsify_campaign_sim_extracts_counterexamples(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "falsify_sim_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        confirm=True,
        falsify_sim=True,
    )
    code = orchestrator.execute()
    assert code == 0
    assert (out_dir / "findings.json").is_file()

    findings_data = json.loads((out_dir / "findings.json").read_text())
    assert len(findings_data) == 1
    finding = findings_data[0]
    assert finding["status"] == "VERIFIED"
    assert finding["exploitability"] == "PROVEN"
    assert "echidna_test_solvency" in finding["title"]

    manifest_data = json.loads((out_dir / "campaign_manifest.json").read_text())
    assert manifest_data["campaign_outcome"] == "COMPLETED_WITH_FINDINGS"
    falsified_p = [p for p in manifest_data["property_results"] if p["status"] == "falsified"]
    assert len(falsified_p) == 1
    assert falsified_p[0]["counterexample"] is not None
    assert len(falsified_p[0]["counterexample"]) == 3  # 3 transaction steps in simulated counterexample


def test_fail_sim_propagates_execution_failed(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "fail_sim_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        confirm=True,
        fail_sim=True,
    )
    code = orchestrator.execute()
    assert code == 1  # Fails gate because outcome is EXECUTION_FAILED
    manifest_data = json.loads((out_dir / "campaign_manifest.json").read_text())
    assert manifest_data["campaign_outcome"] == "EXECUTION_FAILED"
    assert manifest_data["verification_status"] == "FAILED"


def test_timeout_sim_propagates_timeout(fuzz_env):
    out_dir = fuzz_env["scans_dir"] / "timeout_sim_test"
    orchestrator = EchidnaGlassboxOrchestrator(
        repo_root=fuzz_env["repo_root"],
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(out_dir),
        confirm=True,
        timeout_sim=True,
    )
    code = orchestrator.execute()
    assert code == 1
    manifest_data = json.loads((out_dir / "campaign_manifest.json").read_text())
    assert manifest_data["campaign_outcome"] == "TIMED_OUT"
    assert manifest_data["verification_status"] == "FAILED"


def test_governance_gate_adjudicator_fail_closed():
    adjudicator = EchidnaGovernanceAdjudicator("TEST-RUN")
    # Authorization gate
    gate = adjudicator.evaluate_authorization_gate(dry_run=True, confirm=True)
    assert gate.decision == "BLOCKED"

    gate = adjudicator.evaluate_authorization_gate(dry_run=False, confirm=False)
    assert gate.decision == "FAIL"

    gate = adjudicator.evaluate_authorization_gate(dry_run=False, confirm=True)
    assert gate.decision == "PASS"

    # Outcome gate
    gate = adjudicator.evaluate_campaign_outcome_gate("EXECUTION_FAILED", 1, [])
    assert gate.decision == "FAIL"
