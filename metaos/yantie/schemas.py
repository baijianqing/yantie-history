"""Pydantic schemas for the Yantie meeting evidence pack."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


def _require_utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("datetime must include a UTC timezone")
    if offset != timedelta(0):
        raise ValueError("datetime must use UTC offset +00:00")
    return value.astimezone(timezone.utc)


NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, strict=True),
]
EvidenceId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^ev:[^:]+:.+:.+:[0-9a-f]{8}$", strict=True),
]
UtcDateTime = Annotated[datetime, AfterValidator(_require_utc)]


class YantieModel(BaseModel):
    """Closed JSON object used by the Yantie deliverable pack."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceType(str, Enum):
    primary_text = "primary_text"
    chronicle = "chronicle"
    institutional_history = "institutional_history"
    biography = "biography"
    later_commentary = "later_commentary"
    modern_research = "modern_research"
    external_echo = "external_echo"


class AuthorityLevel(str, Enum):
    core = "core"
    background = "background"
    comparison = "comparison"
    echo = "echo"


class LicenseStatus(str, Enum):
    public_domain_text = "public_domain_text"
    licensed_excerpt = "licensed_excerpt"
    link_only = "link_only"
    blocked = "blocked"
    unknown = "unknown"


class DeliveryPolicy(str, Enum):
    excerpt_allowed = "excerpt_allowed"
    metadata_only = "metadata_only"
    link_only = "link_only"
    exclude = "exclude"


class EvidenceKind(str, Enum):
    event_record = "event_record"
    policy_record = "policy_record"
    speech_argument = "speech_argument"
    biographical_context = "biographical_context"
    later_evaluation = "later_evaluation"


class Certainty(str, Enum):
    direct_text = "direct_text"
    high_confidence_context = "high_confidence_context"
    contested = "contested"
    needs_review = "needs_review"


class ReviewStatus(str, Enum):
    candidate = "candidate"
    verified = "verified"
    blocked = "blocked"


class ClaimType(str, Enum):
    original_fact = "original_fact"
    curatorial_inference = "curatorial_inference"
    contested_view = "contested_view"
    personal_reflection_prompt = "personal_reflection_prompt"


class ClaimStance(str, Enum):
    supports_state_monopoly = "supports_state_monopoly"
    opposes_state_monopoly = "opposes_state_monopoly"
    explains_context = "explains_context"
    evaluates_afterlife = "evaluates_afterlife"
    neutral = "neutral"


class DisplayZone(str, Enum):
    meeting = "meeting"
    map = "map"
    evidence_room = "evidence_room"
    power_network = "power_network"
    later_echo = "later_echo"
    judgment_card = "judgment_card"


class MeetingPosition(str, Enum):
    state_policy_defender = "state_policy_defender"
    literati_opposition = "literati_opposition"
    regent_power = "regent_power"
    imperial_center = "imperial_center"
    mediator = "mediator"
    background_actor = "background_actor"


class EventType(str, Enum):
    policy_background = "policy_background"
    meeting_session = "meeting_session"
    political_context = "political_context"
    policy_result = "policy_result"
    later_evaluation = "later_evaluation"


class RelationType(str, Enum):
    supports = "supports"
    opposes = "opposes"
    contextualizes = "contextualizes"
    caused_by = "caused_by"
    actor_interest = "actor_interest"
    value_conflict = "value_conflict"
    power_constraint = "power_constraint"


class RelationStrength(str, Enum):
    explicit_source = "explicit_source"
    contextual_inference = "contextual_inference"
    interpretive_hypothesis = "interpretive_hypothesis"


class MapLayerType(str, Enum):
    region = "region"
    route = "route"
    resource_point = "resource_point"
    military_frontier = "military_frontier"
    capital = "capital"
    policy_pressure = "policy_pressure"


class SourceManifestEntry(YantieModel):
    source_id: NonEmptyString
    title: NonEmptyString
    license_status: LicenseStatus
    delivery_policy: DeliveryPolicy
    excerpt_count: int = Field(ge=0)
    human_verified: bool
    note: NonEmptyString


class EvidenceRequirementSpec(YantieModel):
    requirement_id: NonEmptyString
    requirement_type: NonEmptyString
    description: NonEmptyString
    minimum_count: int = Field(default=1, ge=1)
    required_source_types: list[SourceType] = Field(default_factory=list)
    counterevidence_required: bool = False


class ThemeSpec(YantieModel):
    theme_id: NonEmptyString
    title: NonEmptyString
    historical_period: NonEmptyString
    core_question: NonEmptyString
    experience_mode: NonEmptyString
    evidence_requirements: list[EvidenceRequirementSpec] = Field(default_factory=list)
    value_axes: list[NonEmptyString] = Field(default_factory=list)
    output_contract: dict[str, Any]

    @field_validator("value_axes")
    @classmethod
    def validate_value_axes(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "value_axes")


