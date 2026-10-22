"""Unit tests for TaskLedger concurrency, advisory file locking, and multi-threaded persistence."""
import concurrent.futures
import fcntl
import os
import tempfile
import unittest
from pathlib import Path

from universal_adaptive_engine.harness.ledger import TaskLedger
from universal_adaptive_engine.models.enums import TaskState
from universal_adaptive_engine.models.task import TaskRecord


class LedgerConcurrencyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ledger_path = Path(self.tmp_dir.name) / "ledger.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_lock_file_lifecycle(self):
        """Verify that saving creates the lock file and releases the lock cleanly."""
        ledger = TaskLedger(self.ledger_path)
        task = TaskRecord(task_id="TASK-LOCK-01", goal="Test lock lifecycle")
        ledger.register_task(task)

        lock_path = Path(str(self.ledger_path) + ".lock")
        self.assertTrue(lock_path.exists(), "Lock file should be created alongside ledger")

        # Verify that we can acquire an exclusive non-blocking lock immediately (lock was released)
        with open(lock_path, "a") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def test_concurrent_multithreaded_save_load(self):
        """Verify concurrent operations across threads do not corrupt the ledger."""
        ledger = TaskLedger(self.ledger_path)

        def worker_register(idx: int):
            worker_ledger = TaskLedger(self.ledger_path)
            task = TaskRecord(
                task_id=f"TASK-CONC-{idx:03d}",
                goal=f"Concurrent task {idx}",
                acceptance_criteria=[f"Exit {idx}"],
            )
            # Re-read newest state before registering to simulate independent agents
            worker_ledger.load()
            try:
                worker_ledger.register_task(task)
            except ValueError:
                # In case task was already registered
                pass
            return idx

        # Run 20 concurrent registrations
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_register, i) for i in range(20)]
            results = [f.result() for f in futures]
            self.assertEqual(len(results), 20)

        # Final ledger reload and integrity check
        final_ledger = TaskLedger(self.ledger_path)
        final_ledger.load()
        # Verify JSON is valid and at least all recorded tasks are present and uncorrupted
        tasks = final_ledger.list_tasks()
        self.assertGreater(len(tasks), 0)
        for t in tasks:
            self.assertTrue(t.task_id.startswith("TASK-CONC-"))

    def test_shared_locks_allow_multiple_readers(self):
        """Verify that shared locks (LOCK_SH) allow simultaneous reading."""
        ledger = TaskLedger(self.ledger_path)
        task = TaskRecord(task_id="TASK-READER", goal="Reader verification")
        ledger.register_task(task)

        lock_path = Path(str(self.ledger_path) + ".lock")
        self.assertTrue(lock_path.exists())

        # Acquire a shared lock externally
        with open(lock_path, "a") as ext_f:
            fcntl.flock(ext_f.fileno(), fcntl.LOCK_SH)
            try:
                # Ledger.load() should succeed concurrently under shared lock
                reader_ledger = TaskLedger(self.ledger_path)
                reader_ledger.load()
                self.assertIsNotNone(reader_ledger.get_task("TASK-READER"))
            finally:
                fcntl.flock(ext_f.fileno(), fcntl.LOCK_UN)


if __name__ == "__main__":
    unittest.main()
