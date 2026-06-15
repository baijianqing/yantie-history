"""Research execution service helpers for candidate recall."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from metaos.compiler import EvidenceRequirement, ResearchCompilation
from metaos.research.executor import ResearchExecutionDraft, build_evidence_matrix
from metaos.search import EvidenceCandidate


class EvidenceSearch(Protocol):
    def __call__(self, query: str, *, top_k: int = 5) -> Sequence[EvidenceCandidate]:
        """Return evidence candidates for one query."""


COUNTER_STANCE_TERMS = (
    "counter",
    "counterevidence",
    "contradict",
    "dispute",
    "weaken",
    "gap",
    "missing",
    "not enough",
    "fails",
    "however",
)


def execute_research_plan(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> ResearchExecutionDraft:
    candidates = retrieve_research_candidates(
        compilation,
        search,
        top_k_per_query=top_k_per_query,
    )
    return build_evidence_matrix(compilation, candidates)


def retrieve_research_candidates(
    compilation: ResearchCompilation,
    search: EvidenceSearch,
    *,
    top_k_per_query: int = 5,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for requirement in compilation.evidence_requirements:
        for query in queries_for_requirement(compilation, requirement):
            for candidate in search(query, top_k=max(1, top_k_per_query)):
                tagged = tag_candidate(candidate, requirement=requirement, query=query)
                key = (
                    requirement.id,
                    tagged.chunk_id,
                    str(tagged.metadata.get("stance", "support")),
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(tagged)
    return candidates


def queries_for_requirement(
    compilation: ResearchCompilation,
    requirement: EvidenceRequirement,
) -> list[str]:
    queries = [requirement.description]
    queries.extend(
        query
        for query in compilation.research_plan.query_plan
        if query_targets_requirement(query, requirement)
    )
    for step in compilation.research_plan.steps:
        target_text = " ".join([step.description, *step.expected_evidence])
        if query_targets_requirement(target_text, requirement):
            queries.extend(step.query_hints)
    return dedupe_queries(queries)


def tag_candidate(
    candidate: EvidenceCandidate,
    *,
    requirement: EvidenceRequirement,
    query: str,
) -> EvidenceCandidate:
    metadata = dict(candidate.metadata or {})
    metadata.setdefault("requirement_id", requirement.id)
    metadata.setdefault("requirement_type", requirement.requirement_type.value)
    metadata.setdefault("query", query)
    metadata.setdefault("stance", infer_stance(candidate))
    return candidate.model_copy(update={"metadata": metadata})


def infer_stance(candidate: EvidenceCandidate) -> str:
    raw_stance = str((candidate.metadata or {}).get("stance") or "").strip().lower()
    if raw_stance:
        return "counter" if raw_stance in {"counter", "counterevidence", "contradicts"} else "support"
    text = candidate.text.lower()
    if any(term in text for term in COUNTER_STANCE_TERMS):
        return "counter"
    return "support"


def dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for query in queries:
        text = query.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def query_targets_requirement(query: str, requirement: EvidenceRequirement) -> bool:
    text = query.lower()
    return requirement.id.lower() in text or requirement.requirement_type.value in text