class Source(YantieModel):
    source_id: NonEmptyString
    title: NonEmptyString
    source_type: SourceType
    authority_level: AuthorityLevel
    license_status: LicenseStatus
    canonical_url: NonEmptyString | None = None
    citation_style: NonEmptyString
    delivery_policy: DeliveryPolicy
    human_verified: bool

    @model_validator(mode="after")
    def validate_source_boundary(self) -> "Source":
        if self.source_type == SourceType.external_echo and self.authority_level != AuthorityLevel.echo:
            raise ValueError("external echo sources must use echo authority level")
        if self.license_status == LicenseStatus.blocked and self.delivery_policy != DeliveryPolicy.exclude:
            raise ValueError("blocked sources must use exclude delivery policy")
        if self.delivery_policy == DeliveryPolicy.excerpt_allowed and self.license_status not in {
            LicenseStatus.public_domain_text,
            LicenseStatus.licensed_excerpt,
        }:
            raise ValueError("excerpt delivery requires public domain or licensed excerpt status")
        return self


class Topic(YantieModel):
    topic_id: NonEmptyString
    title: NonEmptyString
    summary: NonEmptyString
    value_axes: list[NonEmptyString] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)


class EvidenceUnit(YantieModel):
    evidence_id: EvidenceId
    source_id: NonEmptyString
    canonical_location: NonEmptyString
    excerpt_original: NonEmptyString | None = None
    paraphrase_zh: NonEmptyString
    evidence_kind: EvidenceKind
    speaker_actor_id: NonEmptyString | None = None
    topic_ids: list[NonEmptyString] = Field(default_factory=list)
    value_tags: list[NonEmptyString] = Field(default_factory=list)
    certainty: Certainty
    copyright_note: NonEmptyString
    review_status: ReviewStatus
    adjacent_context_note: NonEmptyString | None = None

    @field_validator("topic_ids", "value_tags")
    @classmethod
    def validate_string_lists(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "list")


class ExternalReference(YantieModel):
    external_reference_id: NonEmptyString
    provider: NonEmptyString
    title: NonEmptyString
    url: NonEmptyString
    summary: NonEmptyString | None = None
    source_boundary: SourceType = SourceType.external_echo

    @model_validator(mode="after")
    def validate_source_boundary(self) -> "ExternalReference":
        if self.source_boundary != SourceType.external_echo:
            raise ValueError("external references must remain external_echo")
        return self


class Claim(YantieModel):
    claim_id: NonEmptyString
    claim_type: ClaimType
    statement: NonEmptyString
    stance: ClaimStance
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    counterevidence_ids: list[EvidenceId] = Field(default_factory=list)
    external_reference_ids: list[NonEmptyString] = Field(default_factory=list)
    reasoning_note: NonEmptyString | None = None
    display_zone: DisplayZone

    @model_validator(mode="after")
    def validate_claim_shape(self) -> "Claim":
        if self.claim_type != ClaimType.personal_reflection_prompt and not self.evidence_ids:
            raise ValueError("non-reflection claims require evidence")
        if self.claim_type == ClaimType.personal_reflection_prompt and self.evidence_ids:
            raise ValueError("personal reflection prompts cannot claim historical evidence")
        if self.claim_type == ClaimType.curatorial_inference and self.reasoning_note is None:
            raise ValueError("curatorial inference claims require a reasoning note")
        return self


class Actor(YantieModel):
    actor_id: NonEmptyString
    name: NonEmptyString
    role_title: NonEmptyString
    meeting_position: MeetingPosition
    stance_summary: NonEmptyString
    interest_constraints: list[NonEmptyString] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)

    @field_validator("interest_constraints")
    @classmethod
    def validate_constraints(cls, values: list[str]) -> list[str]:
        return _unique_non_empty(values, "interest_constraints")


class Event(YantieModel):
    event_id: NonEmptyString
    title: NonEmptyString
    date_label: NonEmptyString
    event_type: EventType
    summary: NonEmptyString
    location_id: NonEmptyString | None = None
    actor_ids: list[NonEmptyString] = Field(default_factory=list)
    topic_ids: list[NonEmptyString] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)


class Relation(YantieModel):
    relation_id: NonEmptyString
    from_id: NonEmptyString
    to_id: NonEmptyString
    relation_type: RelationType
    evidence_ids: list[EvidenceId] = Field(min_length=1)
    strength: RelationStrength
    note: NonEmptyString | None = None

    @model_validator(mode="after")
    def validate_inference_note(self) -> "Relation":
        if self.strength != RelationStrength.explicit_source and self.note is None:
            raise ValueError("inferred relations require a note")
        return self


