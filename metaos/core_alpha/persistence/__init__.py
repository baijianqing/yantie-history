"""Core Alpha SQLite persistence foundation."""

from metaos.core_alpha.persistence.database import CoreAlphaDatabase
from metaos.core_alpha.persistence.case_scope import CaseScopeRepository
from metaos.core_alpha.persistence.migration import Migration, MigrationRunner
from metaos.core_alpha.persistence.repositories import (
    ConcurrencyConflictError,
    EventStore,
    IdempotencyConflictError,
    IdempotencyRecord,
    IdempotencyStore,
    LifecycleRecord,
    LifecycleRepository,
    OutboxLeaseError,
    OutboxRecord,
    OutboxRepository,
    PersistenceError,
    ProjectionCheckpointRecord,
    ProjectionCheckpointRepository,
    RecordNotFoundError,
    RepositoryBase,
    StaleLifecycleError,
    TombstoneRecord,
    TraceEventRecord,
)
from metaos.core_alpha.persistence.unit_of_work import UnitOfWork

__all__ = [
    "ConcurrencyConflictError",
    "CaseScopeRepository",
    "CoreAlphaDatabase",
    "EventStore",
    "IdempotencyConflictError",
    "IdempotencyRecord",
    "IdempotencyStore",
    "LifecycleRecord",
    "LifecycleRepository",
    "Migration",
    "MigrationRunner",
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
    "UnitOfWork",
]
