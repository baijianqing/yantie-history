"""Create Core Alpha technical persistence foundation tables."""

from metaos.core_alpha.persistence.migration import Migration


MIGRATION = Migration(
    version=1,
    name="foundation",
    up_statements=(
        """
        CREATE TABLE core_alpha_idempotency_records (
            scope TEXT NOT NULL,
            idempotency_key TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            command_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'completed')),
            response_status INTEGER,
            response_json TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            PRIMARY KEY (scope, idempotency_key),
            CHECK (
                (status = 'pending' AND response_status IS NULL AND response_json IS NULL
                    AND completed_at IS NULL)
                OR
                (status = 'completed' AND response_status IS NOT NULL
                    AND response_json IS NOT NULL AND completed_at IS NOT NULL)
            )
        )
        """,
        """
        CREATE TABLE core_alpha_trace_events (
            event_id TEXT PRIMARY KEY,
            event_key TEXT NOT NULL UNIQUE,
            event_type_code TEXT NOT NULL,
            event_type_registry_version TEXT NOT NULL,
            aggregate_type TEXT NOT NULL,
            aggregate_id TEXT NOT NULL,
            aggregate_revision INTEGER NOT NULL CHECK (aggregate_revision >= 1),
            actor_type_code TEXT NOT NULL,
            actor_type_registry_version TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            causation_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX idx_core_alpha_trace_aggregate
        ON core_alpha_trace_events (aggregate_type, aggregate_id, aggregate_revision, occurred_at)
        """,
        """
        CREATE INDEX idx_core_alpha_trace_correlation
        ON core_alpha_trace_events (correlation_id, occurred_at)
        """,
        """
        CREATE TABLE core_alpha_outbox_records (
            outbox_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            payload_hash TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ('pending', 'dispatching', 'dispatched')),
            available_at TEXT NOT NULL,
            lease_owner TEXT,
            lease_expires_at TEXT,
            dispatch_attempt_count INTEGER NOT NULL DEFAULT 0
                CHECK (dispatch_attempt_count >= 0),
            created_at TEXT NOT NULL,
            dispatched_at TEXT,
            last_error TEXT,
            CHECK (
                status <> 'dispatching'
                OR (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
            )
        )
        """,
        """
        CREATE INDEX idx_core_alpha_outbox_claim
        ON core_alpha_outbox_records (status, available_at, lease_expires_at, created_at)
        """,
        """
        CREATE TABLE core_alpha_outbox_dispatch_attempts (
            dispatch_attempt_id TEXT PRIMARY KEY,
            outbox_id TEXT NOT NULL,
            worker_id TEXT NOT NULL,
            attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
            status TEXT NOT NULL
                CHECK (status IN ('in_progress', 'succeeded', 'failed', 'lease_expired')),
            started_at TEXT NOT NULL,
            completed_at TEXT,
            error TEXT,
            FOREIGN KEY (outbox_id) REFERENCES core_alpha_outbox_records(outbox_id)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_outbox_attempts
        ON core_alpha_outbox_dispatch_attempts (outbox_id, attempt_number)
        """,
        """
        CREATE TABLE core_alpha_lifecycle_generations (
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            generation INTEGER NOT NULL CHECK (generation >= 1),
            updated_at TEXT NOT NULL,
            PRIMARY KEY (entity_type, entity_id)
        )
        """,
        """
        CREATE TABLE core_alpha_tombstones (
            tombstone_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            lifecycle_generation INTEGER NOT NULL CHECK (lifecycle_generation >= 1),
            reason TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            deleted_at TEXT NOT NULL,
            UNIQUE (entity_type, entity_id, lifecycle_generation)
        )
        """,
        """
        CREATE INDEX idx_core_alpha_tombstone_entity
        ON core_alpha_tombstones (entity_type, entity_id, lifecycle_generation)
        """,
        """
        CREATE TABLE core_alpha_projection_checkpoints (
            projection_name TEXT PRIMARY KEY,
            checkpoint TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            updated_at TEXT NOT NULL
        )
        """,
    ),
    down_statements=(
        "DROP TABLE IF EXISTS core_alpha_projection_checkpoints",
        "DROP INDEX IF EXISTS idx_core_alpha_tombstone_entity",
        "DROP TABLE IF EXISTS core_alpha_tombstones",
        "DROP TABLE IF EXISTS core_alpha_lifecycle_generations",
        "DROP INDEX IF EXISTS idx_core_alpha_outbox_attempts",
        "DROP TABLE IF EXISTS core_alpha_outbox_dispatch_attempts",
        "DROP INDEX IF EXISTS idx_core_alpha_outbox_claim",
        "DROP TABLE IF EXISTS core_alpha_outbox_records",
        "DROP INDEX IF EXISTS idx_core_alpha_trace_correlation",
        "DROP INDEX IF EXISTS idx_core_alpha_trace_aggregate",
        "DROP TABLE IF EXISTS core_alpha_trace_events",
        "DROP TABLE IF EXISTS core_alpha_idempotency_records",
    ),
)


__all__ = ["MIGRATION"]
