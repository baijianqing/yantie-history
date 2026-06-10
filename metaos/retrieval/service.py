"""Chroma-backed chunk indexing and retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import chromadb
from chromadb.config import Settings

from metaos.core.config import get_settings
from metaos.core.errors import EmbeddingProviderError
from metaos.core.schemas import Chunk
from metaos.retrieval.embeddings import EmbeddingProvider, make_embedding_provider
from metaos.workspace.catalog import ChunkRepository, KnowledgeRepository
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


COLLECTION_NAME = "metaos_chunks"
DEFAULT_UPSERT_BATCH_SIZE = 16
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class IndexStats:
    indexed_chunks: int
    collection_count: int
    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int | None
    collection_name: str = COLLECTION_NAME

    def as_dict(self) -> dict[str, Any]:
        return {
            "indexed_chunks": self.indexed_chunks,
            "collection_count": self.collection_count,
            "collection_name": self.collection_name,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
        }
import math
import numpy as np

def validate_batch(ids, documents, embeddings, metadatas):
    assert len(ids) == len(documents) == len(embeddings) == len(metadatas)

    # 1. 检查 id
    for i, x in enumerate(ids):
        assert isinstance(x, str), f"id 不是字符串: {i}, {type(x)}"
        assert x.strip(), f"id 为空: {i}"

    assert len(ids) == len(set(ids)), "同一个 batch 内 ids 有重复"

    # 2. 检查 document
    for i, doc in enumerate(documents):
        assert isinstance(doc, str), f"document 不是字符串: {i}, {type(doc)}"
        assert doc.strip(), f"document 为空: {i}"
        assert "\x00" not in doc, f"document 含有空字符 \\x00: {i}"

    # 3. 检查 embedding
    dims = set()

    for i, emb in enumerate(embeddings):
        assert emb is not None, f"embedding 是 None: {i}"

        if isinstance(emb, np.ndarray):
            emb = emb.tolist()

        assert isinstance(emb, list), f"embedding 不是 list: {i}, {type(emb)}"
        assert len(emb) > 0, f"embedding 为空: {i}"

        dims.add(len(emb))

        for j, v in enumerate(emb):
            assert isinstance(v, (int, float)), f"embedding 非数字: {i}-{j}, {type(v)}"
            assert math.isfinite(v), f"embedding 有 NaN/Inf: {i}-{j}, {v}"

    assert len(dims) == 1, f"embedding 维度不一致: {dims}"

    # 4. 检查 metadata
    for i, meta in enumerate(metadatas):
        assert isinstance(meta, dict), f"metadata 不是 dict: {i}, {type(meta)}"

        for k, v in meta.items():
            assert isinstance(k, str), f"metadata key 不是字符串: {i}, {k}, {type(k)}"

            assert isinstance(v, (str, int, float, bool)) or v is None, (
                f"metadata value 类型非法: {i}, key={k}, value={v}, type={type(v)}"
            )

@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    knowledge_item_id: str
    text: str
    heading_path: list[str]
    ordinal: int | None
    score: float
    distance: float | None
    source_id: str | None = None
    asset_id: str | None = None
    file_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "knowledge_item_id": self.knowledge_item_id,
            "text": self.text,
            "heading_path": self.heading_path,
            "ordinal": self.ordinal,
            "score": self.score,
            "distance": self.distance,
            "source_id": self.source_id,
            "asset_id": self.asset_id,
            "file_path": self.file_path,
        }


class RetrievalService:
    def __init__(
        self,
        paths: WorkspacePaths | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.paths = paths or ensure_workspace()
        self.embedding_provider = embedding_provider or make_embedding_provider()
        settings = get_settings()
        self.upsert_batch_size = max(
            1,
            min(settings.chroma_upsert_batch_size, DEFAULT_UPSERT_BATCH_SIZE),
        )
        self.chunk_repository = ChunkRepository(self.paths.database)
        self.knowledge_repository = KnowledgeRepository(self.paths.database)
        self.chroma_path = self.paths.index / "chroma"
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )

    def index_knowledge_item(
        self,
        item_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexStats:
        self.knowledge_repository.get(item_id)
        chunks = self.chunk_repository.list_by_knowledge_item(item_id, limit=100000)
        collection = self.collection()
        if int(collection.count()) > 0:
            self._ensure_collection_compatible(collection, self._ensure_provider_dimensions())
        self._delete_knowledge_item(collection, item_id)
        return self._index_chunks(chunks, collection, progress_callback=progress_callback)

    def rebuild_all(self, progress_callback: ProgressCallback | None = None) -> IndexStats:
        self.reset_collection()
        chunks = self.chunk_repository.list_all(limit=100000)
        return self._index_chunks(chunks, self.collection(), progress_callback=progress_callback)

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        query_embeddings = self.embedding_provider.embed([query])
        dimensions = len(query_embeddings[0]) if query_embeddings else None
        collection = self.collection()
        collection_count = int(collection.count())
        if collection_count <= 0:
            return []
        self._ensure_collection_compatible(collection, dimensions)
        result = collection.query(
            query_embeddings=query_embeddings,
            n_results=max(1, min(top_k, 20, collection_count)),
            include=["documents", "metadatas", "distances"],
        )
        return self._parse_search_results(result)

    def collection_count(self) -> int:
        return int(self.collection().count())

    def embedding_status(self) -> dict[str, Any]:
        collection = self.collection()
        return {
            "embedding_provider": self.embedding_provider.name,
            "embedding_model": self.embedding_provider.model,
            "embedding_dimensions": self.embedding_provider.dimensions,
            "embedding_batch_size": getattr(self.embedding_provider, "batch_size", None),
            "embedding_timeout": getattr(self.embedding_provider, "timeout", None),
            "chroma_upsert_batch_size": self.upsert_batch_size,
            "collection_name": COLLECTION_NAME,
            "collection_count": int(collection.count()),
            "collection_metadata": dict(collection.metadata or {}),
        }

    def collection(self):
        return self.client.get_or_create_collection(
            COLLECTION_NAME,
            metadata=self.collection_metadata(),
            embedding_function=None,
        )

    def reset_collection(self) -> None:
        names = {getattr(collection, "name", str(collection)) for collection in self.client.list_collections()}
        if COLLECTION_NAME in names:
            self.client.delete_collection(COLLECTION_NAME)

    def _index_chunks(
        self,
        chunks: list[Chunk],
        collection,
        progress_callback: ProgressCallback | None = None,
    ) -> IndexStats:
        indexed_ids: list[str] = []
        total = len(chunks)
        if progress_callback:
            progress_callback(0, total)
        for start in range(0, total, self.upsert_batch_size):
            batch = chunks[start : start + self.upsert_batch_size]
            ids = [chunk.id for chunk in batch]
            documents = [chunk.text for chunk in batch]
            embeddings = self.embedding_provider.embed(documents)
            dimensions = len(embeddings[0]) if embeddings else None
            self._ensure_collection_compatible(collection, dimensions)
            metadatas = [chunk_metadata(chunk) for chunk in batch]
            validate_batch(ids, documents, embeddings, metadatas)
            embeddings_np = np.asarray(embeddings, dtype=np.float32)
            
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings_np,
                metadatas=metadatas
            	)
            
            self._update_collection_metadata(collection, dimensions)
            indexed_ids.extend(ids)
            if progress_callback:
                progress_callback(len(indexed_ids), total)

        self.chunk_repository.update_embedding_ids(indexed_ids)
        return IndexStats(
            indexed_chunks=len(indexed_ids),
            collection_count=int(collection.count()),
            embedding_provider=self.embedding_provider.name,
            embedding_model=self.embedding_provider.model,
            embedding_dimensions=self.embedding_provider.dimensions,
        )

    def _delete_knowledge_item(self, collection, item_id: str) -> None:
        try:
            collection.delete(where={"knowledge_item_id": item_id})
        except Exception:
            return

    def collection_metadata(
        self,
        dimensions: int | None = None,
        *,
        include_hnsw: bool = True,
    ) -> dict[str, str | int]:
        known_dimensions = dimensions or self.embedding_provider.dimensions or 0
        metadata: dict[str, str | int] = {
            "embedding_provider": self.embedding_provider.name,
            "embedding_model": self.embedding_provider.model,
            "embedding_dimensions": int(known_dimensions),
        }
        if include_hnsw:
            metadata["hnsw:space"] = "cosine"
        return metadata

    def _update_collection_metadata(self, collection, dimensions: int | None) -> None:
        if dimensions is None:
            return
        collection.modify(metadata=self.collection_metadata(dimensions, include_hnsw=False))

    def _ensure_collection_compatible(self, collection, dimensions: int | None) -> None:
        if int(collection.count()) <= 0:
            return
        metadata = collection.metadata or {}
        expected = self.collection_metadata(dimensions)
        mismatches = []
        for key in ("embedding_provider", "embedding_model", "embedding_dimensions"):
            if str(metadata.get(key, "")) != str(expected[key]):
                mismatches.append(
                    f"{key}: existing={metadata.get(key)!r}, current={expected[key]!r}"
                )
        if mismatches:
            raise EmbeddingProviderError(
                "Existing Chroma index was built with a different embedding provider. "
                "请先执行“重建全部索引”，再进行索引或搜索。 "
                + "; ".join(mismatches)
            )

    def _ensure_provider_dimensions(self) -> int | None:
        if self.embedding_provider.dimensions is not None:
            return self.embedding_provider.dimensions
        probe = self.embedding_provider.embed(["MetaOS embedding dimension probe"])
        return len(probe[0]) if probe else None

    def _parse_search_results(self, result: dict[str, Any]) -> list[SearchResult]:
        ids = first_result_list(result.get("ids"))
        documents = first_result_list(result.get("documents"))
        metadatas = first_result_list(result.get("metadatas"))
        distances = first_result_list(result.get("distances"))

        results: list[SearchResult] = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            distance = distances[index] if index < len(distances) else None
            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    knowledge_item_id=str(metadata.get("knowledge_item_id", "")),
                    text=documents[index] if index < len(documents) else "",
                    heading_path=json.loads(str(metadata.get("heading_path_json", "[]"))),
                    ordinal=metadata.get("ordinal"),
                    score=distance_to_score(distance),
                    distance=distance,
                    source_id=metadata.get("source_id"),
                    asset_id=metadata.get("asset_id"),
                    file_path=metadata.get("file_path"),
                )
            )
        return results


def chunk_metadata(chunk: Chunk) -> dict[str, str | int]:
    citation = chunk.citation
    return {
        "knowledge_item_id": chunk.knowledge_item_id,
        "heading_path": " / ".join(chunk.heading_path),
        "heading_path_json": json.dumps(chunk.heading_path, ensure_ascii=False),
        "ordinal": int(chunk.ordinal),
        "char_count": int(chunk.char_count or len(chunk.text)),
        "source_id": citation.source_id if citation and citation.source_id else "",
        "asset_id": citation.asset_id if citation and citation.asset_id else "",
        "file_path": str(citation.file_path) if citation and citation.file_path else "",
    }


def first_result_list(value: Any) -> list[Any]:
    if not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else value


def distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))
