"""Universal Adaptive Workflow & Pipeline Base Architecture."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional
import uuid

from universal_adaptive_engine.models.handoff import HandoffRecord
from universal_adaptive_engine.models.task import TaskTests
from universal_adaptive_engine.models.enums import BlockerCategory
from universal_adaptive_engine.models.blocker import BlockerRecord
from universal_adaptive_engine.adapters.protocol import ArchitectureAdapter


class WorkflowStage(str, Enum):
    """The 14 canonical lifecycle stages defined in the architecture blueprint."""
    INTAKE = "INTAKE"
    DISCOVERY = "DISCOVERY"
    BASELINE = "BASELINE"
    DECOMPOSITION = "DECOMPOSITION"
    PLAN = "PLAN"
    AUTHORIZATION_CHECK = "AUTHORIZATION_CHECK"
    IMPLEMENTATION = "IMPLEMENTATION"
    VERIFICATION = "VERIFICATION"
    INDEPENDENT_REVIEW = "INDEPENDENT_REVIEW"
    STAGING = "STAGING"
    APPROVAL = "APPROVAL"
    DEPLOYMENT = "DEPLOYMENT"
    POST_DEPLOYMENT_VALIDATION = "POST_DEPLOYMENT_VALIDATION"
    COMPLETION_REPORT = "COMPLETION_REPORT"


@dataclass
class PipelineStage:
    """Represents a configured stage in an AgentPipeline."""
    stage: WorkflowStage
    workflow: AgentWorkflow
    required: bool = True
    skippable: bool = False
    skip_reason: Optional[str] = None


@dataclass
class PipelineExecutionReport:
    """Consolidated report produced by an AgentPipeline execution."""
    pipeline_name: str
    goal: str
    overall_status: str  # COMPLETED_VERIFIED, COMPLETED_WITH_LIMITATIONS, BLOCKED, FAILED
    stage_handoffs: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence_collected: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_name": self.pipeline_name,
            "goal": self.goal,
            "overall_status": self.overall_status,
            "stage_handoffs": self.stage_handoffs,
            "evidence_collected": self.evidence_collected,
            "limitations": self.limitations,
            "blockers": self.blockers,
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Pipeline Execution Report: {self.pipeline_name}",
            f"**Overall Status:** `{self.overall_status}`",
            f"**Timestamp:** {self.timestamp}",
            f"**Goal:** {self.goal}",
            "",
            "## 1. Stage Handoff Summaries",
        ]
        for stage_name, handoff in self.stage_handoffs.items():
            status = handoff.get("status", "UNKNOWN")
            agent = handoff.get("agent_role", "Unknown")
            summary = handoff.get("summary", "")
            lines.append(f"- **Stage `{stage_name}`** (`{status}`) - *{agent}*")
            lines.append(f"  - {summary}")
            ev = handoff.get("evidence_refs", [])
            if ev:
                lines.append(f"  - Evidence: {', '.join(ev)}")

        lines.extend(["", "## 2. Evidence Collected"])
        if self.evidence_collected:
            for ev in self.evidence_collected:
                lines.append(f"- `{ev}`")
        else:
            lines.append("- None")

        lines.extend(["", "## 3. Limitations & Blockers"])
        if self.blockers:
            for blk in self.blockers:
                lines.append(f"- **BLOCKER:** {blk}")
        if self.limitations:
            for lim in self.limitations:
                lines.append(f"- {lim}")
        if not self.blockers and not self.limitations:
            lines.append("- None observed")

        return "\n".join(lines)


class AgentWorkflow(ABC):
    """Abstract base class for an agent executing a workflow stage.

    Provides template method pattern `execute()`, lifecycle hooks (`pre_execute`,
    `run_step`, `validate_handoff`, `post_execute`, `handle_blocker`), and adapter binding.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        category: str,
        authority_level: str = "specialist",
        supported_stages: Optional[list[WorkflowStage]] = None,
        adapter: Optional[ArchitectureAdapter] = None,
    ):
        self.agent_id = agent_id
        self.role = role
        self.category = category
        self.authority_level = authority_level
        self.supported_stages = supported_stages or []
        self.adapter = adapter

    def can_handle(self, stage: WorkflowStage | str) -> bool:
        if isinstance(stage, str):
            try:
                stage = WorkflowStage(stage)
            except ValueError:
                return False
        return stage in self.supported_stages

    def execute(self, context: dict[str, Any]) -> HandoffRecord:
        """Template execution method enforcing input checks, step logic, and handoff validation."""
        task_id = context.get("task_id", f"TASK-{uuid.uuid4().hex[:6]}")
        stage_val = context.get("stage")
        stage_name = stage_val.value if isinstance(stage_val, WorkflowStage) else (str(stage_val) if stage_val else None)

        try:
            self.pre_execute(context)
            step_output = self.run_step(context)

            # Build handoff record from step output
            handoff = HandoffRecord(
                task_id=task_id,
                agent_role=self.role,
                stage=stage_name,
                status=step_output.get("status", "COMPLETED_VERIFIED"),
                summary=step_output.get("summary", f"{self.role} completed execution"),
                claims=list(step_output.get("claims", [])),
                evidence_refs=list(step_output.get("evidence_refs", [])),
                files_inspected=list(step_output.get("files_inspected", [])),
                files_changed=list(step_output.get("files_changed", [])),
                commands_run=list(step_output.get("commands_run", [])),
                tests=step_output.get("tests", TaskTests()),
                artifacts=list(step_output.get("artifacts", [])),
                assumptions=list(step_output.get("assumptions", [])),
                limitations=list(step_output.get("limitations", [])),
                security_concerns=list(step_output.get("security_concerns", [])),
                next_action=step_output.get("next_action", "Proceed to next workflow stage"),
            )

            self.validate_handoff(handoff)
            return self.post_execute(handoff, context)

        except Exception as e:
            return self.handle_blocker(e, context)

    def pre_execute(self, context: dict[str, Any]) -> None:
        """Pre-execution validation hook. Subclasses may override."""
        pass

    @abstractmethod
    def run_step(self, context: dict[str, Any]) -> dict[str, Any]:
        """Core execution logic to be implemented by specific agent workflows."""
        raise NotImplementedError("Subclasses must implement run_step")

    def validate_handoff(self, handoff: HandoffRecord) -> None:
        """Validate resulting handoff against schema and architectural invariants."""
        handoff.validate()

    def post_execute(self, handoff: HandoffRecord, context: dict[str, Any]) -> HandoffRecord:
        """Post-execution hook for caching, evidence store registration, etc."""
        return handoff

    def handle_blocker(self, error: Exception, context: dict[str, Any]) -> HandoffRecord:
        """Translate exceptions into structured machine-validated BLOCKED/FAILED handoff envelopes."""
        task_id = context.get("task_id", f"TASK-{uuid.uuid4().hex[:6]}")
        stage_val = context.get("stage")
        stage_name = stage_val.value if isinstance(stage_val, WorkflowStage) else (str(stage_val) if stage_val else None)

        err_str = str(error)
        is_blocked = (
            isinstance(error, (PermissionError, FileNotFoundError))
            or "blocked" in err_str.lower()
            or "permission" in err_str.lower()
            or "not found" in err_str.lower()
            or "missing" in err_str.lower()
            or "policy" in err_str.lower()
            or "boundary" in err_str.lower()
            or "outside workspace" in err_str.lower()
        )
        status = "BLOCKED" if is_blocked else "FAILED"


        handoff = HandoffRecord(
            task_id=task_id,
            agent_role=self.role,
            stage=stage_name,
            status=status,
            summary=f"Execution halted with {status}: {err_str}",
            limitations=[f"Execution stopped: {err_str}"],
            next_action="Diagnose and resolve blocker prerequisite before retrying",
        )
        return handoff


