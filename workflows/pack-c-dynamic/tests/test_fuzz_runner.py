#!/usr/bin/env python3
"""
Python Acceptance & Invariant Test Suite for Pack C Bounded Forge Fuzz Runner.
Verifies path containment, argument validation, authorization gates,
timeout propagation, and atomic artifact serialization.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_SCRIPT = REPO_ROOT / "workflows/pack-c-dynamic/workflow-fuzz.sh"
BOUNDED_SCRIPT = REPO_ROOT / "scripts/bounded_forge_fuzz.sh"
ADAPTER = REPO_ROOT / ".agents/skills/qrpe/adapters/foundry_adapter.py"


def run_runner(*args, env=None) -> subprocess.CompletedProcess:
    cmd = ["bash", str(WORKFLOW_SCRIPT), *args]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=merged_env)


class TestArgumentParsing:
    def test_default_dry_run(self):
        res = run_runner()
        assert res.returncode == 0
        assert "Mode: dry-run" in res.stdout
        assert "[DRY-RUN]" in res.stdout

    def test_explicit_dry_run(self):
        res = run_runner("--dry-run")
        assert res.returncode == 0
        assert "Mode: dry-run" in res.stdout
        assert "[DRY-RUN]" in res.stdout

    def test_dry_run_and_confirm_exclusive(self):
        res1 = run_runner("--dry-run", "--confirm")
        assert res1.returncode == 2
        assert "--dry-run and --confirm cannot be combined" in res1.stderr

        res2 = run_runner("--confirm", "--dry-run")
        assert res2.returncode == 2
        assert "--dry-run and --confirm cannot be combined" in res2.stderr

    def test_duplicate_flags_allowed(self):
        res = run_runner("--dry-run", "--dry-run")
        assert res.returncode == 0
        assert "Mode: dry-run" in res.stdout

    def test_unknown_option_rejected(self):
        res = run_runner("--bogus-flag")
        assert res.returncode == 2
        assert "Unknown argument: --bogus-flag" in res.stderr

    def test_missing_option_values(self):
        res1 = run_runner("--target")
        assert res1.returncode == 2
        assert "Missing value for --target" in res1.stderr

        res2 = run_runner("--target", "--dry-run")
        assert res2.returncode == 2
        assert "Invalid value for --target" in res2.stderr

        res3 = run_runner("--output-dir")
        assert res3.returncode == 2
        assert "Missing value for --output-dir" in res3.stderr

    def test_help_flags(self):
        res_h = run_runner("-h")
        assert res_h.returncode == 0
        assert "Usage:" in res_h.stdout

        res_help = run_runner("--help")
        assert res_help.returncode == 0
        assert "Usage:" in res_help.stdout


class TestPathContainment:
    def test_relative_escape_rejected(self):
        res = run_runner("--target", "../outside_repo")
        assert res.returncode == 2
        assert "escapes the repository root" in (res.stdout + res.stderr)

    def test_absolute_path_rejected(self):
        res = run_runner("--target", "/etc")
        assert res.returncode == 2
        assert "must be repository-relative" in (res.stdout + res.stderr)

    def test_symlink_escape_rejected(self, tmp_path):
        sym_dir = REPO_ROOT / "workflows/pack-c-dynamic/tests/.tmp_pytest_sym"
        try:
            if sym_dir.exists() or sym_dir.is_symlink():
                os.unlink(sym_dir)
            os.symlink("/tmp", sym_dir)
            rel_path = "workflows/pack-c-dynamic/tests/.tmp_pytest_sym"
            res = run_runner("--target", rel_path)
            assert res.returncode == 2
            assert "escapes the repository root" in (res.stdout + res.stderr)
        finally:
            if sym_dir.is_symlink() or sym_dir.exists():
                os.unlink(sym_dir)

    def test_repo_root_as_target_rejected(self):
        res = run_runner("--target", ".")
        assert res.returncode == 2
        assert "cannot be the repository root" in (res.stdout + res.stderr)

    def test_repo_root_as_output_dir_rejected(self):
        res = run_runner("--output-dir", ".")
        assert res.returncode == 2
        assert "cannot be the repository root" in (res.stdout + res.stderr)

    def test_nonexistent_target_rejected(self):
        res = run_runner("--target", "bounties/nonexistent_xyz_123")
        assert res.returncode == 2
        assert "Target directory does not exist" in (res.stdout + res.stderr)

    def test_regular_file_as_output_dir_rejected(self, tmp_path):
        test_file = REPO_ROOT / "workflows/pack-c-dynamic/tests/.tmp_pytest_file"
        try:
            test_file.write_text("not a dir")
            rel_path = "workflows/pack-c-dynamic/tests/.tmp_pytest_file"
            res = run_runner("--output-dir", rel_path)
            assert res.returncode == 2
            assert "Output path exists but is not a directory" in (res.stdout + res.stderr)
        finally:
            if test_file.exists():
                test_file.unlink()


class TestExecutionGatesAndPropagation:
    def test_prerequisite_adapter_missing(self):
        res = run_runner(env={"ADAPTER": "/nonexistent/fake.py"})
        assert res.returncode == 2
        assert "Foundry adapter not found" in res.stderr

    def test_prerequisite_repo_root_missing(self):
        res = run_runner(env={"REPO_ROOT": "/nonexistent/path"})
        assert res.returncode == 2
        assert "Repository root not found" in res.stderr

    def test_adapter_exit_code_preserved(self, tmp_path):
        mock_adapter = tmp_path / "mock_adapter.py"
        mock_adapter.write_text("import sys\nprint('[MOCK_ERR]', file=sys.stderr)\nsys.exit(37)\n")
        res = run_runner(env={"ADAPTER": str(mock_adapter)})
        assert res.returncode == 37
        assert "[MOCK_ERR]" in res.stderr

    def test_confirmed_missing_receipt_rejected(self, tmp_path):
        mock_adapter = tmp_path / "mock_missing_adapter.py"
        mock_adapter.write_text("import sys\nprint('[MOCK_OK]')\nsys.exit(0)\n")
        out_rel = "workflows/pack-c-dynamic/tests/.tmp_pytest_missing"
        out_path = REPO_ROOT / out_rel
        try:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)
            res = run_runner("--confirm", "--output-dir", out_rel, env={"ADAPTER": str(mock_adapter)})
            assert res.returncode == 1
            assert "Missing result artifact" in res.stderr
        finally:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)

    def test_confirmed_corrupt_receipt_rejected(self, tmp_path):
        mock_adapter = tmp_path / "mock_corrupt_adapter.py"
        code = (
            "import sys, pathlib\n"
            "out_idx = sys.argv.index('--output-dir') + 1\n"
            "out_dir = pathlib.Path(sys.argv[out_idx])\n"
            "out_dir.mkdir(parents=True, exist_ok=True)\n"
            "(out_dir / 'receipt.json').write_text('{ bad json')\n"
            "sys.exit(0)\n"
        )
        mock_adapter.write_text(code)
        out_rel = "workflows/pack-c-dynamic/tests/.tmp_pytest_corrupt"
        out_path = REPO_ROOT / out_rel
        try:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)
            res = run_runner("--confirm", "--output-dir", out_rel, env={"ADAPTER": str(mock_adapter)})
            assert res.returncode == 1
            assert "Invalid result artifact JSON" in res.stderr
        finally:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)

    def test_dry_run_leaves_zero_artifacts(self, tmp_path):
        out_rel = "workflows/pack-c-dynamic/tests/.tmp_pytest_dry"
        out_path = REPO_ROOT / out_rel
        try:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)
            res = run_runner("--output-dir", out_rel, "--dry-run")
            assert res.returncode == 0
            receipt = out_path / "receipt.json"
            assert not receipt.exists()
        finally:
            if out_path.exists():
                import shutil
                shutil.rmtree(out_path)

    def test_symlink_script_parity(self):
        assert BOUNDED_SCRIPT.is_symlink() or BOUNDED_SCRIPT.exists()
        res = subprocess.run(["bash", str(BOUNDED_SCRIPT), "--help"], capture_output=True, text=True)
        assert res.returncode == 0
        assert "bounded_forge_fuzz.sh" in res.stdout
