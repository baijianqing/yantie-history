"""Lightweight read-only search for the Yantie evidence pack."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator

from metaos.yantie.schemas import (
    Actor,
    Certainty,
    EvidenceKind,
    EvidencePack,
    EvidenceUnit,
    NonEmptyString,
    ReviewStatus,
    Source,
    SourceType,
    Topic,
    YantieModel,
)


DEFAULT_EVIDENCE_PACK_PATH = Path(__file__).resolve().parent / "data" / "evidence_pack.json"
_SPLIT_PATTERN = re.compile(r"[\s,，;；、。！？!?（）()《》\"'“”‘’]+")
_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "财政": ("财政", "财用", "边费", "用度", "frontier_finance", "state_capacity", "fiscal_capacity"),
    "官营": ("官营", "国家", "盐铁", "state_monopoly"),
    "反对": ("反对", "罢", "与民争利", "贤良文学", "opposes", "anti_profit_governance"),
    "结果": ("结果", "罢榷酤", "罢酒榷", "盐铁如旧", "partial_result"),
    "会议": ("会议", "始元六年", "有司", "贤良文学", "meeting"),
    "桑弘羊": ("桑弘羊", "actor_sang_hongyang"),
    "霍光": ("霍光", "actor_huo_guang", "辅政"),
    "均输": ("均输", "委输", "equal_transport"),
    "榷酤": ("榷酤", "酒榷", "liquor_monopoly"),
    "边防": ("边防", "边费", "匈奴", "frontier_security"),
}


class SearchArchiveStatus(str, Enum):
    ok = "ok"
    archive_insufficient = "archive_insufficient"


class EvidenceSearchFilters(YantieModel):
    source_ids: list[NonEmptyString] = Field(default_factory=list)
    topic_ids: list[NonEmptyString] = Field(default_factory=list)
    actor_ids: list[NonEmptyString] = Field(default_factory=list)
    source_types: list[SourceType] = Field(default_factory=list)
    evidence_kinds: list[EvidenceKind] = Field(default_factory=list)
    certainty: list[Certainty] = Field(default_factory=list)
    value_tags: list[NonEmptyString] = Field(default_factory=list)
    verified_only: bool = True

    @field_validator("source_ids", "topic_ids", "actor_ids", "value_tags")
    @classmethod
    def validate_string_filters(cls, values: list[str]) -> list[str]:
        return _clean_unique_strings(values)

    @field_validator("source_types", "evidence_kinds", "certainty")
    @classmethod
    def validate_enum_filters(cls, values: list[Any]) -> list[Any]:
        return _clean_unique_enums(values)


class EvidenceSearchResult(YantieModel):
    evidence: EvidenceUnit
    source: Source
    speaker: Actor | None = None
    score: int = Field(ge=0)
    matched_terms: list[NonEmptyString] = Field(default_factory=list)
    match_reasons: list[NonEmptyString] = Field(default_factory=list)


class SearchResultList(YantieModel):
    query: str
    filters: EvidenceSearchFilters
    limit: int = Field(ge=0, le=100)
    total: int = Field(ge=0)
    archive_status: SearchArchiveStatus
    message: NonEmptyString | None = None
    results: list[EvidenceSearchResult] = Field(default_factory=list)


def load_default_evidence_pack(path: str | Path = DEFAULT_EVIDENCE_PACK_PATH) -> EvidencePack:
    return _load_evidence_pack(str(Path(path).resolve()))


@lru_cache(maxsize=8)
def _load_evidence_pack(resolved_path: str) -> EvidencePack:
    payload = json.loads(Path(resolved_path).read_text(encoding="utf-8"))
    return EvidencePack.model_validate(payload)


def search_evidence(
    query: str,
    filters: EvidenceSearchFilters | dict[str, Any] | None = None,
    limit: int = 10,
    *,
    pack: EvidencePack | None = None,
) -> SearchResultList:
    evidence_pack = pack or load_default_evidence_pack()
    normalized_filters = normalize_filters(filters)
    clean_query = query.strip()
    clean_limit = max(0, min(int(limit), 100))
    query_terms = _query_terms(clean_query)
    expanded_terms = _expanded_terms(query_terms)
    lexical_hits = _lexical_hits(evidence_pack, expanded_terms)

    sources_by_id = {source.source_id: source for source in evidence_pack.sources}
    actors_by_id = {actor.actor_id: actor for actor in evidence_pack.actors}
    topics_by_id = {topic.topic_id: topic for topic in evidence_pack.topics}
    actor_ids_by_evidence = _actor_ids_by_evidence(evidence_pack.actors)
    ranked_results: list[tuple[int, int, EvidenceSearchResult]] = []

    for ordinal, evidence in enumerate(evidence_pack.evidence_units):
        source = sources_by_id[evidence.source_id]
        if not _matches_filters(evidence, source, normalized_filters, actor_ids_by_evidence):
            continue

        score, matched_terms, match_reasons = _score_evidence(
            evidence,
            source,
            actors_by_id,
            topics_by_id,
            query_terms,
            expanded_terms,
            lexical_hits,
        )
        if query_terms and score <= 0:
            continue
        if not query_terms:
            score = 1
            match_reasons = ["filter_match"]

        speaker = actors_by_id.get(evidence.speaker_actor_id or "")
        ranked_results.append(
            (
                score,
                ordinal,
                EvidenceSearchResult(
                    evidence=evidence,
                    source=source,
                    speaker=speaker,
                    score=score,
                    matched_terms=matched_terms,
                    match_reasons=match_reasons,
                ),
            )
        )

    ranked_results.sort(key=lambda item: (-item[0], item[1]))
    results = [result for _, _, result in ranked_results[:clean_limit]]
    status = SearchArchiveStatus.ok if results else SearchArchiveStatus.archive_insufficient
    message = None if results else "No verified evidence matches this query."
    return SearchResultList(
        query=clean_query,
        filters=normalized_filters,
        limit=clean_limit,
        total=len(ranked_results),
        archive_status=status,
        message=message,
        results=results,
    )


def normalize_filters(filters: EvidenceSearchFilters | dict[str, Any] | None) -> EvidenceSearchFilters:
    if filters is None:
        return EvidenceSearchFilters()
    if isinstance(filters, EvidenceSearchFilters):
        return filters
    return EvidenceSearchFilters.model_validate(filters)


def _query_terms(query: str) -> list[str]:
    return _clean_unique_strings(term.casefold() for term in _SPLIT_PATTERN.split(query.strip()) if term)


def _expanded_terms(query_terms: list[str]) -> dict[str, list[str]]:
    expanded: dict[str, list[str]] = {}
    for term in query_terms:
        aliases = _QUERY_ALIASES.get(term, ())
        expanded[term] = _clean_unique_strings([term, *aliases])
    return expanded


def _lexical_hits(pack: EvidencePack, expanded_terms: dict[str, list[str]]) -> dict[str, set[str]]:
    hits: dict[str, set[str]] = {}
    for index_token, evidence_ids in pack.lexical_index.entries.items():
        normalized_token = index_token.casefold()
        matched_query_terms = [
            query_term
            for query_term, aliases in expanded_terms.items()
            if any(alias in normalized_token or normalized_token in alias for alias in aliases)
        ]
        if not matched_query_terms:
            continue
        for evidence_id in evidence_ids:
            hits.setdefault(evidence_id, set()).update(matched_query_terms)
    return hits


def _score_evidence(
    evidence: EvidenceUnit,
    source: Source,
    actors_by_id: dict[str, Actor],
    topics_by_id: dict[str, Topic],
    query_terms: list[str],
    expanded_terms: dict[str, list[str]],
    lexical_hits: dict[str, set[str]],
) -> tuple[int, list[str], list[str]]:
    if not query_terms:
        return 0, [], []

    primary_text = _normalize_text(
        " ".join(
            [
                evidence.evidence_id,
                evidence.canonical_location,
                evidence.excerpt_original or "",
                evidence.paraphrase_zh,
                evidence.evidence_kind.value,
                evidence.certainty.value,
                " ".join(evidence.value_tags),
            ]
        )
    )
    context_text = _normalize_text(
        " ".join(
            [
                primary_text,
                _source_text(source),
                _speaker_text(evidence, actors_by_id),
                _topic_text(evidence, topics_by_id),
            ]
        )
    )

    score = 0
    matched_terms: set[str] = set()
    match_reasons: set[str] = set()
    lexical_terms = lexical_hits.get(evidence.evidence_id, set())
    for query_term, aliases in expanded_terms.items():
        term_score = 0
        if query_term in lexical_terms:
            term_score += 25
            match_reasons.add("lexical_index")

        if any(alias in primary_text for alias in aliases):
            term_score += 20
            match_reasons.add("evidence_text")
        elif any(alias in context_text for alias in aliases):
            term_score += 10
            match_reasons.add("context_metadata")

        if term_score:
            matched_terms.add(query_term)
            score += term_score

    return score, sorted(matched_terms), sorted(match_reasons)


def _matches_filters(
    evidence: EvidenceUnit,
    source: Source,
    filters: EvidenceSearchFilters,
    actor_ids_by_evidence: dict[str, set[str]],
) -> bool:
    if filters.verified_only and evidence.review_status != ReviewStatus.verified:
        return False
    if filters.source_ids and evidence.source_id not in filters.source_ids:
        return False
    if filters.topic_ids and not set(evidence.topic_ids).intersection(filters.topic_ids):
        return False
    if filters.actor_ids:
        evidence_actor_ids = set(actor_ids_by_evidence.get(evidence.evidence_id, set()))
        if evidence.speaker_actor_id is not None:
            evidence_actor_ids.add(evidence.speaker_actor_id)
        if not evidence_actor_ids.intersection(filters.actor_ids):
            return False
    if filters.source_types and source.source_type not in filters.source_types:
        return False
    if filters.evidence_kinds and evidence.evidence_kind not in filters.evidence_kinds:
        return False
    if filters.certainty and evidence.certainty not in filters.certainty:
        return False
    if filters.value_tags and not set(evidence.value_tags).intersection(filters.value_tags):
        return False
    return True


def _actor_ids_by_evidence(actors: Iterable[Actor]) -> dict[str, set[str]]:
    actor_ids_by_evidence: dict[str, set[str]] = {}
    for actor in actors:
        for evidence_id in actor.evidence_ids:
            actor_ids_by_evidence.setdefault(evidence_id, set()).add(actor.actor_id)
    return actor_ids_by_evidence


def _source_text(source: Source) -> str:
    return _normalize_text(
        " ".join(
            [
                source.source_id,
                source.title,
                source.source_type.value,
                source.authority_level.value,
                source.citation_style,
                source.canonical_url or "",
            ]
        )
    )


def _speaker_text(evidence: EvidenceUnit, actors_by_id: dict[str, Actor]) -> str:
    speaker = actors_by_id.get(evidence.speaker_actor_id or "")
    if speaker is None:
        return ""
    return _normalize_text(
        " ".join(
            [
                speaker.actor_id,
                speaker.name,
                speaker.role_title,
                speaker.meeting_position.value,
                speaker.stance_summary,
                " ".join(speaker.interest_constraints),
            ]
        )
    )


def _topic_text(evidence: EvidenceUnit, topics_by_id: dict[str, Topic]) -> str:
    topic_parts: list[str] = []
    for topic_id in evidence.topic_ids:
        topic = topics_by_id.get(topic_id)
        if topic is None:
            continue
        topic_parts.extend([topic.topic_id, topic.title, topic.summary, " ".join(topic.value_axes)])
    return _normalize_text(" ".join(topic_parts))


def _normalize_text(value: str) -> str:
    return value.casefold()


def _clean_unique_strings(values: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _clean_unique_enums(values: Iterable[Any]) -> list[Any]:
    cleaned: list[Any] = []
    seen: set[Any] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned
