"""
Pytest suite for Medusa Dynamic Property Fuzzing Meta-Agent Orchestrator & Glassbox Verification Plane.
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

from medusa_contracts import (
    AuditEvent,
    CampaignManifest,
    EvidenceEnvelope,
    FindingContract,
    GateDecisionContract,
    StageResult,
    TaskContract,
    load_schema,
)
from medusa_orchestrator import (
    MedusaGlassboxOrchestrator,
    MedusaGovernanceAdjudicator,
    MedusaIndependentChallenger,
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
    scans_dir = bounty_dir / "scans" / "medusa"
    scans_dir.mkdir(parents=True)

    # Minimal Solidity contract harness
    harness_src = (
        "// SPDX-License-Identifier: MIT\n"
        "pragma solidity ^0.8.20;\n"
        "contract VaultFuzzTest {\n"
        "    uint256 public assets = 100;\n"
        "    function property_solvency() public view returns (bool) {\n"
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
        task_id="TASK-MEDUSA-001",
        goal="Run Medusa property fuzzing",
        status="PLANNED",
        owner="MedusaFuzzingEngineer",
        dependencies=[],
        inputs={"target": "bounties/test"},
        permissions_required=["READ_TARGET"],
        acceptance_criteria=["All properties pass"],
        expected_artifacts=["manifest.json"],
        attempt_count=1,
        evidence_refs=["ref:1"],
        blocker=None,
        tests=["medusa_property_fuzzing"],
        limitations=["bounded"],
        next_action="execute",
    )
    task.validate()
    d = task.to_dict()
    assert d["task_id"] == "TASK-MEDUSA-001"
    assert d["schema_version"] == "2.0.0"


def test_finding_contract_validation():
    finding = FindingContract(
        finding_id="MEDUSA-12345678",
        title="Invariant Violation: property_solvency",
        status="VERIFIED",
        source_refs=["prop:property_solvency"],
        affected_versions=["1.0.0"],
        locations=[{
            "path": "bounties/test/contracts/Vault.sol",
            "contract": "Vault",
            "function": "property_solvency",
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
    assert d["finding_id"] == "MEDUSA-12345678"
    assert d["confidence"] == "CERTAIN"


def test_manifest_schema_validation():
    manifest = CampaignManifest(
        run_id="MEDUSA-20261023T000000Z-100",
        repository_revision="0123456789abcdef0123456789abcdef01234567",
        target="bounties/test/contracts",
        medusa_version="1.5.1",
        compiler_version="0.8.20",
        configuration_digest="none",
        binary_digest="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        seed=1337,
        resource_limits={"timeout_seconds": 60, "test_limit": 1000},
        start_time="2026-10-23T00:00:00Z",
        end_time="2026-10-23T00:01:00Z",
        process_exit_status=0,
        campaign_outcome="COMPLETED_VERIFIED",
        property_results=[{
            "property_name": "property_solvency",
            "status": "passed",
            "counterexample": None,
            "calls_count": 500,
            "error_message": None,
        }],
        artifact_refs=["artifacts/stdout.log"],
        verification_status="COMPLETED_VERIFIED",
        limitations=["bounded"],
    )
    manifest.validate()
    assert manifest.campaign_outcome == "COMPLETED_VERIFIED"
    assert manifest.medusa_version == "1.5.1"


def test_evidence_envelope_schema_validation():
    envelope = EvidenceEnvelope(
        envelope_id="ENV-MEDUSA-001",
        slug="test_slug",
        run_id="MEDUSA-RUN-001",
        status="COMPLETED_VERIFIED",
        evidence_type="MEDUSA_PROPERTY_FUZZING",
        manifest={"dummy": "manifest"},
        digests={
            "payload_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "raw_stdout_sha256": "1234",
            "raw_stderr_sha256": "5678",
            "target_source_sha256": "90ab",
        },
        provenance={
            "host": "test-runner",
            "git_commit": "0123456789abcdef0123456789abcdef01234567",
            "medusa_version": "1.5.1",
            "solc_version": "0.8.20",
        },
        timestamp="2026-10-23T00:01:00Z",
    )
    envelope.validate()
    assert envelope.status == "COMPLETED_VERIFIED"


def test_gate_decision_contract_validation():
    decision = GateDecisionContract(
        gate_id="GATE-AUTH-001",
        gate_name="AuthorizationGate",
        required_checks=["confirm_authorized"],
        passed_checks=["confirm_authorized"],
        failed_checks=[],
        decision="PASS",
        rationale="Authorized by --confirm",
        proposer="Orchestrator",
        evaluator="GovernanceAuditor",
        audit_reference="audit:001",
        timestamp="2026-10-23T00:00:00Z",
    )
    decision.validate()
    assert decision.decision == "PASS"


def test_audit_event_schema_validation():
    audit = AuditEvent(
        event_id="AUDIT-0001",
        event_type="STAGE_EXECUTION",
        run_id="RUN-001",
        stage="Stage1_Perception",
        actor="Orchestrator",
        action="validate_scope",
        status="SUCCESS",
        details={"path": "/contracts"},
        timestamp="2026-10-23T00:00:00Z",
    )
    audit.validate()
    assert audit.status == "SUCCESS"


def test_slug_traversal_rejection(fuzz_env):
    orch = MedusaGlassboxOrchestrator(
        slug="../escape",
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 2


def test_path_containment_rejection(fuzz_env):
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target="/etc/shadow",
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 2


def test_dry_run_zero_mutation(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "dry_run_test"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        dry_run=True,
        confirm=False,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0
    assert not output_dir.exists(), "Dry run must NOT create any output files or directories"


def test_missing_confirm_defaults_to_dry_run(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "no_confirm_test"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        dry_run=False,
        confirm=False,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0
    assert not output_dir.exists(), "Missing --confirm must default to dry-run zero-mutation"


def test_dry_run_overrides_confirm(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "precedence_test"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        dry_run=True,
        confirm=True,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0
    assert not output_dir.exists(), "--dry-run must strictly override --confirm"


def test_clean_simulation_execution(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "clean_sim_run"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        confirm=True,
        clean_sim=True,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0
    assert (output_dir / "campaign_manifest.json").is_file()
    assert (output_dir / "envelope.json").is_file()
    assert (output_dir / "receipt.json").is_file()
    assert (output_dir / "audit_events.json").is_file()
    assert (output_dir / "gate_decisions.json").is_file()

    manifest_data = json.loads((output_dir / "campaign_manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["campaign_outcome"] == "COMPLETED_VERIFIED"
    assert manifest_data["verification_status"] == "COMPLETED_VERIFIED"
    assert manifest_data["medusa_version"] != ""


def test_falsify_simulation_extracts_findings(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "falsify_sim_run"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        confirm=True,
        falsify_sim=True,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0
    assert (output_dir / "findings.json").is_file()

    findings_data = json.loads((output_dir / "findings.json").read_text(encoding="utf-8"))
    assert len(findings_data) >= 1
    f = findings_data[0]
    assert "MEDUSA-" in f["finding_id"]
    assert f["status"] == "VERIFIED"
    assert f["confidence"] == "CERTAIN"
    assert f["security_property"] != ""


def test_failure_simulation_exit_code(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "fail_sim_run"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        confirm=True,
        fail_sim=True,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 1


def test_timeout_simulation_exit_code(fuzz_env):
    output_dir = fuzz_env["scans_dir"] / "timeout_sim_run"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        confirm=True,
        timeout_sim=True,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 124


def test_independent_challenger_text_parsing(tmp_path: Path):
    target = tmp_path / "contracts"
    target.mkdir()
    challenger = MedusaIndependentChallenger(target, tmp_path)

    sample_output = (
        "Starting Medusa fuzzer...\n"
        "[PASS] property_owner_authorized\n"
        "[FAIL] property_solvency_conserved\n"
        "Call sequence:\n"
        "1. Vault.deposit(1000)\n"
        "2. Vault.borrow(2000)\n"
    )

    outcome, props, findings = challenger.parse_campaign_output(sample_output, "", 0)
    assert outcome == STATUS_COMPLETED_WITH_FINDINGS
    assert len(props) == 2
    assert len(findings) == 1
    assert findings[0].finding_id.startswith("MEDUSA-")
    assert "property_solvency_conserved" in findings[0].title


def test_bounty_root_target_containment(fuzz_env):
    """Test that targeting the bounty workspace root is permitted when output is under scans/."""
    output_dir = fuzz_env["bounty_dir"] / "scans" / "medusa" / "test_run"
    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["bounty_dir"]),
        output_dir=str(output_dir),
        dry_run=True,
        confirm=False,
        repo_root=fuzz_env["repo_root"],
    )
    code = orch.execute()
    assert code == 0


def test_medusa_command_orchestrator_execution(fuzz_env, tmp_path):
    """Test that reviewed MEDUSA_COMMAND executes through orchestrator and produces all Glassbox artifacts."""
    output_dir = fuzz_env["scans_dir"] / "medusa_cmd_run"
    mock_script = tmp_path / "mock_medusa_cmd.sh"
    mock_script.write_text(
        "#!/usr/bin/env bash\n"
        "echo '[PASS] property_solvency_conserved'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    mock_script.chmod(0o755)

    orch = MedusaGlassboxOrchestrator(
        slug="test_slug",
        target=str(fuzz_env["contracts_dir"]),
        output_dir=str(output_dir),
        confirm=True,
        dry_run=False,
        repo_root=fuzz_env["repo_root"],
        medusa_command=str(mock_script),
    )
    code = orch.execute()
    assert code == 0
    assert (output_dir / "campaign_manifest.json").is_file()
    assert (output_dir / "receipt.json").is_file()
    assert (output_dir / "envelope.json").is_file()
    assert (output_dir / "gate_decisions.json").is_file()
    assert (output_dir / "audit_events.json").is_file()
    assert (output_dir / "stdout.log").is_file()

    receipt_data = json.loads((output_dir / "receipt.json").read_text(encoding="utf-8"))
    assert receipt_data["tool"] == "medusa"
    assert "reviewed-command" in receipt_data["version"]


def test_campaign_outcome_gate_completed_with_limitations():
    """Test that STATUS_COMPLETED_WITH_LIMITATIONS with exit code 0 reconciles and passes."""
    adjudicator = MedusaGovernanceAdjudicator("RUN-LIMITATIONS-001")
    gate = adjudicator.evaluate_campaign_outcome_gate(
        "COMPLETED_WITH_LIMITATIONS", 0, []
    )
    assert gate.decision == "PASS"
    assert "outcome_reconciled" in gate.passed_checks

