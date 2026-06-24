from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    IdempotencyConflictError,
    Migration,
    MigrationRunner,
    OutboxLeaseError,
    RecordNotFoundError,
    RepositoryBase,
    StaleLifecycleError,
    TraceEventRecord,
    UnitOfWork,
)
from metaos.core_alpha.persistence.migrations import MIGRATIONS


NOW = datetime(2026, 6, 25, 5, 0, tzinfo=timezone.utc)


def payload_hash(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class SampleRevisionRepository(RepositoryBase):
    table_name = "sample_revision_records"
    id_column = "record_id"


class CoreAlphaPersistenceFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "core-alpha.db"
        self.database = CoreAlphaDatabase(self.database_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_migration_enables_wal_and_can_roll_back_then_reapply(self) -> None:
        self.assertEqual(self.database.initialize(), [1])
        self.assertEqual(self.database.initialize(), [])
        self.assertEqual(self.database.journal_mode(), "wal")

        connection = self.database.connect()
        try:
            tables = {
                row["name"]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        finally:
            connection.close()
        self.assertIn("core_alpha_idempotency_records", tables)
        self.assertIn("core_alpha_outbox_records", tables)
        self.assertIn("core_alpha_tombstones", tables)

        self.assertEqual(self.database.rollback_last_migration(), 1)
        connection = self.database.connect()
        try:
            missing = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'core_alpha_idempotency_records'
                """
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNone(missing)
        self.assertEqual(self.database.initialize(), [1])

    def test_failed_migration_is_transactionally_rolled_back(self) -> None:
        self.database.initialize()
        failing = Migration(
            version=2,
            name="failing_test",
            up_statements=(
                "CREATE TABLE should_rollback (id TEXT PRIMARY KEY)",
                "INSERT INTO table_that_does_not_exist (id) VALUES ('x')",
            ),
            down_statements=("DROP TABLE IF EXISTS should_rollback",),
        )
        connection = self.database.connect()
        try:
            runner = MigrationRunner(connection, (*MIGRATIONS, failing))
            with self.assertRaises(sqlite3.OperationalError):
                runner.apply_all()
            table = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'should_rollback'
                """
            ).fetchone()
            self.assertIsNone(table)
            self.assertNotIn(2, runner.applied_versions())
        finally:
            connection.close()

    def test_unit_of_work_rolls_back_and_compare_and_swap_rejects_stale_revision(self) -> None:
        self.database.initialize()
        with UnitOfWork(self.database) as uow:
            uow.connection.execute(
                """
                CREATE TABLE sample_revision_records (
                    record_id TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    revision INTEGER NOT NULL
                )
                """
            )
            uow.connection.execute(
                "INSERT INTO sample_revision_records VALUES ('record_1', 'old', 1)"
            )

        with UnitOfWork(self.database) as uow:
            repository = SampleRevisionRepository(uow.connection)
            revision = repository.compare_and_swap_revision(
                "record_1",
                expected_revision=1,
                updates={"value": "new"},
            )
            self.assertEqual(revision, 2)
            with self.assertRaises(ConcurrencyConflictError):
                repository.compare_and_swap_revision(
                    "record_1",
                    expected_revision=1,
                    updates={"value": "stale"},
                )
            with self.assertRaises(RecordNotFoundError):
                repository.compare_and_swap_revision(
                    "missing",
                    expected_revision=1,
                    updates={"value": "none"},
                )

        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.database) as uow:
                uow.connection.execute(
                    "INSERT INTO sample_revision_records VALUES ('record_2', 'temp', 1)"
                )
                raise RuntimeError("force rollback")
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT 1 FROM sample_revision_records WHERE record_id = 'record_2'"
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNone(row)

    def test_idempotency_replays_first_response_and_rejects_changed_request(self) -> None:
        self.database.initialize()
        with UnitOfWork(self.database) as uow:
            record, replay = uow.idempotency.begin(
                scope="user_1:POST:/alpha/research-cases",
                idempotency_key="idem_1",
                request_hash="sha256:aaaa",
                command_id="command_1",
                created_at=NOW,
            )
            self.assertFalse(replay)
            self.assertEqual(record.status, "pending")
            completed = uow.idempotency.complete(
                scope=record.scope,
                idempotency_key=record.idempotency_key,
                request_hash=record.request_hash,
                response_status=201,
                response_body={"data": {"research_case_id": "case_1"}},
                completed_at=NOW + timedelta(seconds=1),
            )
            self.assertEqual(completed.response_status, 201)

        with UnitOfWork(self.database) as uow:
            replayed, replay = uow.idempotency.begin(
                scope="user_1:POST:/alpha/research-cases",
                idempotency_key="idem_1",
                request_hash="sha256:aaaa",
                command_id="command_2",
                created_at=NOW + timedelta(seconds=2),
            )
            self.assertTrue(replay)
            self.assertEqual(replayed.response_body["data"]["research_case_id"], "case_1")
            with self.assertRaises(IdempotencyConflictError):
                uow.idempotency.begin(
                    scope=replayed.scope,
                    idempotency_key=replayed.idempotency_key,
                    request_hash="sha256:bbbb",
                    command_id="command_3",
                    created_at=NOW,
                )

    def test_event_and_outbox_commit_atomically(self) -> None:
        self.database.initialize()
        payload = {"research_run_id": "run_1"}
        event = TraceEventRecord(
            event_id="event_1",
            event_key="command_1:run_started",
            event_type_code="run_started",
            event_type_registry_version="core-alpha-v1",
            aggregate_type="research_run",
            aggregate_id="run_1",
            aggregate_revision=1,
            actor_type_code="user",
            actor_type_registry_version="core-alpha-v1",
            actor_id="user_1",
            correlation_id="correlation_1",
            causation_id="command_1",
            trace_id="trace_1",
            payload_hash=payload_hash(payload),
            payload=payload,
            occurred_at=NOW,
        )

        with self.assertRaises(RuntimeError):
            with UnitOfWork(self.database) as uow:
                uow.events.append(event)
                uow.outbox.enqueue(
                    outbox_id="outbox_1",
                    topic="research.run",
                    payload=payload,
                    idempotency_key="outbox-idem-1",
                    available_at=NOW,
                    created_at=NOW,
                )
                raise RuntimeError("force rollback")

        with UnitOfWork(self.database, write=False) as uow:
            self.assertEqual(uow.events.list_for_aggregate("research_run", "run_1"), [])
            with self.assertRaises(RecordNotFoundError):
                uow.outbox.get("outbox_1")

        with UnitOfWork(self.database) as uow:
            uow.events.append(event)
            uow.outbox.enqueue(
                outbox_id="outbox_1",
                topic="research.run",
                payload=payload,
                idempotency_key="outbox-idem-1",
                available_at=NOW,
                created_at=NOW,
            )
        with UnitOfWork(self.database, write=False) as uow:
            self.assertEqual(len(uow.events.list_for_aggregate("research_run", "run_1")), 1)
            self.assertEqual(uow.outbox.get("outbox_1").status, "pending")

    def test_outbox_expired_lease_can_be_redelivered_at_least_once(self) -> None:
        self.database.initialize()
        with UnitOfWork(self.database) as uow:
            uow.outbox.enqueue(
                outbox_id="outbox_1",
                topic="research.run",
                payload={"run": "run_1"},
                idempotency_key="outbox-idem-1",
                available_at=NOW,
                created_at=NOW,
            )
            first = uow.outbox.claim_pending(
                worker_id="worker_1",
                now=NOW,
                lease_expires_at=NOW + timedelta(seconds=5),
            )
            self.assertEqual(first[0].dispatch_attempt_count, 1)

        with UnitOfWork(self.database) as uow:
            second = uow.outbox.claim_pending(
                worker_id="worker_2",
                now=NOW + timedelta(seconds=6),
                lease_expires_at=NOW + timedelta(seconds=12),
            )
            self.assertEqual(second[0].dispatch_attempt_count, 2)
            with self.assertRaises(OutboxLeaseError):
                uow.outbox.mark_dispatched(
                    "outbox_1",
                    worker_id="worker_1",
                    dispatched_at=NOW + timedelta(seconds=7),
                )
            uow.outbox.mark_dispatched(
                "outbox_1",
                worker_id="worker_2",
                dispatched_at=NOW + timedelta(seconds=7),
            )

        with UnitOfWork(self.database) as uow:
            self.assertEqual(
                uow.outbox.claim_pending(
                    worker_id="worker_3",
                    now=NOW + timedelta(seconds=20),
                    lease_expires_at=NOW + timedelta(seconds=30),
                ),
                [],
            )
            self.assertEqual(uow.outbox.get("outbox_1").status, "dispatched")

    def test_tombstone_advances_generation_and_blocks_late_results(self) -> None:
        self.database.initialize()
        with UnitOfWork(self.database) as uow:
            lifecycle = uow.lifecycle.ensure("research_run", "run_1", now=NOW)
            self.assertEqual(lifecycle.generation, 1)
            uow.lifecycle.assert_current("research_run", "run_1", 1)
            tombstone = uow.lifecycle.advance_with_tombstone(
                tombstone_id="tombstone_1",
                entity_type="research_run",
                entity_id="run_1",
                expected_generation=1,
                reason="Run deleted by user",
                idempotency_key="delete-run-1",
                deleted_at=NOW + timedelta(seconds=1),
            )
            self.assertEqual(tombstone.lifecycle_generation, 2)
            with self.assertRaises(StaleLifecycleError):
                uow.lifecycle.assert_current("research_run", "run_1", 1)
            with self.assertRaises(StaleLifecycleError):
                uow.lifecycle.assert_current("research_run", "run_1", 2)

        connection = self.database.connect()
        try:
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(core_alpha_tombstones)")
            }
        finally:
            connection.close()
        self.assertNotIn("question_text", columns)
        self.assertNotIn("evidence_text", columns)
        self.assertNotIn("prompt", columns)

    def test_projection_checkpoint_uses_compare_and_swap(self) -> None:
        self.database.initialize()
        with UnitOfWork(self.database) as uow:
            created = uow.projection_checkpoints.put(
                projection_name="research_trace",
                checkpoint="cursor_1",
                expected_revision=None,
                updated_at=NOW,
            )
            self.assertEqual(created.revision, 1)
            advanced = uow.projection_checkpoints.put(
                projection_name="research_trace",
                checkpoint="cursor_2",
                expected_revision=1,
                updated_at=NOW + timedelta(seconds=1),
            )
            self.assertEqual(advanced.revision, 2)
            with self.assertRaises(ConcurrencyConflictError):
                uow.projection_checkpoints.put(
                    projection_name="research_trace",
                    checkpoint="stale",
                    expected_revision=1,
                    updated_at=NOW + timedelta(seconds=2),
                )


if __name__ == "__main__":
    unittest.main()
