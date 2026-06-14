"""Repositories for library catalog objects."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from metaos.core.errors import AssetNotFoundError, KnowledgeItemNotFoundError, SourceNotFoundError
from metaos.core.schemas import (
    Asset,
    AssetKind,
    Chunk,
    Citation,
    KnowledgeCategory,
    KnowledgeItem,
    Source,
    SourceType,
)
from metaos.workspace.database import connect, initialize_database


def _json_dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class SourceRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_database(database_path)

    def add(self, source: Source) -> Source:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sources (
                    id, type, uri, title, platform, note, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.id,
                    source.type.value,
                    source.uri,
                    source.title,
                    source.platform,
                    source.note,
                    source.created_at.isoformat(),
                ),
            )
        return source

    def get(self, source_id: str) -> Source:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            raise SourceNotFoundError(f"Source not found: {source_id}")
        return Source(
            id=row["id"],
            type=SourceType(row["type"]),
            uri=row["uri"],
            title=row["title"],
            platform=row["platform"],
            note=row["note"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list(self, limit: int = 50) -> list[Source]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]


class AssetRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_database(database_path)

    def add(self, asset: Asset) -> Asset:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO assets (
                    id, source_id, kind, path, mime_type, sha256, size_bytes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset.id,
                    asset.source_id,
                    asset.kind.value,
                    str(asset.path),
                    asset.mime_type,
                    asset.sha256,
                    asset.size_bytes,
                    asset.created_at.isoformat(),
                ),
            )
        return asset

    def get(self, asset_id: str) -> Asset:
        with connect(self.database_path) as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        if row is None:
            raise AssetNotFoundError(f"Asset not found: {asset_id}")
        return Asset(
            id=row["id"],
            source_id=row["source_id"],
            kind=AssetKind(row["kind"]),
            path=Path(row["path"]),
            mime_type=row["mime_type"],
            sha256=row["sha256"],
            size_bytes=row["size_bytes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list(self, limit: int = 50) -> list[Asset]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM assets ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]


class KnowledgeRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_database(database_path)

    def add(self, item: KnowledgeItem) -> KnowledgeItem:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO knowledge_items (
                    id, title, summary, category, tags_json, markdown_path,
                    citations_json, metadata_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.title,
                    item.summary,
                    item.category.value,
                    _json_dump(item.tags),
                    str(item.markdown_path) if item.markdown_path else None,
                    item.model_dump_json(include={"citations"}),
                    _json_dump(item.metadata),
                    item.created_at.isoformat(),
                ),
            )
        return item

    def get(self, item_id: str) -> KnowledgeItem:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            ).fetchone()
        if row is None:
            raise KnowledgeItemNotFoundError(f"Knowledge item not found: {item_id}")
        raw_citations = json.loads(row["citations_json"] or "[]")
        citations_data = (
            raw_citations.get("citations", [])
            if isinstance(raw_citations, dict)
            else raw_citations
        )
        return KnowledgeItem(
            id=row["id"],
            title=row["title"],
            summary=row["summary"],
            category=KnowledgeCategory(row["category"]),
            tags=json.loads(row["tags_json"] or "[]"),
            markdown_path=Path(row["markdown_path"]) if row["markdown_path"] else None,
            citations=[Citation.model_validate(citation) for citation in citations_data],
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list(self, limit: int = 50) -> list[KnowledgeItem]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_items ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get(row["id"]) for row in rows]

    def delete(self, item_id: str) -> None:
        self.get(item_id)
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))


class ChunkRepository:
    def __init__(self, database_path: Path | None = None):
        self.database_path = initialize_database(database_path)

    def add_many(self, chunks: list[Chunk]) -> list[Chunk]:
        if not chunks:
            return chunks
        with connect(self.database_path) as connection:
            connection.executemany(
                """
                INSERT OR REPLACE INTO chunks (
                    id, knowledge_item_id, ordinal, heading_path_json, text,
                    char_count, citation_json, embedding_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.id,
                        chunk.knowledge_item_id,
                        chunk.ordinal,
                        _json_dump(chunk.heading_path),
                        chunk.text,
                        chunk.char_count if chunk.char_count is not None else len(chunk.text),
                        _json_dump(chunk.citation.model_dump(mode="json")) if chunk.citation else None,
                        chunk.embedding_id,
                        chunk.created_at.isoformat(),
                    )
                    for chunk in chunks
                ],
            )
        return chunks

    def delete_by_knowledge_item(self, item_id: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute("DELETE FROM chunks WHERE knowledge_item_id = ?", (item_id,))

    def list_by_knowledge_item(self, item_id: str, limit: int = 200) -> list[Chunk]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM chunks
                WHERE knowledge_item_id = ?
                ORDER BY ordinal ASC
                LIMIT ?
                """,
                (item_id, limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_all(self, limit: int = 10000) -> list[Chunk]:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM chunks
                ORDER BY created_at ASC, ordinal ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def update_embedding_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        with connect(self.database_path) as connection:
            connection.executemany(
                "UPDATE chunks SET embedding_id = ? WHERE id = ?",
                [(chunk_id, chunk_id) for chunk_id in chunk_ids],
            )

    def clear_embedding_ids_by_knowledge_item(self, item_id: str) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                "UPDATE chunks SET embedding_id = NULL WHERE knowledge_item_id = ?",
                (item_id,),
            )

    def clear_all_embedding_ids(self) -> None:
        with connect(self.database_path) as connection:
            connection.execute("UPDATE chunks SET embedding_id = NULL")

    def count_by_knowledge_item(self, item_id: str) -> int:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM chunks WHERE knowledge_item_id = ?",
                (item_id,),
            ).fetchone()
        return int(row["count"] if row else 0)

    def counts_by_knowledge_item_ids(self, item_ids: list[str]) -> dict[str, int]:
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        with connect(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT knowledge_item_id, COUNT(*) AS count
                FROM chunks
                WHERE knowledge_item_id IN ({placeholders})
                GROUP BY knowledge_item_id
                """,
                item_ids,
            ).fetchall()
        counts = {item_id: 0 for item_id in item_ids}
        counts.update({row["knowledge_item_id"]: int(row["count"]) for row in rows})
        return counts

    def _from_row(self, row) -> Chunk:
        citation_data = json.loads(row["citation_json"]) if row["citation_json"] else None
        return Chunk(
            id=row["id"],
            knowledge_item_id=row["knowledge_item_id"],
            text=row["text"],
            heading_path=json.loads(row["heading_path_json"] or "[]"),
            ordinal=row["ordinal"],
            char_count=row["char_count"],
            citation=Citation.model_validate(citation_data) if citation_data else None,
            embedding_id=row["embedding_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