class MapFeature(YantieModel):
    feature_id: NonEmptyString
    title: NonEmptyString
    summary: NonEmptyString
    coordinates: list[float] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, values: list[float]) -> list[float]:
        if values and len(values) != 2:
            raise ValueError("coordinates must be empty or contain [x, y]")
        return values


class MapLayer(YantieModel):
    layer_id: NonEmptyString
    title: NonEmptyString
    layer_type: MapLayerType
    time_scope: NonEmptyString
    features: list[MapFeature] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)
    display_style: dict[str, Any] = Field(default_factory=dict)


class CuratedPathStep(YantieModel):
    order: int = Field(ge=1)
    title: NonEmptyString
    claim_ids: list[NonEmptyString] = Field(default_factory=list)
    evidence_ids: list[EvidenceId] = Field(default_factory=list)


class CuratedPath(YantieModel):
    path_id: NonEmptyString
    title: NonEmptyString
    summary: NonEmptyString
    steps: list[CuratedPathStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_step_order(self) -> "CuratedPath":
        orders = [step.order for step in self.steps]
        if len(orders) != len(set(orders)):
            raise ValueError("curated path step order must be unique")
        return self


class LexicalIndex(YantieModel):
    tokenization: NonEmptyString = "char_bigram_zh_v1"
    entries: dict[NonEmptyString, list[EvidenceId]] = Field(default_factory=dict)

    @field_validator("entries")
    @classmethod
    def validate_entries(cls, entries: dict[str, list[str]]) -> dict[str, list[str]]:
        cleaned: dict[str, list[str]] = {}
        for token, evidence_ids in entries.items():
            text = token.strip()
            if not text:
                raise ValueError("lexical index tokens cannot be blank")
            cleaned[text] = _unique_non_empty(evidence_ids, "lexical index evidence ids")
        return cleaned


class EvidencePackMeta(YantieModel):
    schema_version: NonEmptyString = "yantie_evidence_pack_v1"
    pack_id: NonEmptyString = "yantie_meeting_v1"
    generated_at: UtcDateTime


class EvidencePack(YantieModel):
    schema_version: NonEmptyString = "yantie_evidence_pack_v1"
    pack_id: NonEmptyString = "yantie_meeting_v1"
    generated_at: UtcDateTime
    source_manifest: list[SourceManifestEntry] = Field(default_factory=list)
    theme_spec: ThemeSpec
    sources: list[Source] = Field(default_factory=list)
    actors: list[Actor] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    evidence_units: list[EvidenceUnit] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    map_layers: list[MapLayer] = Field(default_factory=list)
    curated_paths: list[CuratedPath] = Field(default_factory=list)
    external_references: list[ExternalReference] = Field(default_factory=list)
    lexical_index: LexicalIndex = Field(default_factory=LexicalIndex)

    @model_validator(mode="after")
    def validate_pack_links(self) -> "EvidencePack":
        source_ids = _unique_ids([source.source_id for source in self.sources], "sources")
        actor_ids = _unique_ids([actor.actor_id for actor in self.actors], "actors")
        topic_ids = _unique_ids([topic.topic_id for topic in self.topics], "topics")
        evidence_ids = _unique_ids([evidence.evidence_id for evidence in self.evidence_units], "evidence_units")
        claim_ids = _unique_ids([claim.claim_id for claim in self.claims], "claims")
        event_ids = _unique_ids([event.event_id for event in self.events], "events")
        relation_ids = _unique_ids([relation.relation_id for relation in self.relations], "relations")
        external_reference_ids = _unique_ids(
            [reference.external_reference_id for reference in self.external_references],
            "external_references",
        )

        sources_by_id = {source.source_id: source for source in self.sources}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in self.evidence_units}
        allowed_relation_targets = source_ids | actor_ids | topic_ids | evidence_ids | claim_ids | event_ids

        for manifest_entry in self.source_manifest:
            _require_present(manifest_entry.source_id, source_ids, "source_manifest.source_id")

        for topic in self.topics:
            _require_all_present(topic.evidence_ids, evidence_ids, f"topic {topic.topic_id} evidence_ids")

        for evidence in self.evidence_units:
            source = sources_by_id.get(evidence.source_id)
            if source is None:
                raise ValueError(f"evidence {evidence.evidence_id} references unknown source")
            if evidence.speaker_actor_id is not None:
                _require_present(evidence.speaker_actor_id, actor_ids, f"evidence {evidence.evidence_id} speaker")
            _require_all_present(evidence.topic_ids, topic_ids, f"evidence {evidence.evidence_id} topic_ids")
            _validate_evidence_delivery(evidence, source)

        for actor in self.actors:
            _require_all_present(actor.evidence_ids, evidence_ids, f"actor {actor.actor_id} evidence_ids")

        for event in self.events:
            _require_all_present(event.actor_ids, actor_ids, f"event {event.event_id} actor_ids")
            _require_all_present(event.topic_ids, topic_ids, f"event {event.event_id} topic_ids")
            _require_all_present(event.evidence_ids, evidence_ids, f"event {event.event_id} evidence_ids")

        for claim in self.claims:
            _require_all_present(claim.evidence_ids, evidence_ids, f"claim {claim.claim_id} evidence_ids")
            _require_all_present(
                claim.counterevidence_ids,
                evidence_ids,
                f"claim {claim.claim_id} counterevidence_ids",
            )
            _require_all_present(
                claim.external_reference_ids,
                external_reference_ids,
                f"claim {claim.claim_id} external_reference_ids",
            )
            _validate_claim_evidence(claim, evidence_by_id, sources_by_id)

        for relation in self.relations:
            _require_present(relation.from_id, allowed_relation_targets, f"relation {relation.relation_id} from_id")
            _require_present(relation.to_id, allowed_relation_targets, f"relation {relation.relation_id} to_id")
            _require_all_present(relation.evidence_ids, evidence_ids, f"relation {relation.relation_id} evidence_ids")

        for layer in self.map_layers:
            _require_all_present(layer.evidence_ids, evidence_ids, f"map layer {layer.layer_id} evidence_ids")
            for feature in layer.features:
                _require_all_present(
                    feature.evidence_ids,
                    evidence_ids,
                    f"map feature {feature.feature_id} evidence_ids",
                )

        for path in self.curated_paths:
            for step in path.steps:
                _require_all_present(step.claim_ids, claim_ids, f"curated path {path.path_id} claim_ids")
                _require_all_present(step.evidence_ids, evidence_ids, f"curated path {path.path_id} evidence_ids")

        for token, indexed_evidence_ids in self.lexical_index.entries.items():
            _require_all_present(indexed_evidence_ids, evidence_ids, f"lexical index token {token}")

        _ = relation_ids
        return self


