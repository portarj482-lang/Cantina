"""Tests for SARIFCollectionPipeline in Universal Adaptive Engine."""
from __future__ import annotations

from pathlib import Path
import pytest

from universal_adaptive_engine.workflows.operations.sarif_pipeline import (
    SARIFCollectionPipeline,
    SARIFCollectorAnalystWorkflow,
    SARIFCollectorSecurityReviewerWorkflow,
    SARIFCollectorChallengerWorkflow,
)
from universal_adaptive_engine.workflows.operations import get_operation_pipeline
from universal_adaptive_engine.workflows.base import WorkflowStage


def test_sarif_collection_pipeline_registration(tmp_path: Path):
    pipeline = get_operation_pipeline("sarif-collector", workspace_root=tmp_path)
    assert isinstance(pipeline, SARIFCollectionPipeline)
    assert pipeline.name == "Pack-B-SARIF-Collection-base"

    stage_map = {s.stage: s for s in pipeline.stages}
    assert isinstance(stage_map[WorkflowStage.DISCOVERY].workflow, SARIFCollectorAnalystWorkflow)
    assert isinstance(stage_map[WorkflowStage.AUTHORIZATION_CHECK].workflow, SARIFCollectorSecurityReviewerWorkflow)
    assert isinstance(stage_map[WorkflowStage.INDEPENDENT_REVIEW].workflow, SARIFCollectorChallengerWorkflow)
    assert stage_map[WorkflowStage.DEPLOYMENT].skip_reason is not None


def test_sarif_collector_security_reviewer_containment(tmp_path: Path):
    reviewer = SARIFCollectorSecurityReviewerWorkflow()
    context = {"workspace_root": str(tmp_path), "slug": "base", "task_id": "T1"}
    res = reviewer.run_step(context)
    assert res["status"] == "COMPLETED_VERIFIED"
    assert "path_containment_check" in res["tests"].passed


def test_sarif_collector_security_reviewer_rejection(tmp_path: Path):
    reviewer = SARIFCollectorSecurityReviewerWorkflow()
    context = {"workspace_root": str(tmp_path), "slug": "../../etc", "task_id": "T2"}
    res = reviewer.run_step(context)
    assert res["status"] == "FAILED"
    assert "path_containment_check" in res["tests"].failed
