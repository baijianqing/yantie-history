"""Read-only REST API adapter for the Yantie meeting reconstruction."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator

from metaos.yantie.schemas import (
    AuthorityLevel,
    Claim,
    ClaimStance,
    ClaimType,
    DeliveryPolicy,
    DisplayZone,
    EvidenceId,
    EvidencePack,
    EventType,
    NonEmptyString,
    RelationStrength,
    RelationType,
    SourceType,
    YantieModel,
)
from metaos.yantie.search import (
    EvidenceSearchFilters,
    SearchArchiveStatus,
    load_default_evidence_pack,
    search_evidence,
)


class JudgmentDisposition(str, Enum):
    continue_research = "continue_research"
    historical_understanding_complete = "historical_understanding_complete"
    no_action = "no_action"
    modern_analogy_with_caution = "modern_analogy_with_caution"


class CreateJudgmentCardRequest(YantieModel):
    selected_claim_ids: list[NonEmptyString] = Field(default_factory=list)
    selected_evidence_ids: list[EvidenceId] = Field(default_factory=list)
    personal_reflection: NonEmptyString | None = None
    disposition: JudgmentDisposition = JudgmentDisposition.continue_research

    @model_validator(mode="after")
    def validate_selection(self) -> "CreateJudgmentCardRequest":
        if not self.selected_claim_ids and not self.selected_evidence_ids and self.personal_reflection is None:
            raise ValueError("judgment card requires at least one claim, evidence, or reflection")
        return self


def create_yantie_api_router(*, pack: EvidencePack | None = None) -> APIRouter:
    """Build the YT-A1-API-001 read-only router."""

    evidence_pack = pack or load_default_evidence_pack()
    router = APIRouter(prefix="/api/yantie", tags=["yantie"])

    @router.get("/manifest")
    def get_manifest() -> dict[str, Any]:
        source_type_counts = Counter(source.source_type.value for source in evidence_pack.sources)
        return _success_response(
            evidence_pack,
            {
                "pack_id": evidence_pack.pack_id,
                "schema_version": evidence_pack.schema_version,
                "generated_at": _dump_datetime(evidence_pack.generated_at),
                "source_count": len(evidence_pack.sources),
                "actor_count": len(evidence_pack.actors),
                "event_count": len(evidence_pack.events),
                "topic_count": len(evidence_pack.topics),
                "evidence_count": len(evidence_pack.evidence_units),
                "claim_count": len(evidence_pack.claims),
                "relation_count": len(evidence_pack.relations),
                "map_layer_count": len(evidence_pack.map_layers),
                "source_type_counts": dict(sorted(source_type_counts.items())),
                "features": {
                    "runtime_rag": False,
                    "vector_store": False,
                    "external_echo_enabled": False,
                    "local_judgment_cards": True,
                },
            },
        )

    @router.get("/theme")
    def get_theme() -> dict[str, Any]:
        return _success_response(evidence_pack, evidence_pack.theme_spec.model_dump(mode="json"))

    @router.get("/sources")
    def list_sources(
        source_type: SourceType | None = None,
        authority_level: AuthorityLevel | None = None,
        delivery_policy: DeliveryPolicy | None = None,
        human_verified: bool | None = None,
    ) -> dict[str, Any]:
        items = []
        for source in evidence_pack.sources:
            if source_type is not None and source.source_type != source_type:
                continue
            if authority_level is not None and source.authority_level != authority_level:
                continue
            if delivery_policy is not None and source.delivery_policy != delivery_policy:
                continue
            if human_verified is not None and source.human_verified != human_verified:
                continue
            items.append(source.model_dump(mode="json"))
        return _list_response(evidence_pack, items)

    @router.get("/actors")
    def list_actors(include: str | None = None) -> dict[str, Any]:
        include_evidence_summary = include == "evidence_summary"
        items = []
        for actor in evidence_pack.actors:
            row = actor.model_dump(mode="json")
            if include_evidence_summary:
                row["evidence_summary"] = {
                    "evidence_count": len(actor.evidence_ids),
                    "evidence_ids": actor.evidence_ids,
                }
            items.append(row)
        return _list_response(evidence_pack, items)

    @router.get("/events")
    def list_events(
        event_type: EventType | None = None,
        actor_id: str | None = None,
        topic_id: str | None = None,
    ) -> dict[str, Any]:
        items = []
        for event in evidence_pack.events:
            if event_type is not None and event.event_type != event_type:
                continue
            if actor_id is not None and actor_id not in event.actor_ids:
                continue
            if topic_id is not None and topic_id not in event.topic_ids:
                continue
            items.append(event.model_dump(mode="json"))
        return _list_response(evidence_pack, items)

    @router.get("/map-layers")
    def list_map_layers() -> dict[str, Any]:
        return _list_response(
            evidence_pack,
            [layer.model_dump(mode="json") for layer in evidence_pack.map_layers],
        )

    @router.get("/topics")
    def list_topics() -> dict[str, Any]:
        return _list_response(evidence_pack, [topic.model_dump(mode="json") for topic in evidence_pack.topics])

    @router.get("/evidence/search")
    def search_evidence_route(
        q: Annotated[str, Query()] = "",
        topic_id: str | None = None,
        actor_id: str | None = None,
        source_id: str | None = None,
        source_type: SourceType | None = None,
        claim_type: ClaimType | None = None,
        limit: Annotated[int, Query(ge=0, le=50)] = 20,
    ) -> dict[str, Any]:
        filters = EvidenceSearchFilters(
            source_ids=[source_id] if source_id else [],
            topic_ids=[topic_id] if topic_id else [],
            actor_ids=[actor_id] if actor_id else [],
            source_types=[source_type] if source_type else [],
        )
        search_limit = 100 if claim_type is not None else limit
        result_list = search_evidence(q, filters=filters, limit=search_limit, pack=evidence_pack)
        results = result_list.results

        if claim_type is not None:
            evidence_ids_for_claim_type = _evidence_ids_for_claim_type(evidence_pack, claim_type)
            results = [
                result for result in results if result.evidence.evidence_id in evidence_ids_for_claim_type
            ][:limit]

        archive_status = SearchArchiveStatus.ok if results else SearchArchiveStatus.archive_insufficient
        message = None if results else "No verified evidence matches this query."
        return _success_response(
            evidence_pack,
            {
                "items": [result.model_dump(mode="json") for result in results],
                "total": len(results),
                "archive_status": archive_status.value,
                "message": message,
            },
        )

    @router.get("/evidence/{evidence_id}")
    def get_evidence(evidence_id: str) -> Any:
        evidence = _evidence_by_id(evidence_pack).get(evidence_id)
        if evidence is None:
            return _error_response(evidence_pack, 404, "not_found", f"Evidence unit not found: {evidence_id}")
        return _success_response(evidence_pack, evidence.model_dump(mode="json"))

    @router.get("/claims")
    def list_claims(
        topic_id: str | None = None,
        stance: ClaimStance | None = None,
        display_zone: DisplayZone | None = None,
        claim_type: ClaimType | None = None,
    ) -> dict[str, Any]:
        evidence_by_id = _evidence_by_id(evidence_pack)
        items = []
        for claim in evidence_pack.claims:
            if claim_type is not None and claim.claim_type != claim_type:
                continue
            if stance is not None and claim.stance != stance:
                continue
            if display_zone is not None and claim.display_zone != display_zone:
                continue
            if topic_id is not None and not _claim_touches_topic(claim, topic_id, evidence_by_id):
                continue
            items.append(claim.model_dump(mode="json"))
        return _list_response(evidence_pack, items)

    @router.get("/relations")
    def list_relations(
        from_id: str | None = None,
        to_id: str | None = None,
        relation_type: RelationType | None = None,
        strength: RelationStrength | None = None,
    ) -> dict[str, Any]:
        items = []
        for relation in evidence_pack.relations:
            if from_id is not None and relation.from_id != from_id:
                continue
            if to_id is not None and relation.to_id != to_id:
                continue
            if relation_type is not None and relation.relation_type != relation_type:
                continue
            if strength is not None and relation.strength != strength:
                continue
            items.append(relation.model_dump(mode="json"))
        return _list_response(evidence_pack, items)

    @router.get("/curated-paths")
    def list_curated_paths() -> dict[str, Any]:
        return _list_response(evidence_pack, [path.model_dump(mode="json") for path in evidence_pack.curated_paths])

    @router.get("/curated-paths/{path_id}")
    def get_curated_path(path_id: str) -> Any:
        for path in evidence_pack.curated_paths:
            if path.path_id == path_id:
                return _success_response(evidence_pack, path.model_dump(mode="json"))
        return _error_response(evidence_pack, 404, "not_found", f"Curated path not found: {path_id}")

    @router.post("/judgment-cards")
    def create_judgment_card(payload: CreateJudgmentCardRequest) -> Any:
        missing_claim_ids = [
            claim_id for claim_id in payload.selected_claim_ids if claim_id not in _claim_by_id(evidence_pack)
        ]
        if missing_claim_ids:
            return _error_response(
                evidence_pack,
                404,
                "not_found",
                f"Claim not found: {missing_claim_ids[0]}",
                details={"missing_claim_ids": missing_claim_ids},
            )

        missing_evidence_ids = [
            evidence_id
            for evidence_id in payload.selected_evidence_ids
            if evidence_id not in _evidence_by_id(evidence_pack)
        ]
        if missing_evidence_ids:
            return _error_response(
                evidence_pack,
                404,
                "not_found",
                f"Evidence unit not found: {missing_evidence_ids[0]}",
                details={"missing_evidence_ids": missing_evidence_ids},
            )

        selected_claims = [_claim_by_id(evidence_pack)[claim_id] for claim_id in payload.selected_claim_ids]
        linked_evidence_ids = _linked_evidence_ids(selected_claims, payload.selected_evidence_ids)
        card_payload = {
            "selected_claim_ids": payload.selected_claim_ids,
            "selected_evidence_ids": payload.selected_evidence_ids,
            "personal_reflection": payload.personal_reflection,
            "disposition": payload.disposition.value,
        }
        caution = None
        if payload.disposition == JudgmentDisposition.modern_analogy_with_caution:
            caution = "Historical evidence cannot directly prove a present-day policy conclusion."

        return _success_response(
            evidence_pack,
            {
                "judgment_card_id": _local_card_id(card_payload),
                "pack_id": evidence_pack.pack_id,
                "selected_claim_ids": payload.selected_claim_ids,
                "selected_evidence_ids": payload.selected_evidence_ids,
                "linked_evidence_ids": linked_evidence_ids,
                "sections": _judgment_sections(selected_claims, payload.personal_reflection),
                "disposition": payload.disposition.value,
                "caution": caution,
                "history_boundary": "Personal reflection is not historical evidence.",
                "writes_to_evidence_pack": False,
            },
        )

    return router


def _success_response(pack: EvidencePack, data: Any) -> dict[str, Any]:
    return {"data": data, "meta": _meta(pack)}


def _list_response(pack: EvidencePack, items: list[Any]) -> dict[str, Any]:
    return _success_response(pack, {"items": items, "total": len(items)})


def _error_response(
    pack: EvidencePack,
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
    retryable: bool = False,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "retryable": retryable,
            },
            "meta": _meta(pack),
        },
    )


def _meta(pack: EvidencePack) -> dict[str, Any]:
    return {
        "pack_id": pack.pack_id,
        "schema_version": pack.schema_version,
        "served_at": _dump_datetime(datetime.now(timezone.utc)),
    }


def _dump_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence_by_id(pack: EvidencePack) -> dict[str, Any]:
    return {evidence.evidence_id: evidence for evidence in pack.evidence_units}


def _claim_by_id(pack: EvidencePack) -> dict[str, Claim]:
    return {claim.claim_id: claim for claim in pack.claims}


def _evidence_ids_for_claim_type(pack: EvidencePack, claim_type: ClaimType) -> set[str]:
    evidence_ids: set[str] = set()
    for claim in pack.claims:
        if claim.claim_type == claim_type:
            evidence_ids.update(claim.evidence_ids)
            evidence_ids.update(claim.counterevidence_ids)
    return evidence_ids


def _claim_touches_topic(claim: Claim, topic_id: str, evidence_by_id: dict[str, Any]) -> bool:
    for evidence_id in [*claim.evidence_ids, *claim.counterevidence_ids]:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is not None and topic_id in evidence.topic_ids:
            return True
    return False


def _linked_evidence_ids(claims: list[Claim], selected_evidence_ids: list[str]) -> list[str]:
    linked: list[str] = []
    seen: set[str] = set()
    for evidence_id in selected_evidence_ids:
        if evidence_id not in seen:
            linked.append(evidence_id)
            seen.add(evidence_id)
    for claim in claims:
        for evidence_id in [*claim.evidence_ids, *claim.counterevidence_ids]:
            if evidence_id not in seen:
                linked.append(evidence_id)
                seen.add(evidence_id)
    return linked


def _judgment_sections(claims: list[Claim], personal_reflection: str | None) -> dict[str, Any]:
    sections: dict[str, Any] = {
        "original_facts": [],
        "curatorial_inferences": [],
        "contested_views": [],
        "personal_reflection": personal_reflection,
    }
    for claim in claims:
        row = claim.model_dump(mode="json")
        if claim.claim_type == ClaimType.original_fact:
            sections["original_facts"].append(row)
        elif claim.claim_type == ClaimType.curatorial_inference:
            sections["curatorial_inferences"].append(row)
        elif claim.claim_type == ClaimType.contested_view:
            sections["contested_views"].append(row)
    return sections


def _local_card_id(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"local_judgment:{digest}"
