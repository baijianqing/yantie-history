"""Small transactional migration runner for Core Alpha SQLite state."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up_statements: tuple[str, ...]
    down_statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("migration version must be positive")
        if not self.name.strip():
            raise ValueError("migration name cannot be blank")
        if not self.up_statements or not self.down_statements:
            raise ValueError("migration requires both up and down statements")


class MigrationRunner:
    def __init__(self, connection: sqlite3.Connection, migrations: Iterable[Migration]):
        self.connection = connection
        self.migrations = tuple(sorted(migrations, key=lambda migration: migration.version))
        versions = [migration.version for migration in self.migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("migration versions must be unique")

    def apply_all(self) -> list[int]:
        self._ensure_ledger()
        applied = self.applied_versions()
        newly_applied: list[int] = []
        for migration in self.migrations:
            if migration.version in applied:
                continue
            self._apply(migration)
            newly_applied.append(migration.version)
        return newly_applied

    def rollback_last(self) -> int | None:
        self._ensure_ledger()
        row = self.connection.execute(
            """
            SELECT version
            FROM core_alpha_schema_migrations
            ORDER BY version DESC
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None
        version = int(row["version"])
        migration = next(
            (candidate for candidate in self.migrations if candidate.version == version),
            None,
        )
        if migration is None:
            raise RuntimeError(f"no migration definition for applied version {version}")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migration.down_statements:
                self.connection.execute(statement)
            self.connection.execute(
                "DELETE FROM core_alpha_schema_migrations WHERE version = ?",
                (version,),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        return version

    def applied_versions(self) -> set[int]:
        rows = self.connection.execute(
            "SELECT version FROM core_alpha_schema_migrations"
        ).fetchall()
        return {int(row["version"]) for row in rows}

    def _ensure_ledger(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS core_alpha_schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _apply(self, migration: Migration) -> None:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in migration.up_statements:
                self.connection.execute(statement)
            self.connection.execute(
                """
                INSERT INTO core_alpha_schema_migrations (version, name, applied_at)
                VALUES (?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise


__all__ = ["Migration", "MigrationRunner"]
