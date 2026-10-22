"""Task Ledger implementation with persisted state machine and audit trail."""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from universal_adaptive_engine.models.enums import TaskState, RiskLevel
from universal_adaptive_engine.models.task import TaskRecord, InvalidStateTransitionError, TaskValidationError
from universal_adaptive_engine.models.blocker import BlockerRecord


@dataclass
class LedgerEvent:
    timestamp: str
    task_id: str
    event_type: str  # "CREATED", "TRANSITION", "BLOCKED", "UPDATED"
    from_state: Optional[str]
    to_state: str
    actor: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "actor": self.actor,
            "reason": self.reason,
        }


class TaskLedger:
    """Manages tasks, validates dependencies, enforces state transitions, and records audit trails."""

    def __init__(self, persistence_path: Optional[Path | str] = None):
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self._tasks: dict[str, TaskRecord] = {}
        self._events: list[LedgerEvent] = []
        if self.persistence_path and self.persistence_path.exists():
            self.load()

    def register_task(self, task: TaskRecord, actor: str = "orchestrator") -> TaskRecord:
        """Register a new task in the ledger."""
        task.validate()
        if task.task_id in self._tasks:
            raise ValueError(f"Task with ID {task.task_id} already exists in ledger")

        self._tasks[task.task_id] = task
        self._record_event(
            task_id=task.task_id,
            event_type="CREATED",
            from_state=None,
            to_state=task.status.value,
            actor=actor,
            reason="Initial task registration",
        )
        self.save()
        return task

    def get_task(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def list_tasks(self, status: Optional[TaskState] = None) -> list[TaskRecord]:
        if status is None:
            return list(self._tasks.values())
        return [t for t in self._tasks.values() if t.status == status]

    def can_become_ready(self, task_id: str) -> tuple[bool, list[str]]:
        """Check if all task dependencies are COMPLETED_VERIFIED."""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found")

        unsatisfied = []
        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task:
                unsatisfied.append(f"Missing dependency: {dep_id}")
            elif dep_task.status not in (TaskState.COMPLETED_VERIFIED, TaskState.COMPLETED_WITH_LIMITATIONS):
                unsatisfied.append(f"Dependency {dep_id} is in state {dep_task.status.value}")

        return (len(unsatisfied) == 0, unsatisfied)

    def transition_task(
        self,
        task_id: str,
        new_state: TaskState,
        actor: str = "orchestrator",
        reason: str = ""
    ) -> TaskRecord:
        """Transition task to a new state with full dependency and invariant checks."""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found in ledger")

        # Dependency check when moving to READY
        if new_state == TaskState.READY and task.dependencies:
            can_ready, unsatisfied = self.can_become_ready(task_id)
            if not can_ready:
                raise InvalidStateTransitionError(
                    f"Cannot transition task {task_id} to READY. Unsatisfied dependencies: {unsatisfied}"
                )

        from_state = task.status.value
        task.transition_to(new_state, reason=reason)
        self._record_event(
            task_id=task_id,
            event_type="TRANSITION",
            from_state=from_state,
            to_state=new_state.value,
            actor=actor,
            reason=reason,
        )
        self.save()
        return task

    def block_task(
        self,
        task_id: str,
        blocker: BlockerRecord,
        actor: str = "orchestrator",
    ) -> TaskRecord:
        """Block a task and record the BLOCKED event in the ledger audit trail."""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found in ledger")

        from_state = task.status.value
        task.set_blocked(blocker)
        self._record_event(
            task_id=task_id,
            event_type="BLOCKED",
            from_state=from_state,
            to_state=TaskState.BLOCKED.value,
            actor=actor,
            reason=f"[{blocker.category.value}] {blocker.message}",
        )
        self.save()
        return task

    def _record_event(
        self,
        task_id: str,
        event_type: str,
        from_state: Optional[str],
        to_state: str,
        actor: str,
        reason: str
    ) -> None:
        self._events.append(
            LedgerEvent(
                timestamp=datetime.now(timezone.utc).isoformat(),
                task_id=task_id,
                event_type=event_type,
                from_state=from_state,
                to_state=to_state,
                actor=actor,
                reason=reason,
            )
        )

    def get_events(self, task_id: Optional[str] = None) -> list[LedgerEvent]:
        if task_id is None:
            return list(self._events)
        return [e for e in self._events if e.task_id == task_id]

    def save(self) -> None:
        """Persist tasks and events to file atomically."""
        if not self.persistence_path:
            return
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
            "events": [e.to_dict() for e in self._events],
        }
        temp_file = self.persistence_path.with_suffix(f".tmp.{os.getpid()}")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            os.replace(temp_file, self.persistence_path)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def load(self) -> None:
        """Load tasks and events from file with corruption resilience."""
        if not self.persistence_path or not self.persistence_path.exists():
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            self._tasks = {
                tid: TaskRecord.from_dict(tdata)
                for tid, tdata in payload.get("tasks", {}).items()
            }
            self._events = [
                LedgerEvent(**edata) for edata in payload.get("events", [])
            ]
        except (json.JSONDecodeError, OSError):
            self._tasks = {}
            self._events = []
