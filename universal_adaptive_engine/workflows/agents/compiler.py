"""Domain Compiler Engineer Agent Workflow implementation."""
from __future__ import annotations
import ast
from pathlib import Path
from typing import Any

from universal_adaptive_engine.workflows.base import AgentWorkflow, WorkflowStage
from universal_adaptive_engine.models.task import TaskTests


class DomainCompilerEngineerWorkflow(AgentWorkflow):
    """Domain Compiler Engineer Agent Workflow.

    Handles BASELINE and VERIFICATION stages to validate compiler toolchains,
    syntax trees, and compilation readiness without simulating false passes.
    """

    def __init__(self, adapter=None):
        super().__init__(
            agent_id="agent-domain-compiler-engineer",
            role="Domain Compiler Engineer",
            category="domain_specialist",
            authority_level="specialist",
            supported_stages=[WorkflowStage.BASELINE, WorkflowStage.VERIFICATION],
            adapter=adapter,
        )

    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        workspace_root = Path(context.get("workspace_root", "/home/nova/projects/cantina"))
        python_files = context.get("check_syntax_files", [
            "universal_adaptive_engine/cli.py",
            "universal_adaptive_engine/harness/orchestrator.py",
        ])

        passed_syntax = []
        failed_syntax = []

        for rel_path in python_files:
            file_path = workspace_root / rel_path
            if file_path.exists():
                try:
                    ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
                    passed_syntax.append(str(rel_path))
                except SyntaxError as e:
                    failed_syntax.append(f"{rel_path}: {e}")

        # Check compiler availability via adapter if present
        compiler_status = "unavailable"
        if self.adapter:
            disc = self.adapter.discover()
            tools = disc.get("tools", {})
            if tools.get("solc", {}).get("available"):
                compiler_status = "available"

        if failed_syntax:
            raise SyntaxError(f"Compiler syntax check failed: {failed_syntax}")

        tests = TaskTests(passed=[f"syntax_check_{Path(f).stem}" for f in passed_syntax])
        evidence_refs = [f"EVID-COMPILER-SYNTAX-{context.get('task_id', '001')}"]

        limitations = []
        if compiler_status == "unavailable":
            limitations.append("External domain compilers (solc/foundry) are not installed; AST syntax verification used as supported baseline")

        status = "COMPLETED_VERIFIED" if not limitations else "COMPLETED_WITH_LIMITATIONS"

        return {
            "status": status,
            "summary": f"Domain Compiler Engineer validated AST syntax for {len(passed_syntax)} files (solc: {compiler_status})",
            "claims": [f"AST parse clean for: {', '.join(passed_syntax)}", f"Solidity compiler: {compiler_status}"],
            "evidence_refs": evidence_refs,
            "files_inspected": passed_syntax,
            "limitations": limitations,
            "next_action": "Proceed to security review and authorization checks",
            "tests": tests,
        }
