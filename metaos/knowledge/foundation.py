"""Structured knowledge foundation extraction for MetaOS Alpha."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from metaos.core.schemas import Citation
from metaos.knowledge.versioning import StandardizedDocument, StableChunk


class EntityType(str, Enum):
    person = "person"
    organization = "organization"
    place = "place"
    concept = "concept"
    work = "work"
    project = "project"
    event = "event"


class ClaimType(str, Enum):
    fact = "fact"
    interpretation = "interpretation"
    prediction = "prediction"
    recommendation = "recommendation"
    self_reflection = "self_reflection"


class ClaimStance(str, Enum):
    supports = "supports"
    disputes = "disputes"
    neutral = "neutral"


class EvidenceRelation(str, Enum):
    supports = "supports"
    counters = "counters"
    mentions = "mentions"


class SummaryLevel(str, Enum):
    document = "document"
    section = "section"
    chunk = "chunk"


class Entity(BaseModel):
    id: str
    stable_id: str
    name: str
    type: EntityType
    description: str = ""
    source_count: int = Field(default=1, ge=1)

    @field_validator("id", "stable_id", "name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class EntityAlias(BaseModel):
    id: str
    entity_id: str
    alias: str
    language: str | None = None
    confidence: float = Field(default=1.0, ge=0, le=1)

    @field_validator("id", "entity_id", "alias")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class Event(BaseModel):
    id: str
    stable_id: str
    title: str
    description: str = ""
    event_time: date | None = None
    time_precision: str = "day"
    participants: list[str] = Field(default_factory=list)
    location: str | None = None
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("id", "stable_id", "title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class Claim(BaseModel):
    id: str
    stable_id: str
    claim_text: str
    claim_type: ClaimType
    stance: ClaimStance = ClaimStance.neutral
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_id: str | None = None
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("id", "stable_id", "claim_text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class EvidenceLink(BaseModel):
    id: str
    claim_id: str
    chunk_id: str
    relation: EvidenceRelation
    citation: Citation

    @field_validator("id", "claim_id", "chunk_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class KnowledgeSummary(BaseModel):
    id: str
    level: SummaryLevel
    text: str
    target_id: str
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("id", "text", "target_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return clean_text(value)


class KnowledgeFoundation(BaseModel):
    document_version_id: str
    entities: list[Entity] = Field(default_factory=list)
    aliases: list[EntityAlias] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence_links: list[EvidenceLink] = Field(default_factory=list)
    summaries: list[KnowledgeSummary] = Field(default_factory=list)


def extract_knowledge_foundation(document: StandardizedDocument) -> KnowledgeFoundation:
    entity_mentions: dict[str, set[str]] = {}
    entity_data: dict[str, Entity] = {}
    aliases: list[EntityAlias] = []
    events: list[Event] = []
    claims: list[Claim] = []
    evidence_links: list[EvidenceLink] = []
    summaries: list[KnowledgeSummary] = []

    for chunk in document.chunks:
        citation = chunk.citation
        for line in chunk.text.splitlines():
            kind, payload = split_annotation(line)
            if kind == "entity":
                entity = parse_entity(payload)
                entity_data[entity.name] = entity
                entity_mentions.setdefault(entity.name, set()).add(chunk.id)
            elif kind == "alias":
                alias = parse_alias(payload, entity_data)
                if alias is not None:
                    aliases.append(alias)
            elif kind == "event":
                events.append(parse_event(payload, citation))
            elif kind == "claim":
                claim = parse_claim(payload, citation)
                claims.append(claim)
                if citation is not None:
                    evidence_links.append(evidence_link_for_claim(claim, chunk, citation))
            elif kind == "summary":
                summaries.append(parse_summary(payload, chunk, document.document_version.id, citation))

    entities = [
        entity.model_copy(update={"source_count": len(entity_mentions.get(entity.name, set())) or 1})
        for entity in entity_data.values()
    ]
    return KnowledgeFoundation(
        document_version_id=document.document_version.id,
        entities=entities,
        aliases=aliases,
        events=events,
        claims=claims,
        evidence_links=evidence_links,
        summaries=summaries,
    )


def split_annotation(line: str) -> tuple[str | None, str]:
    if ":" not in line:
        return None, ""
    prefix, payload = line.split(":", 1)
    kind = prefix.strip().lower()
    if kind not in {"entity", "alias", "event", "claim", "summary"}:
        return None, ""
    return kind, payload.strip()


def parse_entity(payload: str) -> Entity:
    name, raw_type, description = padded_parts(payload, 3)
    entity_type = EntityType(raw_type or EntityType.concept.value)
    stable = stable_id("entity", [name.lower(), entity_type.value])
    return Entity(
        id=stable,
        stable_id=stable,
        name=name,
        type=entity_type,
        description=description,
    )


def parse_alias(payload: str, entities: dict[str, Entity]) -> EntityAlias | None:
    entity_name, alias, language = padded_parts(payload, 3)
    entity = entities.get(entity_name)
    if entity is None:
        return None
    return EntityAlias(
        id=stable_id("alias", [entity.id, alias, language]),
        entity_id=entity.id,
        alias=alias,
        language=language or None,
    )


def parse_event(payload: str, citation: Citation | None) -> Event:
    raw_date, title, description, participants, location = padded_parts(payload, 5)
    event_date = date.fromisoformat(raw_date) if raw_date else None
    stable = stable_id("event", [raw_date, title, description])
    return Event(
        id=stable,
        stable_id=stable,
        title=title,
        description=description,
        event_time=event_date,
        participants=csv_parts(participants),
        location=location or None,
        citations=[citation] if citation else [],
    )


def parse_claim(payload: str, citation: Citation | None) -> Claim:
    raw_type, raw_stance, claim_text, raw_confidence = padded_parts(payload, 4)
    claim_type = ClaimType(raw_type or ClaimType.fact.value)
    stance = ClaimStance(raw_stance or ClaimStance.neutral.value)
    confidence = float(raw_confidence) if raw_confidence else 0.5
    stable = stable_id("claim", [claim_type.value, stance.value, claim_text])
    return Claim(
        id=stable,
        stable_id=stable,
        claim_text=claim_text,
        claim_type=claim_type,
        stance=stance,
        confidence=confidence,
        source_id=citation.source_id if citation else None,
        citations=[citation] if citation else [],
    )


def parse_summary(
    payload: str,
    chunk: StableChunk,
    document_version_id: str,
    citation: Citation | None,
) -> KnowledgeSummary:
    raw_level, text = padded_parts(payload, 2)
    level = SummaryLevel(raw_level or SummaryLevel.chunk.value)
    target_id = document_version_id if level == SummaryLevel.document else chunk.id
    return KnowledgeSummary(
        id=stable_id("summary", [level.value, target_id, text]),
        level=level,
        text=text,
        target_id=target_id,
        citations=[citation] if citation else [],
    )


def evidence_link_for_claim(claim: Claim, chunk: StableChunk, citation: Citation) -> EvidenceLink:
    relation = EvidenceRelation.counters if claim.stance == ClaimStance.disputes else EvidenceRelation.supports
    return EvidenceLink(
        id=stable_id("evlink", [claim.id, chunk.id, relation.value]),
        claim_id=claim.id,
        chunk_id=chunk.id,
        relation=relation,
        citation=citation,
    )


def padded_parts(payload: str, count: int) -> list[str]:
    parts = [part.strip() for part in payload.split("|")]
    return [*parts, *([""] * count)][:count]


def csv_parts(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def clean_text(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("field cannot be blank")
    return text


def stable_id(prefix: str, parts: list[str]) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"
