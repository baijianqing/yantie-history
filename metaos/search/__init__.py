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

__all__ = [
    "DEFAULT_RRF_K",
    "EvidenceCandidate",
    "FullTextSearchFilters",
    "FullTextSearchResult",
    "SearchCandidate",
    "full_text_search",
    "rrf_fuse",
]
