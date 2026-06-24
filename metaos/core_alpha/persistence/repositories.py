"""Technical repositories shared by Core Alpha application commands."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")


class PersistenceError(RuntimeError):
    """Base class for Core Alpha persistence failures."""


class RecordNotFoundError(PersistenceError):
    pass


class ConcurrencyConflictError(PersistenceError):
    pass


class IdempotencyConflictError(PersistenceError):
    pass


class StaleLifecycleError(PersistenceError):
    pass


class OutboxLeaseError(PersistenceError):
    pass


def _utc_iso(value: datetime) -> str:
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("persistence timestamps must use UTC offset +00:00")
    return value.isoformat()


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value is not None else None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _payload_hash(payload_json: str) -> str:
    return f"sha256:{hashlib.sha256(payload_json.encode('utf-8')).hexdigest()}"


class RepositoryBase:
    table_name: str
    id_column: str

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._validate_identifier(self.table_name)
        self._validate_identifier(self.id_column)

    def compare_and_swap_revision(
        self,
        record_id: str,
        *,
        expected_revision: int,
        updates: Mapping[str, Any],
    ) -> int:
        if expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        if not updates:
            raise ValueError("compare-and-swap requires at least one update")
        if "revision" in updates or self.id_column in updates:
            raise ValueError("identity and revision cannot be supplied as update fields")
        for column in updates:
            self._validate_identifier(column)

        assignments = [f"{column} = ?" for column in updates]
        assignments.append("revision = ?")
        next_revision = expected_revision + 1
        parameters = [*updates.values(), next_revision, record_id, expected_revision]
        cursor = self.connection.execute(
            f"""
            UPDATE {self.table_name}
            SET {', '.join(assignments)}
            WHERE {self.id_column} = ? AND revision = ?
            """,
            parameters,
        )
        if cursor.rowcount == 1:
            return next_revision
        exists = self.connection.execute(
            f"SELECT 1 FROM {self.table_name} WHERE {self.id_column} = ?",
            (record_id,),
        ).fetchone()
        if exists is None:
            raise RecordNotFoundError(f"record not found: {record_id}")
        raise ConcurrencyConflictError(
            f"revision conflict for {record_id}: expected {expected_revision}"
        )

    @staticmethod
    def _validate_identifier(value: str) -> None:
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError(f"unsafe SQLite identifier: {value!r}")


@dataclass(frozen=True)
class IdempotencyRecord:
    scope: str
    idempotency_key: str
    request_hash: str
    command_id: str
    status: str
    response_status: int | None
    response_body: Any | None
    created_at: datetime
    completed_at: datetime | None


class IdempotencyStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def begin(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_hash: str,
        command_id: str,
        created_at: datetime,
    ) -> tuple[IdempotencyRecord, bool]:
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO core_alpha_idempotency_records (
                scope, idempotency_key, request_hash, command_id, status, created_at
            ) VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (scope, idempotency_key, request_hash, command_id, _utc_iso(created_at)),
        )
        record = self.get(scope, idempotency_key)
        if record.request_hash != request_hash:
            raise IdempotencyConflictError(
                "the idempotency key was already used with a different request"
            )
        is_replay = cursor.rowcount == 0
        return record, is_replay

    def complete(
        self,
        *,
        scope: str,
        idempotency_key: str,
        request_hash: str,
        response_status: int,
        response_body: Any,
        completed_at: datetime,
    ) -> IdempotencyRecord:
        existing = self.get(scope, idempotency_key)
        if existing.request_hash != request_hash:
            raise IdempotencyConflictError(
                "the idempotency key was already used with a different request"
            )
        if existing.status == "completed":
            return existing
        self.connection.execute(
            """
            UPDATE core_alpha_idempotency_records
            SET status = 'completed', response_status = ?, response_json = ?, completed_at = ?
            WHERE scope = ? AND idempotency_key = ? AND status = 'pending'
            """,
            (
                response_status,
                _canonical_json(response_body),
                _utc_iso(completed_at),
                scope,
                idempotency_key,
            ),
        )
        return self.get(scope, idempotency_key)

    def get(self, scope: str, idempotency_key: str) -> IdempotencyRecord:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_idempotency_records
            WHERE scope = ? AND idempotency_key = ?
            """,
            (scope, idempotency_key),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"idempotency record not found: {scope}/{idempotency_key}")
        return IdempotencyRecord(
            scope=row["scope"],
            idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"],
            command_id=row["command_id"],
            status=row["status"],
            response_status=row["response_status"],
            response_body=json.loads(row["response_json"]) if row["response_json"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=_datetime(row["completed_at"]),
        )


@dataclass(frozen=True)
class TraceEventRecord:
    event_id: str
    event_key: str
    event_type_code: str
    event_type_registry_version: str
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    actor_type_code: str
    actor_type_registry_version: str
    actor_id: str
    correlation_id: str
    causation_id: str
    trace_id: str
    payload_hash: str
    payload: Any
    occurred_at: datetime


class EventStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def append(self, event: TraceEventRecord) -> None:
        payload_json = _canonical_json(event.payload)
        if _payload_hash(payload_json) != event.payload_hash:
            raise ValueError("event payload_hash does not match payload")
        self.connection.execute(
            """
            INSERT INTO core_alpha_trace_events (
                event_id, event_key, event_type_code, event_type_registry_version,
                aggregate_type, aggregate_id, aggregate_revision,
                actor_type_code, actor_type_registry_version, actor_id,
                correlation_id, causation_id, trace_id,
                payload_hash, payload_json, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_key,
                event.event_type_code,
                event.event_type_registry_version,
                event.aggregate_type,
                event.aggregate_id,
                event.aggregate_revision,
                event.actor_type_code,
                event.actor_type_registry_version,
                event.actor_id,
                event.correlation_id,
                event.causation_id,
                event.trace_id,
                event.payload_hash,
                payload_json,
                _utc_iso(event.occurred_at),
            ),
        )

    def list_for_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[TraceEventRecord]:
        rows = self.connection.execute(
            """
            SELECT * FROM core_alpha_trace_events
            WHERE aggregate_type = ? AND aggregate_id = ?
            ORDER BY aggregate_revision, occurred_at, event_id
            """,
            (aggregate_type, aggregate_id),
        ).fetchall()
        return [self._record(row) for row in rows]

    @staticmethod
    def _record(row: sqlite3.Row) -> TraceEventRecord:
        return TraceEventRecord(
            event_id=row["event_id"],
            event_key=row["event_key"],
            event_type_code=row["event_type_code"],
            event_type_registry_version=row["event_type_registry_version"],
            aggregate_type=row["aggregate_type"],
            aggregate_id=row["aggregate_id"],
            aggregate_revision=row["aggregate_revision"],
            actor_type_code=row["actor_type_code"],
            actor_type_registry_version=row["actor_type_registry_version"],
            actor_id=row["actor_id"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
            trace_id=row["trace_id"],
            payload_hash=row["payload_hash"],
            payload=json.loads(row["payload_json"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
        )


@dataclass(frozen=True)
class OutboxRecord:
    outbox_id: str
    topic: str
    payload_hash: str
    payload: Any
    idempotency_key: str
    status: str
    available_at: datetime
    lease_owner: str | None
    lease_expires_at: datetime | None
    dispatch_attempt_count: int
    created_at: datetime
    dispatched_at: datetime | None
    last_error: str | None


class OutboxRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def enqueue(
        self,
        *,
        outbox_id: str,
        topic: str,
        payload: Any,
        idempotency_key: str,
        available_at: datetime,
        created_at: datetime,
    ) -> OutboxRecord:
        payload_json = _canonical_json(payload)
        payload_hash = _payload_hash(payload_json)
        self.connection.execute(
            """
            INSERT OR IGNORE INTO core_alpha_outbox_records (
                outbox_id, topic, payload_hash, payload_json, idempotency_key,
                status, available_at, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                outbox_id,
                topic,
                payload_hash,
                payload_json,
                idempotency_key,
                _utc_iso(available_at),
                _utc_iso(created_at),
            ),
        )
        record = self.get_by_idempotency_key(idempotency_key)
        if record.payload_hash != payload_hash or record.topic != topic:
            raise IdempotencyConflictError(
                "the outbox idempotency key was already used for another message"
            )
        return record

    def claim_pending(
        self,
        *,
        worker_id: str,
        now: datetime,
        lease_expires_at: datetime,
        limit: int = 10,
    ) -> list[OutboxRecord]:
        if limit < 1:
            raise ValueError("claim limit must be positive")
        if lease_expires_at <= now:
            raise ValueError("lease_expires_at must be later than now")
        now_iso = _utc_iso(now)
        candidates = self.connection.execute(
            """
            SELECT outbox_id
            FROM core_alpha_outbox_records
            WHERE dispatched_at IS NULL
              AND available_at <= ?
              AND (
                  status = 'pending'
                  OR (status = 'dispatching' AND lease_expires_at <= ?)
              )
            ORDER BY created_at, outbox_id
            LIMIT ?
            """,
            (now_iso, now_iso, limit),
        ).fetchall()
        claimed: list[OutboxRecord] = []
        for candidate in candidates:
            outbox_id = candidate["outbox_id"]
            self.connection.execute(
                """
                UPDATE core_alpha_outbox_dispatch_attempts
                SET status = 'lease_expired', completed_at = ?
                WHERE outbox_id = ? AND status = 'in_progress'
                """,
                (now_iso, outbox_id),
            )
            cursor = self.connection.execute(
                """
                UPDATE core_alpha_outbox_records
                SET status = 'dispatching', lease_owner = ?, lease_expires_at = ?,
                    dispatch_attempt_count = dispatch_attempt_count + 1
                WHERE outbox_id = ? AND dispatched_at IS NULL AND (
                    status = 'pending'
                    OR (status = 'dispatching' AND lease_expires_at <= ?)
                )
                """,
                (worker_id, _utc_iso(lease_expires_at), outbox_id, now_iso),
            )
            if cursor.rowcount != 1:
                continue
            record = self.get(outbox_id)
            self.connection.execute(
                """
                INSERT INTO core_alpha_outbox_dispatch_attempts (
                    dispatch_attempt_id, outbox_id, worker_id, attempt_number,
                    status, started_at
                ) VALUES (?, ?, ?, ?, 'in_progress', ?)
                """,
                (
                    f"dispatch_attempt_{uuid.uuid4().hex}",
                    outbox_id,
                    worker_id,
                    record.dispatch_attempt_count,
                    now_iso,
                ),
            )
            claimed.append(record)
        return claimed

    def mark_dispatched(self, outbox_id: str, *, worker_id: str, dispatched_at: datetime) -> None:
        completed_iso = _utc_iso(dispatched_at)
        cursor = self.connection.execute(
            """
            UPDATE core_alpha_outbox_records
            SET status = 'dispatched', dispatched_at = ?, lease_owner = NULL,
                lease_expires_at = NULL, last_error = NULL
            WHERE outbox_id = ? AND status = 'dispatching' AND lease_owner = ?
            """,
            (completed_iso, outbox_id, worker_id),
        )
        if cursor.rowcount != 1:
            raise OutboxLeaseError("outbox record is not leased by this worker")
        self.connection.execute(
            """
            UPDATE core_alpha_outbox_dispatch_attempts
            SET status = 'succeeded', completed_at = ?
            WHERE outbox_id = ? AND worker_id = ? AND status = 'in_progress'
            """,
            (completed_iso, outbox_id, worker_id),
        )

    def mark_failed(
        self,
        outbox_id: str,
        *,
        worker_id: str,
        error: str,
        failed_at: datetime,
        retry_at: datetime,
    ) -> None:
        failed_iso = _utc_iso(failed_at)
        cursor = self.connection.execute(
            """
            UPDATE core_alpha_outbox_records
            SET status = 'pending', available_at = ?, lease_owner = NULL,
                lease_expires_at = NULL, last_error = ?
            WHERE outbox_id = ? AND status = 'dispatching' AND lease_owner = ?
            """,
            (_utc_iso(retry_at), error, outbox_id, worker_id),
        )
        if cursor.rowcount != 1:
            raise OutboxLeaseError("outbox record is not leased by this worker")
        self.connection.execute(
            """
            UPDATE core_alpha_outbox_dispatch_attempts
            SET status = 'failed', completed_at = ?, error = ?
            WHERE outbox_id = ? AND worker_id = ? AND status = 'in_progress'
            """,
            (failed_iso, error, outbox_id, worker_id),
        )

    def get(self, outbox_id: str) -> OutboxRecord:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_outbox_records WHERE outbox_id = ?",
            (outbox_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"outbox record not found: {outbox_id}")
        return self._record(row)

    def get_by_idempotency_key(self, idempotency_key: str) -> OutboxRecord:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_outbox_records WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"outbox idempotency key not found: {idempotency_key}")
        return self._record(row)

    @staticmethod
    def _record(row: sqlite3.Row) -> OutboxRecord:
        return OutboxRecord(
            outbox_id=row["outbox_id"],
            topic=row["topic"],
            payload_hash=row["payload_hash"],
            payload=json.loads(row["payload_json"]),
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            available_at=datetime.fromisoformat(row["available_at"]),
            lease_owner=row["lease_owner"],
            lease_expires_at=_datetime(row["lease_expires_at"]),
            dispatch_attempt_count=row["dispatch_attempt_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            dispatched_at=_datetime(row["dispatched_at"]),
            last_error=row["last_error"],
        )


@dataclass(frozen=True)
class LifecycleRecord:
    entity_type: str
    entity_id: str
    generation: int
    updated_at: datetime


@dataclass(frozen=True)
class TombstoneRecord:
    tombstone_id: str
    entity_type: str
    entity_id: str
    lifecycle_generation: int
    reason: str
    idempotency_key: str
    deleted_at: datetime


class LifecycleRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure(self, entity_type: str, entity_id: str, *, now: datetime) -> LifecycleRecord:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO core_alpha_lifecycle_generations (
                entity_type, entity_id, generation, updated_at
            ) VALUES (?, ?, 1, ?)
            """,
            (entity_type, entity_id, _utc_iso(now)),
        )
        return self.get(entity_type, entity_id)

    def advance_with_tombstone(
        self,
        *,
        tombstone_id: str,
        entity_type: str,
        entity_id: str,
        expected_generation: int,
        reason: str,
        idempotency_key: str,
        deleted_at: datetime,
    ) -> TombstoneRecord:
        next_generation = expected_generation + 1
        cursor = self.connection.execute(
            """
            UPDATE core_alpha_lifecycle_generations
            SET generation = ?, updated_at = ?
            WHERE entity_type = ? AND entity_id = ? AND generation = ?
            """,
            (
                next_generation,
                _utc_iso(deleted_at),
                entity_type,
                entity_id,
                expected_generation,
            ),
        )
        if cursor.rowcount != 1:
            raise StaleLifecycleError("lifecycle generation does not match")
        self.connection.execute(
            """
            INSERT INTO core_alpha_tombstones (
                tombstone_id, entity_type, entity_id, lifecycle_generation,
                reason, idempotency_key, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tombstone_id,
                entity_type,
                entity_id,
                next_generation,
                reason,
                idempotency_key,
                _utc_iso(deleted_at),
            ),
        )
        return self.get_tombstone(tombstone_id)

    def assert_current(self, entity_type: str, entity_id: str, expected_generation: int) -> None:
        record = self.get(entity_type, entity_id)
        tombstoned = self.connection.execute(
            """
            SELECT 1 FROM core_alpha_tombstones
            WHERE entity_type = ? AND entity_id = ? AND lifecycle_generation = ?
            """,
            (entity_type, entity_id, record.generation),
        ).fetchone()
        if record.generation != expected_generation or tombstoned is not None:
            raise StaleLifecycleError("lifecycle generation is stale or tombstoned")

    def get(self, entity_type: str, entity_id: str) -> LifecycleRecord:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_lifecycle_generations
            WHERE entity_type = ? AND entity_id = ?
            """,
            (entity_type, entity_id),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"lifecycle record not found: {entity_type}/{entity_id}")
        return LifecycleRecord(
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            generation=row["generation"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_tombstone(self, tombstone_id: str) -> TombstoneRecord:
        row = self.connection.execute(
            "SELECT * FROM core_alpha_tombstones WHERE tombstone_id = ?",
            (tombstone_id,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"tombstone not found: {tombstone_id}")
        return TombstoneRecord(
            tombstone_id=row["tombstone_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            lifecycle_generation=row["lifecycle_generation"],
            reason=row["reason"],
            idempotency_key=row["idempotency_key"],
            deleted_at=datetime.fromisoformat(row["deleted_at"]),
        )


@dataclass(frozen=True)
class ProjectionCheckpointRecord:
    projection_name: str
    checkpoint: str
    revision: int
    updated_at: datetime


class ProjectionCheckpointRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def put(
        self,
        *,
        projection_name: str,
        checkpoint: str,
        expected_revision: int | None,
        updated_at: datetime,
    ) -> ProjectionCheckpointRecord:
        existing = self.connection.execute(
            """
            SELECT revision FROM core_alpha_projection_checkpoints
            WHERE projection_name = ?
            """,
            (projection_name,),
        ).fetchone()
        if existing is None:
            if expected_revision is not None:
                raise ConcurrencyConflictError("projection checkpoint does not exist")
            self.connection.execute(
                """
                INSERT INTO core_alpha_projection_checkpoints (
                    projection_name, checkpoint, revision, updated_at
                ) VALUES (?, ?, 1, ?)
                """,
                (projection_name, checkpoint, _utc_iso(updated_at)),
            )
        else:
            if expected_revision is None or existing["revision"] != expected_revision:
                raise ConcurrencyConflictError("projection checkpoint revision conflict")
            cursor = self.connection.execute(
                """
                UPDATE core_alpha_projection_checkpoints
                SET checkpoint = ?, revision = revision + 1, updated_at = ?
                WHERE projection_name = ? AND revision = ?
                """,
                (checkpoint, _utc_iso(updated_at), projection_name, expected_revision),
            )
            if cursor.rowcount != 1:
                raise ConcurrencyConflictError("projection checkpoint revision conflict")
        return self.get(projection_name)

    def get(self, projection_name: str) -> ProjectionCheckpointRecord:
        row = self.connection.execute(
            """
            SELECT * FROM core_alpha_projection_checkpoints
            WHERE projection_name = ?
            """,
            (projection_name,),
        ).fetchone()
        if row is None:
            raise RecordNotFoundError(f"projection checkpoint not found: {projection_name}")
        return ProjectionCheckpointRecord(
            projection_name=row["projection_name"],
            checkpoint=row["checkpoint"],
            revision=row["revision"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


__all__ = [
    "ConcurrencyConflictError",
    "EventStore",
    "IdempotencyConflictError",
    "IdempotencyRecord",
    "IdempotencyStore",
    "LifecycleRecord",
    "LifecycleRepository",
    "OutboxLeaseError",
    "OutboxRecord",
    "OutboxRepository",
    "PersistenceError",
    "ProjectionCheckpointRecord",
    "ProjectionCheckpointRepository",
    "RecordNotFoundError",
    "RepositoryBase",
    "StaleLifecycleError",
    "TombstoneRecord",
    "TraceEventRecord",
]
