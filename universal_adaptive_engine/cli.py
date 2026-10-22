"""Command-line interface for Universal Adaptive Intelligence Architecture."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from universal_adaptive_engine.harness.orchestrator import UniversalAdaptiveOrchestrator
from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.adapters.cantina_adapter import CantinaBountyAdapter
from universal_adaptive_engine.providers import (
    ReasoningPurpose,
    ReasoningRequest,
    ReasoningStatus,
    get_reasoning_provider,
)
from universal_adaptive_engine.models.task import TaskRecord
from universal_adaptive_engine.models.finding import FindingRecord
from universal_adaptive_engine.models.adaptation import AdaptationRecord
from universal_adaptive_engine.models.evidence import EvidenceRecord
from universal_adaptive_engine.models.capability import CapabilityRecord
from universal_adaptive_engine.models.handoff import HandoffRecord
from universal_adaptive_engine.workflows.canonical_pipeline import CanonicalAdaptivePipeline
from universal_adaptive_engine.workflows.cantina_pipeline import CantinaBountyPipeline
from universal_adaptive_engine.workflows.operations import (
    get_operation_pipeline,
    list_available_operations,
    DisputeSystemPipeline,
    DelayedWETHSolvencyPipeline,
    MultiproofTEEPipeline,
    RPCGovernancePipeline,
)
from universal_adaptive_engine.workflows.base import WorkflowStage
from universal_adaptive_engine.workflows.agents import (
    OrchestratorWorkflow,
    ArchitectureAnalystWorkflow,
    RepositoryInvestigatorWorkflow,
    DomainCompilerEngineerWorkflow,
    DomainSecurityResearcherWorkflow,
    SecurityReviewerWorkflow,
    ImplementationEngineerWorkflow,
    VerificationEngineerWorkflow,
    IndependentChallengerWorkflow,
    ReleaseEngineerWorkflow,
    EvaluatorWorkflow,
    KnowledgeCuratorWorkflow,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Universal Adaptive Intelligence Architecture CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # discover
    disc_parser = subparsers.add_parser("discover", help="Discover host capabilities and environment")
    disc_parser.add_argument("--target-root", default=None, help="Target root directory to discover")
    disc_parser.add_argument("--bounty", default=None, help="Bounty slug to discover")

    # vertical-slice
    slice_parser = subparsers.add_parser("vertical-slice", help="Run an end-to-end vertical slice")
    slice_parser.add_argument("--goal", default="Verify host architecture integrity and canonical schemas")
    slice_parser.add_argument("--target", default="INSTRUCTIONS.md")
    slice_parser.add_argument("--slice", default=None, help="Vertical slice name or identifier")

    # health-check
    subparsers.add_parser("health-check", help="Run adapter and reasoning provider health checks")

    # reason
    reason_parser = subparsers.add_parser("reason", help="Query the reasoning provider for architectural analysis, planning, or hypothesis generation")
    reason_parser.add_argument("--prompt", required=True, help="Reasoning prompt / task instruction")
    reason_parser.add_argument("--purpose", default="planning", choices=[p.value for p in ReasoningPurpose], help="Reasoning task purpose")
    reason_parser.add_argument("--system-instruction", default=None, help="Optional system instruction")
    reason_parser.add_argument("--input-file", default=None, help="Optional JSON or text file to include as context")
    reason_parser.add_argument("--model", default=None, help="Model override (e.g. o3-mini, o1)")
    reason_parser.add_argument("--json", action="store_true", help="Output full JSON response")

    # validate-record
    val_parser = subparsers.add_parser("validate", help="Validate a JSON record against canonical schemas")
    val_parser.add_argument("--type", choices=["task", "finding", "adaptation", "evidence", "capability", "handoff"], required=True)
    val_parser.add_argument("--file", required=True, help="Path to JSON file")

    # pipeline
    pipe_parser = subparsers.add_parser("pipeline", help="Execute an inheritable multi-agent workflow pipeline")
    pipe_parser.add_argument(
        "--flavor",
        choices=["canonical", "cantina", "dispute", "delayed-weth", "multiproof-tee", "rpc-governance"],
        default="canonical",
        help="Pipeline type / domain operation",
    )
    pipe_parser.add_argument("--goal", default=None, help="Pipeline goal")
    pipe_parser.add_argument("--bounty", default=None, help="Target bounty slug")
    pipe_parser.add_argument("--target-root", default=None, help="Target directory root")
    pipe_parser.add_argument("--architecture", default=None, help="Architecture override")

    # operation
    op_parser = subparsers.add_parser("operation", help="Execute a specialized domain invariant operation pipeline")
    op_parser.add_argument(
        "--name",
        choices=["dispute", "delayed-weth", "multiproof-tee", "rpc-governance", "cantina", "canonical"],
        required=True,
        help="Operation pipeline name",
    )
    op_parser.add_argument("--goal", default=None, help="Operation goal")
    op_parser.add_argument("--bounty", default=None, help="Target bounty slug")
    op_parser.add_argument("--target-root", default=None, help="Target directory root")
    op_parser.add_argument("--architecture", default=None, help="Architecture override")

    # agent-workflow
    agent_parser = subparsers.add_parser("agent-workflow", help="Execute a specialist agent workflow step")
    agent_parser.add_argument(
        "--agent",
        choices=[
            "orchestrator",
            "analyst",
            "investigator",
            "compiler",
            "researcher",
            "reviewer",
            "engineer",
            "verifier",
            "challenger",
            "release",
            "evaluator",
            "curator",
        ],
        required=True,
        help="Specialist agent to execute",
    )
    agent_parser.add_argument("--stage", default=None, help="Stage override (e.g. INTAKE, DISCOVERY, BASELINE)")
    agent_parser.add_argument("--goal", default="Execute agent step", help="Step goal")

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    orchestrator = UniversalAdaptiveOrchestrator(workspace_root=project_root)

    if args.command == "discover":
        if getattr(args, "target_root", None) or getattr(args, "bounty", None):
            from universal_adaptive_engine.adapters.discovery import TargetDiscoveryAdapter
            disc_adapter = TargetDiscoveryAdapter(
                workspace_root=orchestrator.workspace_root,
                target_root=getattr(args, "target_root", None),
            )
            ctx = {}
            if getattr(args, "bounty", None):
                ctx["bounty_slug"] = args.bounty
            res = disc_adapter.discover(ctx)
            print(json.dumps(res["target_context"].to_dict(), indent=2))
            return 0 if res["is_valid"] else 1
        else:
            host_disc = orchestrator.host_adapter.discover()
            cantina_disc = orchestrator.cantina_adapter.discover()
            output = {"host": host_disc, "cantina": cantina_disc}
            print(json.dumps(output, indent=2))
            return 0

    elif args.command == "vertical-slice":
        goal = args.goal
        if getattr(args, "slice", None) and args.goal == "Verify host architecture integrity and canonical schemas":
            goal = f"Verify vertical slice {args.slice}"
        report = orchestrator.run_vertical_slice(goal=goal, target_file=args.target)
        print(report.to_markdown())
        return 0 if report.completion_state == "COMPLETED_VERIFIED" else 1

    elif args.command == "health-check":
        host_health = orchestrator.host_adapter.health_check()
        cantina_health = orchestrator.cantina_adapter.health_check()
        provider_health = orchestrator.reasoning_provider.health_check().to_dict() if orchestrator.reasoning_provider else {"status": "NOT_CONFIGURED"}
        output = {
            "host_adapter": host_health,
            "cantina_adapter": cantina_health,
            "reasoning_provider": provider_health,
        }
        print(json.dumps(output, indent=2))
        return 0 if (host_health["status"] == "HEALTHY" and cantina_health["status"] in ("HEALTHY", "DEGRADED")) else 1

    elif args.command == "reason":
        context_data = {}
        if args.input_file:
            inp_path = Path(args.input_file)
            if not inp_path.exists():
                print(f"Error: input file {inp_path} not found", file=sys.stderr)
                return 1
            content = inp_path.read_text(encoding="utf-8")
            try:
                context_data = json.loads(content)
            except Exception:
                context_data = {"raw_content": content}

        req = ReasoningRequest(
            prompt=args.prompt,
            purpose=ReasoningPurpose(args.purpose),
            context=context_data,
            system_instruction=args.system_instruction,
            model_override=args.model,
        )

        resp = orchestrator.reason(req)
        if args.json:
            print(json.dumps(resp.to_dict(), indent=2))
        else:
            print(f"[{resp.status.value.upper()}] Provider: {resp.provider} (Model: {resp.model})")
            if resp.content:
                print("\n" + resp.content)
            if resp.error_message:
                print(f"\nError: {resp.error_message}", file=sys.stderr)
        return 0 if resp.status == ReasoningStatus.SUCCESS else 1

    elif args.command == "pipeline":
        goal = args.goal or f"Execute {args.flavor} multi-agent workflow pipeline"
        pipe = get_operation_pipeline(
            args.flavor,
            adapter=orchestrator.cantina_adapter if args.flavor != "canonical" else orchestrator.host_adapter,
            workspace_root=orchestrator.workspace_root,
        )
        pipe_ctx = {"goal": goal}
        if getattr(args, "bounty", None):
            pipe_ctx["bounty_slug"] = args.bounty
        if getattr(args, "target_root", None):
            pipe_ctx["target_root"] = args.target_root
        if getattr(args, "architecture", None):
            pipe_ctx["architecture"] = args.architecture
        report = pipe.execute(pipe_ctx)
        print(report.to_markdown())
        return 0 if report.overall_status in ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS") else 1

    elif args.command == "operation":
        goal = args.goal or f"Execute end-to-end domain operation {args.name}"
        op_ctx = {"goal": goal}
        if getattr(args, "bounty", None):
            op_ctx["bounty_slug"] = args.bounty
        if getattr(args, "target_root", None):
            op_ctx["target_root"] = args.target_root
        if getattr(args, "architecture", None):
            op_ctx["architecture"] = args.architecture
        report = orchestrator.run_operation(args.name, goal=goal, context=op_ctx)
        print(report.to_markdown())
        return 0 if report.overall_status in ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS") else 1

    elif args.command == "agent-workflow":
        agent_map = {
            "orchestrator": OrchestratorWorkflow(orchestrator.host_adapter),
            "analyst": ArchitectureAnalystWorkflow(orchestrator.host_adapter),
            "investigator": RepositoryInvestigatorWorkflow(orchestrator.host_adapter),
            "compiler": DomainCompilerEngineerWorkflow(orchestrator.host_adapter),
            "researcher": DomainSecurityResearcherWorkflow(orchestrator.host_adapter),
            "reviewer": SecurityReviewerWorkflow(orchestrator.host_adapter),
            "engineer": ImplementationEngineerWorkflow(orchestrator.host_adapter),
            "verifier": VerificationEngineerWorkflow(orchestrator.host_adapter),
            "challenger": IndependentChallengerWorkflow(orchestrator.host_adapter),
            "release": ReleaseEngineerWorkflow(orchestrator.host_adapter),
            "evaluator": EvaluatorWorkflow(orchestrator.host_adapter),
            "curator": KnowledgeCuratorWorkflow(orchestrator.host_adapter),
        }
        wf = agent_map[args.agent]
        context = {
            "goal": args.goal,
            "stage": WorkflowStage(args.stage) if args.stage else (wf.supported_stages[0] if wf.supported_stages else WorkflowStage.INTAKE),
            "workspace_root": str(orchestrator.workspace_root),
        }
        handoff = wf.execute(context)
        print(json.dumps(handoff.to_dict(), indent=2))
        return 0 if handoff.status in ("COMPLETED_VERIFIED", "COMPLETED_WITH_LIMITATIONS") else 1

    elif args.command == "validate":
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File {path} not found", file=sys.stderr)
            return 1
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            if args.type == "task":
                rec = TaskRecord.from_dict(data)
                rec.validate()
            elif args.type == "finding":
                rec = FindingRecord.from_dict(data)
                rec.validate()
            elif args.type == "adaptation":
                rec = AdaptationRecord.from_dict(data)
                rec.validate()
            elif args.type == "evidence":
                rec = EvidenceRecord.from_dict(data)
                rec.validate()
            elif args.type == "capability":
                rec = CapabilityRecord.from_dict(data)
                rec.validate()
            elif args.type == "handoff":
                rec = HandoffRecord.from_dict(data)
                rec.validate()
            print(f"Successfully validated {args.type} record: {path}")
            return 0
        except Exception as e:
            print(f"Validation failed for {path}: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

