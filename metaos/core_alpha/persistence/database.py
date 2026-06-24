"""SQLite connection and migration entry point for Core Alpha state."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from metaos.core_alpha.persistence.migration import MigrationRunner
from metaos.core_alpha.persistence.migrations import MIGRATIONS


class CoreAlphaDatabase:
    def __init__(self, path: Path, *, busy_timeout_ms: int = 5000):
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms cannot be negative")
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.path,
            isolation_level=None,
            timeout=self.busy_timeout_ms / 1000,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def initialize(self) -> list[int]:
        connection = self.connect()
        try:
            return MigrationRunner(connection, MIGRATIONS).apply_all()
        finally:
            connection.close()

    def rollback_last_migration(self) -> int | None:
        connection = self.connect()
        try:
            return MigrationRunner(connection, MIGRATIONS).rollback_last()
        finally:
            connection.close()

    def journal_mode(self) -> str:
        connection = self.connect()
        try:
            row = connection.execute("PRAGMA journal_mode").fetchone()
            return str(row[0]).lower()
        finally:
            connection.close()


__all__ = ["CoreAlphaDatabase"]
