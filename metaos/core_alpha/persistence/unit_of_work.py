"""Explicit short transaction boundary for Core Alpha repositories."""

from __future__ import annotations

import sqlite3
from types import TracebackType

from metaos.core_alpha.persistence.database import CoreAlphaDatabase
from metaos.core_alpha.persistence.repositories import (
    EventStore,
    IdempotencyStore,
    LifecycleRepository,
    OutboxRepository,
    ProjectionCheckpointRepository,
)


class UnitOfWork:
    def __init__(self, database: CoreAlphaDatabase, *, write: bool = True):
        self.database = database
        self.write = write
        self._connection: sqlite3.Connection | None = None
        self._finished = False

    def __enter__(self) -> "UnitOfWork":
        if self._connection is not None:
            raise RuntimeError("UnitOfWork cannot be entered twice")
        self._connection = self.database.connect()
        self._connection.execute("BEGIN IMMEDIATE" if self.write else "BEGIN")
        self._finished = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        try:
            if not self._finished:
                if exc_type is None:
                    self.connection.commit()
                else:
                    self.connection.rollback()
        finally:
            self.connection.close()
            self._connection = None
            self._finished = True
        return False

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("UnitOfWork is not active")
        return self._connection

    @property
    def idempotency(self) -> IdempotencyStore:
        return IdempotencyStore(self.connection)

    @property
    def events(self) -> EventStore:
        return EventStore(self.connection)

    @property
    def outbox(self) -> OutboxRepository:
        return OutboxRepository(self.connection)

    @property
    def lifecycle(self) -> LifecycleRepository:
        return LifecycleRepository(self.connection)

    @property
    def projection_checkpoints(self) -> ProjectionCheckpointRepository:
        return ProjectionCheckpointRepository(self.connection)

    def commit(self) -> None:
        if self._finished:
            raise RuntimeError("UnitOfWork is already finished")
        self.connection.commit()
        self._finished = True

    def rollback(self) -> None:
        if self._finished:
            raise RuntimeError("UnitOfWork is already finished")
        self.connection.rollback()
        self._finished = True


__all__ = ["UnitOfWork"]
