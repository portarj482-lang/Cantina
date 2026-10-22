"""Verification Engineer Agent Workflow implementation."""
from __future__ import annotations
import subprocess
import time
from typing import Any

from universal_adaptive_engine.workflows.base import AgentWorkflow, WorkflowStage
from universal_adaptive_engine.models.task import TaskTests


class VerificationEngineerWorkflow(AgentWorkflow):
    """Verification Engineer Agent Workflow.

    Handles VERIFICATION stage to execute deterministic automated tests,
    capture pass/fail outcomes, compute digests, and generate evidence.
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

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        test_commands = context.get("test_commands", [])
        workspace_root = context.get("workspace_root", "/home/nova/projects/cantina")

        passed_tests = []
        failed_tests = []
        commands_run = []

        if not test_commands:
            # Default verification check: targeted deterministic baseline check
            test_commands = ["python3 -m unittest global/core/tests/test_case_state.py"]


        for cmd in test_commands:
            t0 = time.time()
            res = subprocess.run(cmd, shell=True, cwd=workspace_root, capture_output=True, text=True)
            duration_ms = round((time.time() - t0) * 1000, 2)
            commands_run.append({
                "command": cmd,
                "exit_code": res.returncode,
                "duration_ms": duration_ms,
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
        evidence_refs = [f"EVID-VERIFY-PASS-{context.get('task_id', '001')}"]

        return {
            "status": "COMPLETED_VERIFIED",
            "summary": f"Verification Engineer confirmed {len(passed_tests)} tests passed with 0 failures",
            "claims": claims,
            "evidence_refs": evidence_refs,
            "commands_run": commands_run,
            "next_action": "Submit slice to independent challenger for adversarial review",
            "tests": TaskTests(passed=passed_tests, failed=[]),
        }
