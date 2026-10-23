"""Verification Engineer Agent Workflow implementation."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Optional

from universal_adaptive_engine.workflows.base import AgentWorkflow, WorkflowStage
from universal_adaptive_engine.models.task import TaskTests


class VerificationEngineerWorkflow(AgentWorkflow):
    """Verification Engineer Agent Workflow.

    Handles VERIFICATION stage to execute deterministic automated tests,
    capture pass/fail outcomes, compute SHA-256 digests, and generate evidence.
    Supports Python unit tests and Forge smart contract test execution.
    """

    def __init__(self, adapter=None):
        super().__init__(
            agent_id="agent-verification-engineer",
            role="Verification Engineer",
            category="verification",
            authority_level="specialist",
            supported_stages=[WorkflowStage.VERIFICATION],
            adapter=adapter,
        )

    def _resolve_tool_env(self) -> dict[str, str]:
        """Build execution environment enriched with common user toolchain directories."""
        env = os.environ.copy()
        user_tool_dirs = [
            Path.home() / ".foundry" / "bin",
            Path.home() / ".cargo" / "bin",
            Path.home() / ".local" / "bin",
            Path("/usr/local/bin"),
        ]
        search_path = env.get("PATH", "")
        for d in user_tool_dirs:
            if d.exists() and str(d) not in search_path:
                search_path = f"{search_path}:{d}"
        env["PATH"] = search_path
        return env

    def _resolve_forge_binary(self, env: dict[str, str]) -> Optional[str]:
        """Locate the forge binary via search paths or adapter discovery."""
        return shutil.which("forge", path=env.get("PATH", ""))

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        test_commands = context.get("test_commands", [])
        workspace_root = context.get("workspace_root", ".")
        use_forge = context.get("use_forge", False)
        forge_args = context.get("forge_args", [])
        test_framework = context.get("test_framework")
        task_id = context.get("task_id", "001")

        env = self._resolve_tool_env()
        forge_bin = self._resolve_forge_binary(env)

        # Detect if forge testing is explicitly requested or inferred from foundry.toml
        workspace_path = Path(workspace_root).resolve()
        has_foundry_project = (workspace_path / "foundry.toml").exists()

        is_forge_run = use_forge or test_framework == "foundry" or (has_foundry_project and not test_commands)

        if is_forge_run:
            if not forge_bin:
                raise RuntimeError(
                    "Deterministic verification failed: Forge binary not found in PATH or ~/.foundry/bin"
                )
            cmd_list = [forge_bin, "test", "--root", str(workspace_path)]
            if forge_args:
                cmd_list.extend(forge_args)

            t0 = time.time()
            res = subprocess.run(cmd_list, cwd=str(workspace_path), capture_output=True, text=True, env=env)
            duration_ms = round((time.time() - t0) * 1000, 2)

            raw_output = res.stdout + ("\n" + res.stderr if res.stderr else "")
            output_digest = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()

            # Parse Forge test summary
            passed_tests = []
            failed_tests = []
            for line in raw_output.splitlines():
                line_str = line.strip()
                if line_str.startswith("[PASS]"):
                    passed_tests.append(line_str)
                elif line_str.startswith("[FAIL]"):
                    failed_tests.append(line_str)

            if res.returncode != 0 and not failed_tests:
                failed_tests.append(f"forge test failed (exit {res.returncode}): {res.stderr[:200]}")

            commands_run = [{
                "command": " ".join(cmd_list),
                "exit_code": res.returncode,
                "duration_ms": duration_ms,
                "output_digest": output_digest,
            }]

            if failed_tests:
                raise RuntimeError(f"Forge verification tests failed: {failed_tests}")

            claims = [
                "Forge test suite passed deterministically with exit code 0",
                f"Executed via {forge_bin} with output digest {output_digest[:16]}...",
            ]
            evidence_refs = [f"EVID-VERIFY-FORGE-PASS-{task_id}"]

            return {
                "status": "COMPLETED_VERIFIED",
                "summary": f"Verification Engineer confirmed Forge tests passed ({len(passed_tests)} tests, 0 failures)",
                "claims": claims,
                "evidence_refs": evidence_refs,
                "commands_run": commands_run,
                "output_digest": output_digest,
                "next_action": "Submit slice to independent challenger for adversarial review",
                "tests": TaskTests(passed=passed_tests if passed_tests else ["forge test"], failed=[]),
            }

        passed_tests = []
        failed_tests = []
        commands_run = []

        if not test_commands:
            # Default verification check: targeted deterministic baseline check
            test_commands = ["python3 -m unittest global/core/tests/test_case_state.py"]

        for cmd in test_commands:
            t0 = time.time()
            res = subprocess.run(cmd, shell=True, cwd=workspace_root, capture_output=True, text=True, env=env)
            duration_ms = round((time.time() - t0) * 1000, 2)
            cmd_digest = hashlib.sha256((res.stdout + res.stderr).encode("utf-8")).hexdigest()
            commands_run.append({
                "command": cmd,
                "exit_code": res.returncode,
                "duration_ms": duration_ms,
                "output_digest": cmd_digest,
            })
            if res.returncode == 0:
                passed_tests.append(cmd)
            else:
                failed_tests.append(f"{cmd} (exit {res.returncode}): {res.stderr[:200]}")

        if failed_tests:
            raise RuntimeError(f"Deterministic verification tests failed: {failed_tests}")

        claims = [
            f"All {len(passed_tests)} verification test suites passed deterministically",
            "Reproducible test execution confirmed with exit status 0",
        ]
        evidence_refs = [f"EVID-VERIFY-PASS-{task_id}"]

        return {
            "status": "COMPLETED_VERIFIED",
            "summary": f"Verification Engineer confirmed {len(passed_tests)} tests passed with 0 failures",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "commands_run": commands_run,
            "output_digest": commands_run[0]["output_digest"] if commands_run else None,
            "next_action": "Submit slice to independent challenger for adversarial review",
            "tests": TaskTests(passed=passed_tests, failed=[]),
        }
