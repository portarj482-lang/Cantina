"""Pytest suite for UOOMA Pack B SARIF Collector Engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path
import pytest

COLLECTOR_DIR = Path(__file__).resolve().parents[1]
if str(COLLECTOR_DIR) not in sys.path:
    sys.path.insert(0, str(COLLECTOR_DIR))

from sarif_collector import (
    UOOMASarifCollector,
    PathTraversalError,
    SARIFNormalizationError,
    compute_sha256,
    compute_str_hash,
)


@pytest.fixture
def test_env(tmp_path: Path):
    repo_root = tmp_path / "cantina"
    repo_root.mkdir()
    bounties_dir = repo_root / "bounties" / "test_bounty" / "scans"
    bounties_dir.mkdir(parents=True)
    schemas_dir = repo_root / "workflows" / "pack-b-static" / "schemas"
    schemas_dir.mkdir(parents=True)

    # Copy schema from actual repo
    real_schema = Path(__file__).resolve().parents[1] / "schemas" / "normalized_sarif.schema.json"
    (schemas_dir / "normalized_sarif.schema.json").write_text(real_schema.read_text())

    return {
        "repo_root": repo_root,
        "scans_dir": bounties_dir,
        "slug": "test_bounty",
    }


def test_slug_validation_rejects_traversal(test_env):
    with pytest.raises(PathTraversalError):
        UOOMASarifCollector(
            repo_root=test_env["repo_root"],
            slug="../evil",
            dry_run=True,
        )


def test_slug_validation_rejects_special_chars(test_env):
    with pytest.raises(PathTraversalError):
        UOOMASarifCollector(
            repo_root=test_env["repo_root"],
            slug="bad/slug",
            dry_run=True,
        )


def test_empty_directory_produces_empty_status(test_env):
    collector = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        dry_run=False,
        confirm=True,
    )
    exit_code = collector.execute()
    assert exit_code == 0
    out_file = test_env["scans_dir"] / "normalized_sarif.json"
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["status"] == "EMPTY"
    assert data["summary"]["total_raw_findings"] == 0
    assert data["summary"]["deduplicated_findings"] == 0
    assert data["verification_records"]["readback_verified"] is True


def test_slither_and_semgrep_normalization(test_env):
    scans_dir = test_env["scans_dir"]

    # Write Slither fixture
    slither_data = {
        "results": {
            "detectors": [
                {
                    "check": "uninitialized-state",
                    "impact": "High",
                    "description": "Uninitialized state variable",
                    "id": "init-1",
                    "elements": [
                        {
                            "name": "owner",
                            "source_mapping": {
                                "filename_relative": "contracts/Ownable.sol",
                                "lines": [12],
                            },
                        }
                    ],
                }
            ]
        }
    }
    (scans_dir / "slither.json").write_text(json.dumps(slither_data))

    # Write Semgrep fixture
    semgrep_data = {
        "results": [
            {
                "check_id": "missing-zero-check",
                "path": "contracts/Token.sol",
                "start": {"line": 40},
                "end": {"line": 40},
                "extra": {"message": "Missing zero address validation"},
            }
        ]
    }
    (scans_dir / "semgrep.json").write_text(json.dumps(semgrep_data))

    collector = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        dry_run=False,
        confirm=True,
    )
    exit_code = collector.execute()
    assert exit_code == 0

    out_file = scans_dir / "normalized_sarif.json"
    data = json.loads(out_file.read_text())
    assert data["status"] == "COLLECTED"
    assert len(data["runs"]) == 2
    assert data["summary"]["deduplicated_findings"] == 2
    assert "slither" in data["summary"]["tool_breakdown"]
    assert "semgrep" in data["summary"]["tool_breakdown"]


def test_dry_run_does_not_create_file(test_env):
    collector = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        dry_run=True,
        confirm=True,
    )
    exit_code = collector.execute()
    assert exit_code == 0
    out_file = test_env["scans_dir"] / "normalized_sarif.json"
    assert not out_file.exists()


def test_falsification_on_corrupt_sim_preserves_valid_artifact(test_env):
    scans_dir = test_env["scans_dir"]
    # Create initial valid output
    out_file = scans_dir / "normalized_sarif.json"
    initial_content = json.dumps({"existing": "valid_artifact"})
    out_file.write_text(initial_content)

    collector = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        dry_run=False,
        confirm=True,
        corrupt_sim=True,
    )
    exit_code = collector.execute()
    assert exit_code == 1

    # Invariant: Prior valid artifact preserved
    assert out_file.read_text() == initial_content


def test_invalid_mode_raises_value_error(test_env):
    with pytest.raises(ValueError):
        UOOMASarifCollector(
            repo_root=test_env["repo_root"],
            slug=test_env["slug"],
            mode="INVALID_MODE",
        )


def test_modes_inspect_plan_and_verify(test_env, capsys):
    scans_dir = test_env["scans_dir"]
    (scans_dir / "dummy.sarif").write_text(json.dumps({
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "test-tool"}},
            "results": [{
                "ruleId": "T001",
                "message": {"text": "Test rule finding"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": "Test.sol"}, "region": {"startLine": 5}}}],
            }],
        }]
    }))

    # 1. Mode INSPECT
    c_inspect = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        mode="INSPECT",
    )
    assert c_inspect.execute() == 0
    captured = capsys.readouterr()
    assert "[INSPECT] Discovered 1 scan files" in captured.out
    assert not (scans_dir / "normalized_sarif.json").exists()

    # 2. Mode PLAN
    c_plan = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        mode="PLAN",
    )
    assert c_plan.execute() == 0
    captured = capsys.readouterr()
    assert "[PLAN] Status: PLANNED" in captured.out
    assert not (scans_dir / "normalized_sarif.json").exists()

    # 3. Mode EXECUTE
    c_exec = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        mode="EXECUTE",
        confirm=True,
    )
    assert c_exec.execute() == 0
    out_file = scans_dir / "normalized_sarif.json"
    receipt_file = scans_dir / "receipt.json"
    assert out_file.exists()
    assert receipt_file.exists()

    # Check exact byte digest
    exact_hash = compute_sha256(out_file)
    receipt_data = json.loads(receipt_file.read_text())
    assert receipt_data["exact_file_sha256"] == exact_hash
    assert receipt_data["readback_verified"] is True

    # 4. Mode VERIFY
    c_verify = UOOMASarifCollector(
        repo_root=test_env["repo_root"],
        slug=test_env["slug"],
        mode="VERIFY",
    )
    assert c_verify.execute() == 0
    captured = capsys.readouterr()
    assert "[OK] Verification succeeded" in captured.out
