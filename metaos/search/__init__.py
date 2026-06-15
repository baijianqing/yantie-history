"""Search contracts and services for MetaOS Alpha."""

from metaos.search.fusion import (
    DEFAULT_RRF_K,
    EvidenceCandidate,
    SearchCandidate,
    rrf_fuse,
)
from metaos.search.full_text import (
    FullTextSearchFilters,
    FullTextSearchResult,
    full_text_search,
)
from metaos.search.hybrid import hybrid_search
from metaos.search.vector import (
    VectorRetrievalService,
    search_result_to_candidate,
    vector_search,
)

__all__ = [
    "DEFAULT_RRF_K",
    "EvidenceCandidate",
    "FullTextSearchFilters",
    "FullTextSearchResult",
    "SearchCandidate",
    "VectorRetrievalService",
    "full_text_search",
    "hybrid_search",
    "rrf_fuse",
    "search_result_to_candidate",
    "vector_search",
]
