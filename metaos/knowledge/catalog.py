"""Read-only Core Alpha Knowledge Catalog adapter.

The current workspace schema predates the frozen Core Alpha domain model. This
adapter projects existing Source / Asset / KnowledgeItem / Chunk rows into
stable KnowledgeItem, KnowledgeItemVersion, Chunk, and IndexGeneration
identities without modifying library content, re-chunking, or rebuilding indexes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from metaos.core.errors import AssetNotFoundError, KnowledgeItemNotFoundError
from metaos.core.schemas import Asset, Chunk, KnowledgeItem
from metaos.knowledge.chunking import DEFAULT_CHUNKER_VERSION, estimate_tokens
from metaos.knowledge.versioning import DEFAULT_INDEX_VERSION, stable_prefixed_id
from metaos.workspace.catalog import AssetRepository, ChunkRepository, KnowledgeRepository


NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class KnowledgeCatalogError(RuntimeError):
    """Base class for catalog projection failures."""


class KnowledgeCatalogNotFoundError(KnowledgeCatalogError):
    """Raised when a projected identity cannot be resolved."""


class KnowledgeCatalogIntegrityError(KnowledgeCatalogError):
    """Raised when persisted content identity no longer matches disk content."""


class KnowledgeCatalogItem(BaseModel):
    knowledge_item_id: NonEmptyString
    title: NonEmptyString
    item_type: NonEmptyString
    language: NonEmptyString
    owner_scope: NonEmptyString
    lifecycle_status: NonEmptyString
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    current_knowledge_item_version_id: NonEmptyString | None
    aliases: list[NonEmptyString] = Field(default_factory=list)


class KnowledgeCatalogVersion(BaseModel):
    knowledge_item_version_id: NonEmptyString
    knowledge_item_id: NonEmptyString
    version: int = Field(ge=1)
    content_hash: NonEmptyString
    structure_hash: NonEmptyString
    parser_version: NonEmptyString
    language: NonEmptyString
    availability_status: NonEmptyString
    created_at: datetime
    previous_version_id: NonEmptyString | None
    asset_id: NonEmptyString | None
    storage_ref: NonEmptyString | None
    chunker_version: NonEmptyString
    index_strategy_version: NonEmptyString


class KnowledgeCatalogChunk(BaseModel):
    chunk_id: NonEmptyString
    knowledge_item_version_id: NonEmptyString
    position: int = Field(ge=0)
    content_hash: NonEmptyString
    chunker_version: NonEmptyString
    created_at: datetime
    parent_chunk_id: NonEmptyString | None
    previous_chunk_id: NonEmptyString | None
    next_chunk_id: NonEmptyString | None
    section_path: list[NonEmptyString]
    page: int | None
    timestamp_seconds: float | None
    start_offset: int | None
    end_offset: int | None
    token_count: int
    char_count: int
    text_preview: str


class IndexGenerationMetadata(BaseModel):
    index_generation_id: NonEmptyString
    index_type: NonEmptyString
    knowledge_item_version_id: NonEmptyString
    chunk_strategy_version: NonEmptyString
    index_strategy_version: NonEmptyString
    status: NonEmptyString
    expected_item_count: int = Field(ge=0)
    actual_item_count: int = Field(ge=0)
    validation_summary: NonEmptyString
    created_at: datetime
    embedding_model: NonEmptyString | None = None
    embedding_dimension: int | None = None
    previous_generation_id: NonEmptyString | None = None
    ready_at: datetime | None = None
    invalidated_at: datetime | None = None


class KnowledgeCatalogAdapter:
    """Read-only projection over existing workspace knowledge repositories."""

    def __init__(self, database_path: Path | None = None):
        self.database_path = database_path
        self.items = KnowledgeRepository(database_path)
        self.chunks = ChunkRepository(database_path)
        self.assets = AssetRepository(database_path)

    def list_items(self, limit: int = 50) -> list[KnowledgeCatalogItem]:
        return [self._item_response(item) for item in self.items.list(limit=limit)]

    def get_item(self, knowledge_item_id: str) -> KnowledgeCatalogItem:
        return self._item_response(self._get_item(knowledge_item_id))

    def list_versions(self, knowledge_item_id: str) -> list[KnowledgeCatalogVersion]:
        return [self.get_current_version(knowledge_item_id)]

    def get_current_version(self, knowledge_item_id: str) -> KnowledgeCatalogVersion:
        item = self._get_item(knowledge_item_id)
        return self._version_response(item)

    def get_version(self, knowledge_item_version_id: str) -> KnowledgeCatalogVersion:
        for item in self.items.list(limit=10000):
            version = self._version_response(item)
            if version.knowledge_item_version_id == knowledge_item_version_id:
                return version
        raise KnowledgeCatalogNotFoundError(
            f"knowledge item version not found: {knowledge_item_version_id}"
        )

    def list_chunks(
        self,
        knowledge_item_version_id: str,
        *,
        limit: int = 200,
    ) -> list[KnowledgeCatalogChunk]:
        version = self.get_version(knowledge_item_version_id)
        raw_chunks = self.chunks.list_by_knowledge_item(version.knowledge_item_id, limit=limit)
        return [
            self._chunk_response(
                chunk=chunk,
                version=version,
                previous_chunk_id=raw_chunks[index - 1].id if index > 0 else None,
                next_chunk_id=raw_chunks[index + 1].id if index < len(raw_chunks) - 1 else None,
            )
            for index, chunk in enumerate(raw_chunks)
        ]

    def get_chunk(self, chunk_id: str) -> KnowledgeCatalogChunk:
        for item in self.items.list(limit=10000):
            version = self._version_response(item)
            for chunk in self.list_chunks(version.knowledge_item_version_id, limit=10000):
                if chunk.chunk_id == chunk_id:
                    return chunk
        raise KnowledgeCatalogNotFoundError(f"chunk not found: {chunk_id}")

    def list_index_generations(
        self,
        knowledge_item_version_id: str,
    ) -> list[IndexGenerationMetadata]:
        version = self.get_version(knowledge_item_version_id)
        chunks = self.list_chunks(knowledge_item_version_id, limit=10000)
        index_id = stable_prefixed_id(
            "idxgen",
            [
                version.knowledge_item_version_id,
                version.chunker_version,
                version.index_strategy_version,
                str(len(chunks)),
            ],
        )
        created_at = chunks[0].created_at if chunks else version.created_at
        return [
            IndexGenerationMetadata(
                index_generation_id=index_id,
                index_type="workspace_chunk_metadata",
                knowledge_item_version_id=version.knowledge_item_version_id,
                chunk_strategy_version=version.chunker_version,
                index_strategy_version=version.index_strategy_version,
                status="ready",
                expected_item_count=len(chunks),
                actual_item_count=len(chunks),
                validation_summary="Projected from workspace chunk metadata.",
                created_at=created_at,
                ready_at=created_at,
            )
        ]

    def _item_response(self, item: KnowledgeItem) -> KnowledgeCatalogItem:
        version_id: str | None
        try:
            version_id = self._version_response(item).knowledge_item_version_id
        except KnowledgeCatalogIntegrityError:
            raise
        except KnowledgeCatalogError:
            version_id = None
        updated_at = self._latest_chunk_time(item.id) or item.created_at
        return KnowledgeCatalogItem(
            knowledge_item_id=item.id,
            title=item.title,
            item_type="document",
            language=str(item.metadata.get("language") or "und"),
            owner_scope="local_workspace",
            lifecycle_status="active",
            revision=int(item.metadata.get("catalog_revision") or 1),
            created_at=_utc(item.created_at),
            updated_at=_utc(updated_at),
            current_knowledge_item_version_id=version_id,
            aliases=[str(tag) for tag in item.tags],
        )

    def _version_response(self, item: KnowledgeItem) -> KnowledgeCatalogVersion:
        asset = self._asset_for_item(item)
        chunker_version = str(item.metadata.get("chunker") or DEFAULT_CHUNKER_VERSION)
        parser_version = str(item.metadata.get("parser") or "text_v1")
        index_version = str(item.metadata.get("index_version") or DEFAULT_INDEX_VERSION)
        content_hash = self._asset_content_hash(asset)
        chunk_count = self.chunks.count_by_knowledge_item(item.id)
        structure_hash = _hash_text(
            "|".join(
                [
                    item.title,
                    str(chunk_count),
                    chunker_version,
                    index_version,
                    ",".join(item.tags),
                ]
            )
        )
        version_id = stable_prefixed_id(
            "kiv",
            [
                item.id,
                asset.id if asset else "asset_missing",
                content_hash,
                structure_hash,
                parser_version,
                chunker_version,
                index_version,
            ],
        )
        storage_ref = str(asset.path) if asset else None
        availability = "available" if asset is not None and asset.path.exists() else "unavailable"
        return KnowledgeCatalogVersion(
            knowledge_item_version_id=version_id,
            knowledge_item_id=item.id,
            version=1,
            content_hash=f"sha256:{content_hash}",
            structure_hash=f"sha256:{structure_hash}",
            parser_version=parser_version,
            language=str(item.metadata.get("language") or "und"),
            availability_status=availability,
            created_at=_utc(asset.created_at if asset else item.created_at),
            previous_version_id=None,
            asset_id=asset.id if asset else None,
            storage_ref=storage_ref,
            chunker_version=chunker_version,
            index_strategy_version=index_version,
        )

    def _chunk_response(
        self,
        *,
        chunk: Chunk,
        version: KnowledgeCatalogVersion,
        previous_chunk_id: str | None,
        next_chunk_id: str | None,
    ) -> KnowledgeCatalogChunk:
        citation = chunk.citation
        text = chunk.text
        return KnowledgeCatalogChunk(
            chunk_id=chunk.id,
            knowledge_item_version_id=version.knowledge_item_version_id,
            position=max(chunk.ordinal - 1, 0),
            content_hash=f"sha256:{_hash_text(_normalize_text(text))}",
            chunker_version=version.chunker_version,
            created_at=_utc(chunk.created_at),
            parent_chunk_id=None,
            previous_chunk_id=previous_chunk_id,
            next_chunk_id=next_chunk_id,
            section_path=chunk.heading_path,
            page=citation.page if citation else None,
            timestamp_seconds=citation.timestamp_seconds if citation else None,
            start_offset=None,
            end_offset=None,
            token_count=estimate_tokens(text),
            char_count=chunk.char_count if chunk.char_count is not None else len(text),
            text_preview=_preview(text),
        )

    def _asset_for_item(self, item: KnowledgeItem) -> Asset | None:
        asset_id = item.metadata.get("asset_id")
        if not asset_id and item.citations:
            asset_id = item.citations[0].asset_id
        if not asset_id:
            return None
        try:
            return self.assets.get(str(asset_id))
        except AssetNotFoundError:
            return None

    def _asset_content_hash(self, asset: Asset | None) -> str:
        if asset is None:
            return _hash_text("asset_missing")
        path = asset.path
        stored_hash = asset.sha256
        actual_hash: str | None = None
        if path.exists():
            actual_hash = _hash_bytes(path.read_bytes())
        if stored_hash and actual_hash and stored_hash != actual_hash:
            raise KnowledgeCatalogIntegrityError(
                f"asset content hash changed without a new version: {asset.id}"
            )
        if stored_hash:
            return stored_hash
        if actual_hash:
            return actual_hash
        return _hash_text(f"missing:{asset.id}:{asset.path}")

    def _latest_chunk_time(self, item_id: str) -> datetime | None:
        chunks = self.chunks.list_by_knowledge_item(item_id, limit=10000)
        if not chunks:
            return None
        return max(chunk.created_at for chunk in chunks)

    def _get_item(self, knowledge_item_id: str) -> KnowledgeItem:
        try:
            return self.items.get(knowledge_item_id)
        except KnowledgeItemNotFoundError as exc:
            raise KnowledgeCatalogNotFoundError(
                f"knowledge item not found: {knowledge_item_id}"
            ) from exc


def _hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode("utf-8"))


def _normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in normalized.splitlines()).strip()


def _preview(text: str, limit: int = 180) -> str:
    normalized = " ".join(_normalize_text(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + "..."


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "IndexGenerationMetadata",
    "KnowledgeCatalogAdapter",
    "KnowledgeCatalogChunk",
    "KnowledgeCatalogError",
    "KnowledgeCatalogIntegrityError",
    "KnowledgeCatalogItem",
    "KnowledgeCatalogNotFoundError",
    "KnowledgeCatalogVersion",
]
