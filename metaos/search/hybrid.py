"""Hybrid evidence retrieval for Alpha research tasks."""

from __future__ import annotations

from collections.abc import Sequence

from metaos.core.schemas import Chunk
from metaos.search.full_text import FullTextSearchFilters, full_text_search
from metaos.search.fusion import EvidenceCandidate, rrf_fuse
from metaos.search.vector import VectorRetrievalService, vector_search


def hybrid_search(
    query: str,
    *,
    chunks: Sequence[Chunk] = (),
    vector_retrieval: VectorRetrievalService | None = None,
    filters: FullTextSearchFilters | dict | None = None,
    top_k: int = 5,
    full_text_top_k: int | None = None,
    vector_top_k: int | None = None,
) -> list[EvidenceCandidate]:
    query = query.strip()
    if not query or top_k <= 0:
        return []

    channels = {}
    if chunks:
        channels["full_text"] = full_text_search(
            query,
            chunks=chunks,
            filters=filters,
            top_k=full_text_top_k or top_k,
        )
    if vector_retrieval is not None:
        channels["vector"] = vector_search(
            query,
            retrieval=vector_retrieval,
            filters=filters,
            top_k=vector_top_k or top_k,
        )
    if not channels:
        return []
    return rrf_fuse(channels, filters=filters, top_k=top_k)