class AgentPipeline:
    """Composable pipeline chaining multiple AgentWorkflows through a configured sequence."""

    def __init__(self, name: str, adapter: Optional[ArchitectureAdapter] = None):
        self.name = name
        self.adapter = adapter
        self.stages: list[PipelineStage] = []

    def add_stage(
        self,
        stage: WorkflowStage,
        workflow: AgentWorkflow,
        required: bool = True,
        skippable: bool = False,
    ) -> AgentPipeline:
        """Add a stage to the pipeline sequence."""
        if self.adapter and workflow.adapter is None:
            workflow.adapter = self.adapter
        self.stages.append(PipelineStage(stage=stage, workflow=workflow, required=required, skippable=skippable))
        return self

    def override_stage(self, stage: WorkflowStage, new_workflow: AgentWorkflow) -> bool:
        """Replace an existing stage's agent workflow with a specialized subagent workflow."""
        if self.adapter and new_workflow.adapter is None:
            new_workflow.adapter = self.adapter
        for s in self.stages:
            if s.stage == stage:
                s.workflow = new_workflow
                return True
        return False

    def skip_stage(self, stage: WorkflowStage, reason: str) -> bool:
        """Mark a stage as skippable with an explicit reason."""
        for s in self.stages:
            if s.stage == stage:
                s.skippable = True
                s.skip_reason = reason
                return True
        return False

    def execute(self, initial_context: Optional[dict[str, Any]] = None) -> PipelineExecutionReport:
        """Execute the pipeline sequentially, threading context and accumulating handoffs."""
        context = dict(initial_context or {})
        goal = str(context.get("goal", "Execute canonical pipeline"))
        task_id = context.get("task_id", f"TASK-PIPE-{uuid.uuid4().hex[:6]}")
        if "workspace_root" not in context:
            if hasattr(self, "workspace_root") and self.workspace_root:
                context["workspace_root"] = str(self.workspace_root)
            elif self.adapter and hasattr(self.adapter, "workspace_root") and self.adapter.workspace_root:
                context["workspace_root"] = str(self.adapter.workspace_root)

        if hasattr(self, "bounty_slug") and getattr(self, "bounty_slug") and "bounty_slug" not in context:
            context["bounty_slug"] = str(getattr(self, "bounty_slug"))
        if hasattr(self, "target_root") and getattr(self, "target_root") and "target_root" not in context:
            context["target_root"] = str(getattr(self, "target_root"))

        if "target_context" not in context:
            try:
                from universal_adaptive_engine.models.target_context import TargetContextResolver
                tc = TargetContextResolver.resolve(context, context.get("workspace_root"))
                context["target_context"] = tc
                if tc.bounty_slug and "bounty_slug" not in context:
                    context["bounty_slug"] = tc.bounty_slug
                if tc.target_root and "target_root" not in context:
                    context["target_root"] = str(tc.target_root)
            except Exception:
                pass

        stage_handoffs: dict[str, dict[str, Any]] = {}
        all_evidence: list[str] = []
        all_limitations: list[str] = []
        all_blockers: list[str] = []
        pipeline_status = "COMPLETED_VERIFIED"

        for p_stage in self.stages:
            stage_name = p_stage.stage.value

            # Check if stage is marked skippable with reason
            if p_stage.skippable and p_stage.skip_reason:
                handoff = HandoffRecord(
                    task_id=task_id,
                    agent_role=p_stage.workflow.role,
                    stage=stage_name,
                    status="NOT_RUN",
                    summary=f"Stage skipped: {p_stage.skip_reason}",
                    limitations=[f"Skipped stage {stage_name}: {p_stage.skip_reason}"],
                    next_action="Proceed to subsequent stage",
                )
                stage_handoffs[stage_name] = handoff.to_dict()
                all_limitations.extend(handoff.limitations)
                context["last_handoff"] = handoff.to_dict()
                context.setdefault("stage_handoffs", {})[stage_name] = handoff.to_dict()
                continue

            # Set current stage in context
            context["stage"] = p_stage.stage
            handoff = p_stage.workflow.execute(context)
            stage_handoffs[stage_name] = handoff.to_dict()
            context["last_handoff"] = handoff.to_dict()
            context.setdefault("stage_handoffs", {})[stage_name] = handoff.to_dict()

            all_evidence.extend(handoff.evidence_refs)
            all_limitations.extend(handoff.limitations)

            if handoff.status == "BLOCKED":
                all_blockers.append(f"{stage_name} blocked by {p_stage.workflow.role}: {handoff.summary}")
                if p_stage.required:
                    pipeline_status = "BLOCKED"
                    # Mark remaining stages as NOT_RUN
                    self._mark_remaining_not_run(p_stage.stage, stage_handoffs, task_id, "Prior required stage blocked")
                    break
            elif handoff.status == "FAILED":
                all_blockers.append(f"{stage_name} failed under {p_stage.workflow.role}: {handoff.summary}")
                if p_stage.required:
                    pipeline_status = "FAILED"
                    self._mark_remaining_not_run(p_stage.stage, stage_handoffs, task_id, "Prior required stage failed")
                    break
            elif handoff.status == "COMPLETED_WITH_LIMITATIONS":
                if pipeline_status == "COMPLETED_VERIFIED":
                    pipeline_status = "COMPLETED_WITH_LIMITATIONS"

        return PipelineExecutionReport(
            pipeline_name=self.name,
            goal=goal,
            overall_status=pipeline_status,
            stage_handoffs=stage_handoffs,
            evidence_collected=list(set(all_evidence)),
            limitations=list(set(all_limitations)),
            blockers=all_blockers,
        )

    def _mark_remaining_not_run(
        self,
        current_stage: WorkflowStage,
        stage_handoffs: dict[str, dict[str, Any]],
        task_id: str,
        reason: str,
    ) -> None:
        passed_current = False
        for s in self.stages:
            if s.stage == current_stage:
                passed_current = True
                continue
            if passed_current:
                stage_handoffs[s.stage.value] = HandoffRecord(
                    task_id=task_id,
                    agent_role=s.workflow.role,
                    stage=s.stage.value,
                    status="NOT_RUN",
                    summary=f"Not run: {reason}",
                    limitations=[f"Stage {s.stage.value} was not run: {reason}"],
                    next_action="Resolve prerequisite failure",
                ).to_dict()
