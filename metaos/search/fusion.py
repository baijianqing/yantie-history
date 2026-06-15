"""RRF fusion for MetaOS Alpha search candidates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, Field, field_validator

from metaos.core.schemas import Citation
from metaos.search.full_text import FullTextSearchFilters, FullTextSearchResult


DEFAULT_RRF_K = 60


class SearchCandidate(BaseModel):
    chunk_id: str
    knowledge_item_id: str
    text: str
    heading_path: list[str] = Field(default_factory=list)
    ordinal: int | None = None
    score: float = 0.0
    citation: Citation | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunk_id", "knowledge_item_id", "text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class EvidenceCandidate(SearchCandidate):
    fused_score: float = 0.0
    channel_ranks: dict[str, int] = Field(default_factory=dict)
    channel_scores: dict[str, float] = Field(default_factory=dict)


def rrf_fuse(
    channels: Mapping[str, Sequence[SearchCandidate | FullTextSearchResult | Any]],
    *,
    filters: FullTextSearchFilters | dict | None = None,
    top_k: int = 5,
    k: int = DEFAULT_RRF_K,
) -> list[EvidenceCandidate]:
    if top_k <= 0:
        return []

    normalized_filters = normalize_filters(filters)
    merged: dict[str, EvidenceCandidate] = {}
    for channel_name, raw_candidates in channels.items():
        channel = str(channel_name).strip()
        if not channel:
            raise ValueError("channel name cannot be blank")
        filtered_candidates = [
            candidate
            for candidate in (normalize_candidate(raw_candidate) for raw_candidate in raw_candidates)
            if candidate_matches(candidate, normalized_filters)
        ]
        for rank, candidate in enumerate(filtered_candidates, start=1):
            contribution = 1 / (max(1, k) + rank)
            if candidate.chunk_id not in merged:
                merged[candidate.chunk_id] = EvidenceCandidate(
                    **candidate.model_dump(),
                    fused_score=0.0,
                    channel_ranks={},
                    channel_scores={},
                )
            current = merged[candidate.chunk_id]
            current.fused_score += contribution
            current.channel_ranks[channel] = min(rank, current.channel_ranks.get(channel, rank))
            current.channel_scores[channel] = candidate.score
            if current.citation is None and candidate.citation is not None:
                current.citation = candidate.citation
            if not current.metadata and candidate.metadata:
                current.metadata = candidate.metadata

    return sorted(
        merged.values(),
        key=lambda candidate: (
            -candidate.fused_score,
            min(candidate.channel_ranks.values()) if candidate.channel_ranks else 999999,
            candidate.chunk_id,
        ),
    )[:top_k]


def normalize_candidate(raw_candidate: SearchCandidate | FullTextSearchResult | Any) -> SearchCandidate:
    if isinstance(raw_candidate, SearchCandidate):
        return raw_candidate
    if isinstance(raw_candidate, FullTextSearchResult):
        return SearchCandidate(
            chunk_id=raw_candidate.chunk_id,
            knowledge_item_id=raw_candidate.knowledge_item_id,
            text=raw_candidate.text,
            heading_path=raw_candidate.heading_path,
            ordinal=raw_candidate.ordinal,
            score=raw_candidate.score,
            citation=raw_candidate.citation,
        )
    return SearchCandidate(
        chunk_id=str(getattr(raw_candidate, "chunk_id")),
        knowledge_item_id=str(getattr(raw_candidate, "knowledge_item_id")),
        text=str(getattr(raw_candidate, "text")),
        heading_path=list(getattr(raw_candidate, "heading_path", []) or []),
        ordinal=getattr(raw_candidate, "ordinal", None),
        score=float(getattr(raw_candidate, "score", 0.0) or 0.0),
        citation=getattr(raw_candidate, "citation", None),
        metadata=dict(getattr(raw_candidate, "metadata", {}) or {}),
    )


def normalize_filters(filters: FullTextSearchFilters | dict | None) -> FullTextSearchFilters:
    if filters is None:
        return FullTextSearchFilters()
    if isinstance(filters, FullTextSearchFilters):
        return filters
    return FullTextSearchFilters.model_validate(filters)


def candidate_matches(candidate: SearchCandidate, filters: FullTextSearchFilters) -> bool:
    expected = filters.model_dump(exclude_none=True)
    if not expected:
        return True
    values = candidate_filter_values(candidate)
    return all(str(values.get(key, "")) == str(value) for key, value in expected.items())


def candidate_filter_values(candidate: SearchCandidate) -> dict[str, str]:
    citation = candidate.citation
    values = {
        "knowledge_item_id": candidate.knowledge_item_id,
        "source_id": citation.source_id if citation and citation.source_id else "",
        "asset_id": citation.asset_id if citation and citation.asset_id else "",
        "file_path": str(citation.file_path) if citation and citation.file_path else "",
    }
    values.update({key: str(value) for key, value in candidate.metadata.items() if value is not None})
    return values
