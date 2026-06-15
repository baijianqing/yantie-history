"""Vector retrieval adapter for Alpha evidence search."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from metaos.core.schemas import Citation
from metaos.search.full_text import FullTextSearchFilters
from metaos.search.fusion import SearchCandidate, candidate_matches, normalize_filters


class VectorRetrievalService(Protocol):
    def search(self, query: str, top_k: int = 5) -> Sequence[Any]:
        """Return vector search results shaped like retrieval.service.SearchResult."""


def vector_search(
    query: str,
    *,
    retrieval: VectorRetrievalService,
    filters: FullTextSearchFilters | dict | None = None,
    top_k: int = 5,
) -> list[SearchCandidate]:
    query = query.strip()
    if not query or top_k <= 0:
        return []

    normalized_filters = normalize_filters(filters)
    candidates = [
        search_result_to_candidate(result)
        for result in retrieval.search(query, top_k=max(1, top_k))
    ]
    return [
        candidate
        for candidate in candidates
        if candidate_matches(candidate, normalized_filters)
    ][:top_k]


def search_result_to_candidate(result: Any) -> SearchCandidate:
    citation = getattr(result, "citation", None) or citation_from_result(result)
    distance = getattr(result, "distance", None)
    metadata: dict[str, Any] = {"channel": "vector"}
    if distance is not None:
        metadata["distance"] = float(distance)
    return SearchCandidate(
        chunk_id=str(getattr(result, "chunk_id")),
        knowledge_item_id=str(getattr(result, "knowledge_item_id")),
        text=str(getattr(result, "text")),
        heading_path=list(getattr(result, "heading_path", []) or []),
        ordinal=getattr(result, "ordinal", None),
        score=float(getattr(result, "score", 0.0) or 0.0),
        citation=citation,
        metadata=metadata,
    )


def citation_from_result(result: Any) -> Citation:
    text = str(getattr(result, "text", "") or "").strip()
    return Citation(
        source_id=clean_optional(getattr(result, "source_id", None)),
        asset_id=clean_optional(getattr(result, "asset_id", None)),
        file_path=path_or_none(getattr(result, "file_path", None)),
        excerpt=text or None,
    )


def clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def path_or_none(value: Any) -> Path | None:
    text = clean_optional(value)
    return Path(text) if text else None
