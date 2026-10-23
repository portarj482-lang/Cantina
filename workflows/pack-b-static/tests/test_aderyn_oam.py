"""
Pytest suite for SAMA / OAM Aderyn Static Analysis Orchestrator.
Tests path containment, state machine transitions, independent validation layers,
evidence envelope schema compliance, and adversarial falsification checks.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import jsonschema
import pytest

WORKFLOW_DIR = Path(__file__).resolve().parents[1]
if str(WORKFLOW_DIR) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_DIR))

from aderyn_orchestrator import (
    OAMAderynOrchestrator,
    STATUS_BLOCKED,
    STATUS_DRY_RUN_COMPLETE,
    STATUS_COMPLETED_CLEAN,
    STATUS_COMPLETED_WITH_FINDINGS,
    STATUS_EXECUTION_FAILED,
    STATUS_VALIDATION_FAILED,
    compute_sha256,
)


@pytest.fixture
def oam_env(tmp_path: Path):
    repo_root = tmp_path / "cantina"
    repo_root.mkdir()
    bounty_dir = repo_root / "bounties" / "test_slug"
    contracts_dir = bounty_dir / "contracts" / "src"
    contracts_dir.mkdir(parents=True)
    scans_dir = bounty_dir / "scans" / "aderyn"
    scans_dir.mkdir(parents=True)

    # Minimal contract
    (contracts_dir / "Token.sol").write_text(
        "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.20;\ncontract Token {}\n"
    )

    # Tooling registry
    global_dir = repo_root / "global"
    global_dir.mkdir(parents=True)
    tooling_md = global_dir / "tooling.md"
    tooling_md.write_text(
        "| Tool | Use | Install | Version check | Status (2026-10-23) | Version | Command | Notes |\n"
        "| aderyn | Static analysis | cargo | aderyn --version | OK | 0.6.8 | aderyn . -o report.json | OK |\n"
    )

    # Schema
    schema_path = WORKFLOW_DIR / "schemas" / "evidence_envelope.schema.json"
    schema_data = json.loads(schema_path.read_text())

    # Adapter path
    real_adapter = WORKFLOW_DIR.parents[1] / ".agents" / "skills" / "qrpe" / "adapters" / "aderyn_adapter.py"

    return {
        "repo_root": repo_root,
        "bounty_dir": bounty_dir,
        "contracts_dir": bounty_dir / "contracts",
        "scans_dir": scans_dir,
        "slug": "test_slug",
        "adapter_path": real_adapter,
        "schema": schema_data,
    }


def test_invalid_slug_traversal_blocked(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug="../escape",
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_target_escape_blocked(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=Path("/etc"),
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED


def test_dry_run_zero_mutation(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=True,
        confirm=True,  # dry-run must override confirm
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 0
    assert orch.terminal_status == STATUS_DRY_RUN_COMPLETE
    # Zero files created in scans_dir
    assert list(oam_env["scans_dir"].glob("*")) == []


def test_schema_valid_evidence_envelope_clean(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 0
    assert orch.terminal_status == STATUS_COMPLETED_CLEAN

    envelope_file = oam_env["scans_dir"] / "evidence_envelope.json"
    assert envelope_file.exists()
    envelope_data = json.loads(envelope_file.read_text())

    # Validate against formal schema
    jsonschema.validate(instance=envelope_data, schema=oam_env["schema"])
    assert envelope_data["terminal_status"] == STATUS_COMPLETED_CLEAN
    assert envelope_data["findings_summary"]["total_findings"] == 0
    assert envelope_data["validation_results"]["digest_verified"] is True


def test_corrupt_report_causes_validation_failure(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        corrupt_report_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_VALIDATION_FAILED


def test_digest_mismatch_causes_validation_failure(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        digest_mismatch_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_VALIDATION_FAILED


def test_attribution_mismatch_detected(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        clean_sim=True,
        attribution_mismatch_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_VALIDATION_FAILED
    assert orch.error_code == "ATTRIBUTION_MISMATCH"


def test_scanner_failure_propagates_exit_code(oam_env):
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        scanner_fail_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1
    assert orch.terminal_status == STATUS_EXECUTION_FAILED
    assert orch.error_code == "EXECUTION_FAILED"

    # Verify evidence envelope conforms to schema on failure path
    envelope_file = oam_env["scans_dir"] / "evidence_envelope.json"
    assert envelope_file.exists()
    envelope_data = json.loads(envelope_file.read_text())
    jsonschema.validate(instance=envelope_data, schema=oam_env["schema"])
    assert envelope_data["terminal_status"] == STATUS_EXECUTION_FAILED
    assert envelope_data["error_code"] == "EXECUTION_FAILED"


def test_adapter_zero_cannot_override_receipt_nonzero(oam_env):
    """Preserve adapter failure semantics: adapter exit 0 cannot override nonzero receipt."""
    # Create valid dummy report and receipt with exit_code: 1
    report_file = oam_env["scans_dir"] / "aderyn.json"
    report_file.write_text(json.dumps({"files_summary": {}, "high_issues": {"issues": []}}))
    actual_sha = compute_sha256(report_file)

    receipt_file = oam_env["scans_dir"] / "receipt.json"
    receipt_data = {
        "tool": "aderyn",
        "version": "0.6.8",
        "command": ["aderyn", str(oam_env["contracts_dir"])],
        "exit_code": 1,
        "duration_seconds": 0.5,
        "output_file": str(report_file),
        "sha256": actual_sha,
    }
    receipt_file.write_text(json.dumps(receipt_data))

    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        adapter_path=oam_env["adapter_path"],
    )
    orch.adapter_exit_code = 0  # Adapter claimed 0
    success, exit_code = orch._perform_independent_validation()
    assert success is False
    assert exit_code == 1
    assert orch.terminal_status == STATUS_EXECUTION_FAILED
    assert orch.error_code == "EXECUTION_FAILED"


def test_existing_valid_artifact_survives_failed_scan(oam_env):
    """Invariance rule: existing valid artifacts must survive failed runs intact."""
    report_file = oam_env["scans_dir"] / "aderyn.json"
    initial_content = json.dumps({"files_summary": {"initial": True}, "high_issues": {"issues": []}})
    report_file.write_text(initial_content)
    initial_sha = compute_sha256(report_file)

    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=oam_env["contracts_dir"],
        output_dir=oam_env["scans_dir"],
        dry_run=False,
        confirm=True,
        scanner_fail_sim=True,
        adapter_path=oam_env["adapter_path"],
    )
    code = orch.run_lifecycle()
    assert code == 1

    # Verify existing aderyn.json was preserved completely intact
    assert report_file.exists()
    assert compute_sha256(report_file) == initial_sha
    assert report_file.read_text() == initial_content


def test_prefix_scope_escape_blocked(oam_env):
    """Verify that a path with prefix matching repo_root name is rejected."""
    evil_target = oam_env["repo_root"].parent / f"{oam_env['repo_root'].name}_attacker"
    orch = OAMAderynOrchestrator(
        repo_root=oam_env["repo_root"],
        slug=oam_env["slug"],
        target_dir=evil_target,
        dry_run=True,
    )
    code = orch.run_lifecycle()
    assert code == 2
    assert orch.terminal_status == STATUS_BLOCKED

