"""Unit tests for Canonical Schemas (TaskRecord, FindingRecord, AdaptationRecord, EvidenceRecord, CapabilityRecord)."""
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.models import (
    TaskRecord,
    TaskState,
    RiskLevel,
    TaskTests,
    TaskValidationError,
    FindingRecord,
    FindingStatus,
    LocationRef,
    ImpactLevel,
    ExploitabilityLevel,
    ConfidenceLevel,
    FindingValidationError,
    AdaptationRecord,
    CandidateType,
    AdaptationDecision,
    CompatibilityMatrix,
    AdaptationValidationError,
    EvidenceRecord,
    EvidenceType,
    EvidenceValidationError,
    CapabilityRecord,
    CapabilityStatus,
    CapabilityValidationError,
    BlockerRecord,
    BlockerCategory,
    ResultStatus,
    ResolutionStatus,
)


class CanonicalSchemasTestCase(unittest.TestCase):
    def test_valid_task_record(self):
        task = TaskRecord(
            task_id="TASK-0001",
            goal="Establish host baseline",
            status=TaskState.PROPOSED,
            owner="orchestrator",
            assigned_role="Architecture Analyst",
            dependencies=[],
            inputs=["workspace_root"],
            expected_artifacts=["baseline.json"],
            acceptance_criteria=["Baseline JSON contains OS and Python version"],
            permissions_required=["filesystem.read"],
            risk_level=RiskLevel.LOW,
            attempt_count=0,
            evidence_refs=["EVID-0001"],
            tests=TaskTests(passed=["test_baseline"]),
            limitations=["Read-only checks"],
            next_action="Run discovery",
        )
        task.validate()
        d = task.to_dict()
        self.assertEqual(d["task_id"], "TASK-0001")
        self.assertEqual(d["status"], "PROPOSED")

        # Roundtrip
        restored = TaskRecord.from_dict(d)
        self.assertEqual(restored.task_id, task.task_id)
        self.assertEqual(restored.status, task.status)
        self.assertEqual(restored.risk_level, task.risk_level)

    def test_invalid_task_record_empty_goal(self):
        task = TaskRecord(task_id="TASK-0002", goal="   ")
        with self.assertRaises(TaskValidationError):
            task.validate()

    def test_task_with_diagnosed_blocker(self):
        blocker = BlockerRecord.create_diagnosed(
            category=BlockerCategory.PERMISSION_DENIED,
            message="Cannot write to /root",
            diagnosis="Access denied on system directory",
            recovery_action="Switch to workspace scratch dir",
            stop_condition="Do not retry /root",
            recoverable=False,
        )
        task = TaskRecord(
            task_id="TASK-0003",
            goal="Write temp artifact",
            status=TaskState.BLOCKED,
            blocker=blocker,
        )
        task.validate()
        d = task.to_dict()
        self.assertIsNotNone(d["blocker"])
        self.assertEqual(d["blocker"]["category"], "PERMISSION_DENIED")

    def test_valid_finding_record(self):
        finding = FindingRecord(
            finding_id="FIND-0001",
            title="Reentrancy vulnerable withdraw function",
            status=FindingStatus.CANDIDATE,
            source_refs=["[SRC: contracts/Vault.sol:45 @e004a]"],
            affected_versions=["1.0.0"],
            locations=[LocationRef(path="contracts/Vault.sol", start_line=45, end_line=55, symbol="withdraw")],
            original_labels=["S"],
            derived_labels=["reentrancy", "state_update_after_transfer"],
            preconditions=["Attacker must possess non-zero balance"],
            security_property="CEI (Checks-Effects-Interactions) invariant",
            root_cause="External call executed prior to balance zeroing",
            impact=ImpactLevel.HIGH,
            exploitability=ExploitabilityLevel.UNVERIFIED,
            confidence=ConfidenceLevel.MEDIUM,
            unresolved_assumptions=["Reentrancy lock might exist in parent contract"],
        )
        finding.validate()
        d = finding.to_dict()
        self.assertEqual(d["finding_id"], "FIND-0001")
        self.assertEqual(d["impact"], "high")

        # Roundtrip
        restored = FindingRecord.from_dict(d)
        self.assertEqual(restored.finding_id, finding.finding_id)
        self.assertEqual(restored.status, finding.status)

    def test_finding_demonstrated_without_reproduction_fails(self):
        finding = FindingRecord(
            finding_id="FIND-0002",
            title="Unchecked call return",
            status=FindingStatus.CANDIDATE,
            source_refs=["[SRC: Vault.sol]"],
            exploitability=ExploitabilityLevel.DEMONSTRATED,
            reproduction_refs=[],  # Empty!
        )
        with self.assertRaises(FindingValidationError):
            finding.validate()

    def test_finding_supported_without_source_fails(self):
        finding = FindingRecord(
            finding_id="FIND-0003",
            title="Slippage missing",
            status=FindingStatus.SUPPORTED,
            source_refs=[],  # Empty!
            confidence=ConfidenceLevel.HIGH,
        )
        with self.assertRaises(FindingValidationError):
            finding.validate()

    def test_valid_adaptation_record(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0001",
            candidate_type=CandidateType.TOOL,
            license="Apache-2.0",
            intended_capability="Slither AST static analyzer adapter",
            rationale="Allows automated detection of known Solidity antipatterns",
            compatibility=CompatibilityMatrix(
                contracts="compatible",
                dependencies="compatible",
                security="passed",
                regressions="none_observed",
            ),
            protected_core_changed=False,
            shared_contracts_changed=False,
            approval_required=False,
            decision=AdaptationDecision.ACCEPTED_FOR_STAGING,
        )
        adaptation.validate()
        d = adaptation.to_dict()
        self.assertEqual(d["candidate_id"], "ADAPT-0001")
        self.assertEqual(d["decision"], "ACCEPTED_FOR_STAGING")

    def test_adaptation_production_without_rollback_fails(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0002",
            candidate_type=CandidateType.TOOL,
            license="MIT",
            intended_capability="Core state updater",
            rationale="Update task state mechanism",
            compatibility=CompatibilityMatrix(security="passed", regressions="none_observed"),
            approval_required=True,
            approval_ref="AUTH-ADMIN-01",
            decision=AdaptationDecision.ACCEPTED_FOR_PRODUCTION,
            rollback_ref=None,  # Missing rollback!
        )
        with self.assertRaises(AdaptationValidationError):
            adaptation.validate()

    def test_adaptation_production_with_unpassed_security_fails(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0003",
            candidate_type=CandidateType.SKILL,
            license="MIT",
            intended_capability="External web scraper",
            rationale="Scrapes forum",
            compatibility=CompatibilityMatrix(security="not_checked", regressions="none_observed"),
            approval_required=True,
            approval_ref="AUTH-ADMIN-01",
            decision=AdaptationDecision.ACCEPTED_FOR_PRODUCTION,
            rollback_ref="git:revert-001",
        )
        with self.assertRaises(AdaptationValidationError):
            adaptation.validate()

    def test_evidence_record_and_file_hashing(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
            tmp.write("Hello evidence\n")
            tmp_path = Path(tmp.name)

        try:
            sha256 = EvidenceRecord.hash_artifact(tmp_path)
            evid = EvidenceRecord(
                evidence_id="EVID-0001",
                evidence_type=EvidenceType.OBSERVED,
                source_ref=str(tmp_path),
                artifact_path=str(tmp_path),
                sha256=sha256,
                acquisition_method="file_read",
                observed_result="Hello evidence present",
                confidence=ConfidenceLevel.VERIFIED,
            )
            evid.validate()

            # Mismatched hash fails validation
            bad_evid = EvidenceRecord(
                evidence_id="EVID-0002",
                evidence_type=EvidenceType.OBSERVED,
                source_ref=str(tmp_path),
                artifact_path=str(tmp_path),
                sha256="0" * 64,
                acquisition_method="file_read",
                observed_result="Tampered hash",
                confidence=ConfidenceLevel.VERIFIED,
            )
            with self.assertRaises(EvidenceValidationError):
                bad_evid.validate()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_capability_record(self):
        cap = CapabilityRecord(
            capability_id="compiler.solc",
            display_name="Solidity Compiler 0.8.28",
            status=CapabilityStatus.VERIFIED,
            permissions_required=["subprocess.exec"],
            inputs=["source.sol"],
            outputs=["ast.json", "bin"],
            dependencies=[],
            evidence_refs=["EVID-SOLC-VERSION"],
            limitations=["Requires standard-json API for AST generation"],
        )
        cap.validate()

        # Capability marked VERIFIED without evidence fails
        bad_cap = CapabilityRecord(
            capability_id="compiler.solc.bad",
            display_name="Solc",
            status=CapabilityStatus.VERIFIED,
            evidence_refs=[],  # Missing!
        )
        with self.assertRaises(CapabilityValidationError):
            bad_cap.validate()

    def test_adaptation_production_with_incompatible_contracts_fails(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0004",
            candidate_type=CandidateType.ADAPTER,
            license="MIT",
            intended_capability="Incompatible adapter",
            rationale="Test",
            compatibility=CompatibilityMatrix(
                contracts="incompatible",
                dependencies="compatible",
                security="passed",
                regressions="none_observed",
            ),
            baseline_ref="BASE-001",
            approval_ref="AUTH-ADMIN",
            rollback_ref="git:revert",
            decision=AdaptationDecision.ACCEPTED_FOR_PRODUCTION,
        )
        with self.assertRaises(AdaptationValidationError):
            adaptation.validate()

    def test_adaptation_staging_with_failed_security_fails(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0005",
            candidate_type=CandidateType.TOOL,
            license="MIT",
            intended_capability="Dangerous tool",
            rationale="Test",
            compatibility=CompatibilityMatrix(
                contracts="compatible",
                security="failed",
            ),
            decision=AdaptationDecision.ACCEPTED_FOR_STAGING,
        )
        with self.assertRaises(AdaptationValidationError):
            adaptation.validate()

    def test_adaptation_production_without_baseline_fails(self):
        adaptation = AdaptationRecord(
            candidate_id="ADAPT-0006",
            candidate_type=CandidateType.TOOL,
            license="MIT",
            intended_capability="Unbaselined tool",
            rationale="Test",
            compatibility=CompatibilityMatrix(
                contracts="compatible",
                dependencies="compatible",
                security="passed",
                regressions="none_observed",
            ),
            approval_ref="AUTH-ADMIN",
            rollback_ref="git:revert",
            baseline_ref=None,
            candidate_evaluation_ref=None,
            decision=AdaptationDecision.ACCEPTED_FOR_PRODUCTION,
        )
        with self.assertRaises(AdaptationValidationError):
            adaptation.validate()

    def test_finding_accepted_without_source_fails(self):
        finding = FindingRecord(
            finding_id="FIND-0010",
            title="Accepted finding without source",
            status=FindingStatus.ACCEPTED,
            source_refs=[],
            confidence=ConfidenceLevel.VERIFIED,
        )
        with self.assertRaises(FindingValidationError):
            finding.validate()

    def test_finding_refuted_with_verified_confidence_fails(self):
        finding = FindingRecord(
            finding_id="FIND-0011",
            title="Refuted finding with verified confidence",
            status=FindingStatus.REFUTED,
            source_refs=["[SRC: test.sol]"],
            counterevidence_refs=["EVID-COUNTER"],
            confidence=ConfidenceLevel.VERIFIED,
        )
        with self.assertRaises(FindingValidationError):
            finding.validate()

    def test_finding_refuted_without_counterevidence_fails(self):
        finding = FindingRecord(
            finding_id="FIND-0012",
            title="Refuted finding without counterevidence",
            status=FindingStatus.REFUTED,
            source_refs=["[SRC: test.sol]"],
            counterevidence_refs=[],
            confidence=ConfidenceLevel.REFUTED,
        )
        with self.assertRaises(FindingValidationError):
            finding.validate()


    def test_result_and_resolution_status_enums(self):
        """Verify ResultStatus and ResolutionStatus conform to USAP_Codable_Refactor spec."""
        self.assertEqual(ResultStatus.PASS, "PASS")
        self.assertEqual(ResultStatus.FAIL, "FAIL")
        self.assertEqual(ResultStatus.BLOCKED, "BLOCKED")
        self.assertEqual(ResultStatus.NOT_APPLICABLE, "NOT_APPLICABLE")
        self.assertEqual(ResultStatus.NOT_VERIFIED, "NOT_VERIFIED")

        self.assertEqual(ResolutionStatus.CONFIRMED, "CONFIRMED")
        self.assertEqual(ResolutionStatus.PARTIAL, "PARTIAL")
        self.assertEqual(ResolutionStatus.AMBIGUOUS, "AMBIGUOUS")
        self.assertEqual(ResolutionStatus.UNSUPPORTED, "UNSUPPORTED")
        self.assertEqual(ResolutionStatus.INVALID, "INVALID")


if __name__ == "__main__":
    unittest.main()
