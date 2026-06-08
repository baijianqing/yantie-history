"""SQLite connection and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from metaos.workspace.paths import ensure_workspace


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    message TEXT,
    error TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    result_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    uri TEXT NOT NULL,
    title TEXT,
    platform TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(type);
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    mime_type TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_source_id ON assets(source_id);
CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT,
    category TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    markdown_path TEXT,
    citations_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_category ON knowledge_items(category);
CREATE INDEX IF NOT EXISTS idx_knowledge_items_created_at ON knowledge_items(created_at);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    knowledge_item_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    heading_path_json TEXT NOT NULL DEFAULT '[]',
    text TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    citation_json TEXT,
    embedding_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_knowledge_item_id ON chunks(knowledge_item_id);
CREATE INDEX IF NOT EXISTS idx_chunks_knowledge_item_ordinal
    ON chunks(knowledge_item_id, ordinal);
"""


def connect(database_path: Path | None = None) -> sqlite3.Connection:
    paths = ensure_workspace()
    db_path = database_path or paths.database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, factory=ClosingConnection)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path: Path | None = None) -> Path:
    paths = ensure_workspace()
    db_path = database_path or paths.database
    with connect(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
    return db_path


def main() -> None:
    print(initialize_database())


if __name__ == "__main__":
    main()
