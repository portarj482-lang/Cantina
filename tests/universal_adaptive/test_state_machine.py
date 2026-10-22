"""Unit tests for Task state machine, transitions, dependencies, and TaskLedger."""
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.models import (
    TaskRecord,
    TaskState,
    RiskLevel,
    TaskTests,
    InvalidStateTransitionError,
    TaskValidationError,
    BlockerRecord,
    BlockerCategory,
)
from universal_adaptive_engine.harness.ledger import TaskLedger


class StateMachineTestCase(unittest.TestCase):
    def test_valid_state_transitions(self):
        task = TaskRecord(
            task_id="TASK-T01",
            goal="Execute smoke check",
            acceptance_criteria=["Exit code is 0"],
            evidence_refs=["EVID-SMOKE"],
        )
        self.assertEqual(task.status, TaskState.PROPOSED)
        self.assertEqual(task.attempt_count, 0)

        # PROPOSED -> READY
        task.transition_to(TaskState.READY)
        self.assertEqual(task.status, TaskState.READY)

        # READY -> RUNNING
        task.transition_to(TaskState.RUNNING)
        self.assertEqual(task.status, TaskState.RUNNING)
        self.assertEqual(task.attempt_count, 1)

        # RUNNING -> VERIFYING
        task.transition_to(TaskState.VERIFYING)
        self.assertEqual(task.status, TaskState.VERIFYING)

        # VERIFYING -> COMPLETED_VERIFIED
        task.transition_to(TaskState.COMPLETED_VERIFIED)
        self.assertEqual(task.status, TaskState.COMPLETED_VERIFIED)

    def test_invalid_state_transition_jump(self):
        task = TaskRecord(task_id="TASK-T02", goal="Bypass check")
        # Direct jump from PROPOSED to COMPLETED_VERIFIED must fail
        with self.assertRaises(InvalidStateTransitionError):
            task.transition_to(TaskState.COMPLETED_VERIFIED)

    def test_completed_verified_is_terminal(self):
        task = TaskRecord(
            task_id="TASK-T03",
            goal="Done task",
            status=TaskState.PROPOSED,
            acceptance_criteria=["Ok"],
            evidence_refs=["EVID-1"],
        )
        task.transition_to(TaskState.READY)
        task.transition_to(TaskState.RUNNING)
        task.transition_to(TaskState.VERIFYING)
        task.transition_to(TaskState.COMPLETED_VERIFIED)

        # Cannot move out of COMPLETED_VERIFIED
        with self.assertRaises(InvalidStateTransitionError):
            task.transition_to(TaskState.RUNNING)

    def test_completion_invariants_enforced(self):
        # Missing acceptance criteria
        task_no_criteria = TaskRecord(
            task_id="TASK-T04",
            goal="Incomplete",
            evidence_refs=["EVID-1"],
        )
        task_no_criteria.transition_to(TaskState.READY)
        task_no_criteria.transition_to(TaskState.RUNNING)
        task_no_criteria.transition_to(TaskState.VERIFYING)
        with self.assertRaises(TaskValidationError):
            task_no_criteria.transition_to(TaskState.COMPLETED_VERIFIED)

        # Failing test prevents completion
        task_failing = TaskRecord(
            task_id="TASK-T05",
            goal="Failing task",
            acceptance_criteria=["Must pass"],
            evidence_refs=["EVID-1"],
            tests=TaskTests(failed=["test_crash"]),
        )
        task_failing.transition_to(TaskState.READY)
        task_failing.transition_to(TaskState.RUNNING)
        task_failing.transition_to(TaskState.VERIFYING)
        with self.assertRaises(TaskValidationError):
            task_failing.transition_to(TaskState.COMPLETED_VERIFIED)

    def test_task_blocking_and_recovery(self):
        task = TaskRecord(task_id="TASK-T06", goal="Blocked resource task")
        task.transition_to(TaskState.READY)
        task.transition_to(TaskState.RUNNING)

        blocker = BlockerRecord.create_diagnosed(
            category=BlockerCategory.TOOL_UNAVAILABLE,
            message="Compiler solc not in PATH",
            diagnosis="solc binary missing",
            recovery_action="Use soltest Docker image or mock compiler output",
            stop_condition="Stop if neither is available",
        )
        task.set_blocked(blocker)
        self.assertEqual(task.status, TaskState.BLOCKED)
        self.assertEqual(task.blocker.category, BlockerCategory.TOOL_UNAVAILABLE)

        # Recover back to READY
        task.transition_to(TaskState.READY, reason="Alternative tool verified")
        self.assertEqual(task.status, TaskState.READY)

    def test_task_ledger_dependencies_and_audit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = Path(tmpdir) / "ledger.json"
            ledger = TaskLedger(ledger_file)

            dep_task = TaskRecord(
                task_id="TASK-DEP",
                goal="Generate keypair",
                acceptance_criteria=["Key generated"],
                evidence_refs=["EVID-KEY"],
            )
            main_task = TaskRecord(
                task_id="TASK-MAIN",
                goal="Sign message",
                dependencies=["TASK-DEP"],
                acceptance_criteria=["Message signed"],
                evidence_refs=["EVID-SIG"],
            )

            ledger.register_task(dep_task)
            ledger.register_task(main_task)

            # main_task cannot transition to READY while dep_task is PROPOSED
            with self.assertRaises(InvalidStateTransitionError):
                ledger.transition_task("TASK-MAIN", TaskState.READY)

            # Advance dep_task to COMPLETED_VERIFIED
            ledger.transition_task("TASK-DEP", TaskState.READY)
            ledger.transition_task("TASK-DEP", TaskState.RUNNING)
            ledger.transition_task("TASK-DEP", TaskState.VERIFYING)
            ledger.transition_task("TASK-DEP", TaskState.COMPLETED_VERIFIED)

            # Now main_task CAN transition to READY
            ledger.transition_task("TASK-MAIN", TaskState.READY)
            self.assertEqual(ledger.get_task("TASK-MAIN").status, TaskState.READY)

            # Verify audit trail
            events = ledger.get_events("TASK-MAIN")
            self.assertTrue(len(events) >= 2)  # CREATED, TRANSITION to READY

            # Verify persistence and reload
            loaded_ledger = TaskLedger(ledger_file)
            self.assertEqual(len(loaded_ledger.list_tasks()), 2)
            self.assertEqual(loaded_ledger.get_task("TASK-DEP").status, TaskState.COMPLETED_VERIFIED)
            self.assertEqual(loaded_ledger.get_task("TASK-MAIN").status, TaskState.READY)

    def test_verifying_can_transition_to_blocked_and_cancelled(self):
        task = TaskRecord(
            task_id="TASK-VERIFY-BLOCK",
            goal="Verification task",
            acceptance_criteria=["Check ok"],
            evidence_refs=["EVID-1"],
        )
        task.transition_to(TaskState.READY)
        task.transition_to(TaskState.RUNNING)
        task.transition_to(TaskState.VERIFYING)
        self.assertEqual(task.status, TaskState.VERIFYING)

        blocker = BlockerRecord.create_diagnosed(
            category=BlockerCategory.TOOL_UNAVAILABLE,
            message="Test runner missing in container",
            diagnosis="Runner not in PATH",
            recovery_action="Use container image",
            stop_condition="Stop if image unavailable",
        )
        task.set_blocked(blocker)
        self.assertEqual(task.status, TaskState.BLOCKED)
        self.assertEqual(task.blocker.category, BlockerCategory.TOOL_UNAVAILABLE)

        # Recovery to READY clears blocker
        task.transition_to(TaskState.READY, reason="Runner installed")
        self.assertEqual(task.status, TaskState.READY)
        self.assertIsNone(task.blocker)

    def test_completed_with_limitations_invariants(self):
        task = TaskRecord(
            task_id="TASK-LIM-01",
            goal="Task completed with limitations",
            acceptance_criteria=["Base check"],
        )
        task.transition_to(TaskState.READY)
        task.transition_to(TaskState.RUNNING)
        task.transition_to(TaskState.VERIFYING)

        # Fails without evidence refs
        with self.assertRaises(TaskValidationError):
            task.transition_to(TaskState.COMPLETED_WITH_LIMITATIONS)

        task.evidence_refs = ["EVID-LIM-1"]
        # Fails without recorded limitations
        with self.assertRaises(TaskValidationError):
            task.transition_to(TaskState.COMPLETED_WITH_LIMITATIONS)

        task.limitations = ["Network was unavailable"]
        # Succeeds when evidence and limitations are provided
        task.transition_to(TaskState.COMPLETED_WITH_LIMITATIONS)
        self.assertEqual(task.status, TaskState.COMPLETED_WITH_LIMITATIONS)

    def test_ledger_block_task_records_blocked_audit_event(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = Path(tmpdir) / "ledger.json"
            ledger = TaskLedger(ledger_file)
            task = TaskRecord(task_id="TASK-AUDIT-BLOCK", goal="Task to be blocked")
            ledger.register_task(task)
            ledger.transition_task("TASK-AUDIT-BLOCK", TaskState.READY)
            ledger.transition_task("TASK-AUDIT-BLOCK", TaskState.RUNNING)

            blocker = BlockerRecord.create_diagnosed(
                category=BlockerCategory.PERMISSION_DENIED,
                message="Cannot access /secret",
                diagnosis="Root permission required",
                recovery_action="Operate in sandbox",
                stop_condition="Do not retry /secret",
                recoverable=False,
            )
            blocked_task = ledger.block_task("TASK-AUDIT-BLOCK", blocker)
            self.assertEqual(blocked_task.status, TaskState.BLOCKED)

            events = ledger.get_events("TASK-AUDIT-BLOCK")
            blocked_events = [e for e in events if e.event_type == "BLOCKED"]
            self.assertEqual(len(blocked_events), 1)
            self.assertEqual(blocked_events[0].to_state, "BLOCKED")
            self.assertIn("PERMISSION_DENIED", blocked_events[0].reason)


if __name__ == "__main__":
    unittest.main()