def _unique_non_empty(values: list[str], field_name: str) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} cannot contain blank values")
        if text in seen:
            raise ValueError(f"{field_name} cannot contain duplicate values")
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _unique_ids(values: list[str], field_name: str) -> set[str]:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"{field_name} contains duplicate id {value}")
        seen.add(value)
    return seen


def _require_present(value: str, allowed_values: set[str], field_name: str) -> None:
    if value not in allowed_values:
        raise ValueError(f"{field_name} references unknown id {value}")


def _require_all_present(values: list[str], allowed_values: set[str], field_name: str) -> None:
    for value in values:
        _require_present(value, allowed_values, field_name)


def _validate_evidence_delivery(evidence: EvidenceUnit, source: Source) -> None:
    if source.source_type == SourceType.external_echo and evidence.review_status != ReviewStatus.blocked:
        raise ValueError("external echo sources cannot produce historical evidence")
    if source.delivery_policy == DeliveryPolicy.exclude and evidence.review_status != ReviewStatus.blocked:
        raise ValueError("excluded sources cannot produce usable evidence")
    if source.delivery_policy != DeliveryPolicy.excerpt_allowed and evidence.excerpt_original is not None:
        raise ValueError("non-excerpt sources cannot carry original excerpts")
    if evidence.review_status == ReviewStatus.verified and source.delivery_policy == DeliveryPolicy.exclude:
        raise ValueError("verified evidence cannot come from excluded sources")


def _validate_claim_evidence(
    claim: Claim,
    evidence_by_id: dict[str, EvidenceUnit],
    sources_by_id: dict[str, Source],
) -> None:
    for evidence_id in [*claim.evidence_ids, *claim.counterevidence_ids]:
        evidence = evidence_by_id[evidence_id]
        source = sources_by_id[evidence.source_id]
        if source.source_type == SourceType.external_echo:
            raise ValueError("external echo evidence cannot support historical claims")
        if evidence.review_status != ReviewStatus.verified:
            raise ValueError("claims can only cite verified evidence")

    if claim.claim_type == ClaimType.original_fact:
        if not any(evidence_by_id[evidence_id].certainty == Certainty.direct_text for evidence_id in claim.evidence_ids):
            raise ValueError("original fact claims require direct text evidence")
