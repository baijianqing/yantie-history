from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timezone

from pydantic import ValidationError

from metaos.yantie import (
    Actor,
    AuthorityLevel,
    Claim,
    ClaimType,
    DeliveryPolicy,
    EvidenceKind,
    EvidencePack,
    EvidenceRequirementSpec,
    EvidenceUnit,
    Event,
    LicenseStatus,
    Relation,
    RelationStrength,
    RelationType,
    Source,
    SourceManifestEntry,
    SourceType,
    ThemeSpec,
    Topic,
)


UTC_NOW = datetime(2026, 7, 3, 0, 0, 0, tzinfo=timezone.utc)
EVIDENCE_ID = "ev:src_yantielun:juan01_benyi:state_monopoly:deadbeef"
CONTEXT_ID = "ev:src_tongjian_023:shiyuan06:meeting_result:cafebabe"


class YantieEvidencePackContractTests(unittest.TestCase):
    def test_valid_pack_preserves_evidence_graph_contract(self) -> None:
        pack = EvidencePack.model_validate(valid_pack_payload())

        self.assertEqual(pack.pack_id, "yantie_meeting_v1")
        self.assertEqual(pack.sources[0].delivery_policy, DeliveryPolicy.excerpt_allowed)
        self.assertEqual(pack.claims[0].claim_type, ClaimType.original_fact)
        self.assertEqual(pack.relations[0].strength, RelationStrength.explicit_source)
        self.assertIn(EVIDENCE_ID, pack.lexical_index.entries["盐铁"])

    def test_closed_models_reject_extra_fields_and_non_utc_time(self) -> None:
        payload = valid_pack_payload()
        payload["unexpected"] = "forbidden"
        with self.assertRaises(ValidationError):
            EvidencePack.model_validate(payload)

        payload = valid_pack_payload()
        payload["generated_at"] = datetime(2026, 7, 3, 0, 0, 0)
        with self.assertRaises(ValidationError):
            EvidencePack.model_validate(payload)

    def test_claims_require_verified_direct_evidence_for_original_facts(self) -> None:
        payload = valid_pack_payload()
        payload["evidence_units"][0]["certainty"] = "high_confidence_context"
        with self.assertRaisesRegex(ValidationError, "direct text evidence"):
            EvidencePack.model_validate(payload)

        payload = valid_pack_payload()
        payload["evidence_units"][0]["review_status"] = "candidate"
        with self.assertRaisesRegex(ValidationError, "verified evidence"):
            EvidencePack.model_validate(payload)

    def test_curatorial_inference_requires_reasoning_note(self) -> None:
        with self.assertRaises(ValidationError):
            Claim(
                claim_id="claim_inference",
                claim_type="curatorial_inference",
                statement="The meeting also reveals power constraints.",
                stance="explains_context",
                evidence_ids=[EVIDENCE_ID],
                reasoning_note=None,
                display_zone="power_network",
            )

    def test_external_echo_cannot_be_historical_evidence(self) -> None:
        payload = valid_pack_payload()
        payload["sources"].append(
            {
                "source_id": "src_zhihu_echo",
                "title": "Zhihu contemporary echo",
                "source_type": "external_echo",
                "authority_level": "echo",
                "license_status": "link_only",
                "canonical_url": "https://developer.zhihu.com/",
                "citation_style": "Zhihu external echo",
                "delivery_policy": "link_only",
                "human_verified": True,
            }
        )
        payload["evidence_units"].append(
            {
                "evidence_id": "ev:src_zhihu_echo:search:modern_echo:0123abcd",
                "source_id": "src_zhihu_echo",
                "canonical_location": "search",
                "excerpt_original": None,
                "paraphrase_zh": "Modern discussion only.",
                "evidence_kind": "later_evaluation",
                "speaker_actor_id": None,
                "topic_ids": ["topic_salt_iron"],
                "value_tags": ["external_echo"],
                "certainty": "contested",
                "copyright_note": "External search result.",
                "review_status": "verified",
            }
        )
        payload["claims"][0]["evidence_ids"] = ["ev:src_zhihu_echo:search:modern_echo:0123abcd"]

        with self.assertRaisesRegex(ValidationError, "external echo"):
            EvidencePack.model_validate(payload)

    def test_delivery_policy_blocks_original_excerpt_for_link_only_sources(self) -> None:
        with self.assertRaises(ValidationError):
            Source(
                source_id="src_modern",
                title="Modern study",
                source_type="modern_research",
                authority_level="comparison",
                license_status="link_only",
                citation_style="Modern study",
                delivery_policy="excerpt_allowed",
                human_verified=False,
            )

        payload = valid_pack_payload()
        payload["sources"][0]["license_status"] = "link_only"
        payload["sources"][0]["delivery_policy"] = "link_only"
        with self.assertRaisesRegex(ValidationError, "non-excerpt"):
            EvidencePack.model_validate(payload)

    def test_relations_and_links_must_be_explainable_and_resolvable(self) -> None:
        with self.assertRaises(ValidationError):
            Relation(
                relation_id="rel_inferred",
                from_id="actor_sang_hongyang",
                to_id="topic_salt_iron",
                relation_type=RelationType.actor_interest,
                evidence_ids=[EVIDENCE_ID],
                strength=RelationStrength.contextual_inference,
                note=None,
            )

        payload = valid_pack_payload()
        payload["actors"][0]["evidence_ids"] = ["ev:src_missing:bad:bad:00000000"]
        with self.assertRaisesRegex(ValidationError, "unknown id"):
            EvidencePack.model_validate(payload)


def valid_pack_payload() -> dict:
    return {
        "schema_version": "yantie_evidence_pack_v1",
        "pack_id": "yantie_meeting_v1",
        "generated_at": UTC_NOW,
        "source_manifest": [
            SourceManifestEntry(
                source_id="src_yantielun",
                title="Yantie lun",
                license_status=LicenseStatus.public_domain_text,
                delivery_policy=DeliveryPolicy.excerpt_allowed,
                excerpt_count=1,
                human_verified=True,
                note="Public domain source excerpt.",
            ).model_dump(mode="json"),
            SourceManifestEntry(
                source_id="src_tongjian_023",
                title="Zizhi Tongjian juan 023",
                license_status=LicenseStatus.public_domain_text,
                delivery_policy=DeliveryPolicy.excerpt_allowed,
                excerpt_count=1,
                human_verified=True,
                note="Chronicle context source.",
            ).model_dump(mode="json"),
        ],
        "theme_spec": ThemeSpec(
            theme_id="theme_yantie_meeting",
            title="Yantie meeting reconstruction",
            historical_period="Western Han, Yuanfeng era",
            core_question="Should the salt and iron monopoly be abolished?",
            experience_mode="meeting_reconstruction",
            evidence_requirements=[
                EvidenceRequirementSpec(
                    requirement_id="req_primary_text",
                    requirement_type="primary_fact",
                    description="Use direct text for factual claims.",
                    minimum_count=1,
                    required_source_types=[SourceType.primary_text],
                )
            ],
            value_axes=["fiscal_capacity_vs_livelihood"],
            output_contract={"sections": ["facts", "inferences", "disputes", "reflection"]},
        ).model_dump(mode="json"),
        "sources": [
            Source(
                source_id="src_yantielun",
                title="Yantie lun",
                source_type=SourceType.primary_text,
                authority_level=AuthorityLevel.core,
                license_status=LicenseStatus.public_domain_text,
                canonical_url="https://zh.wikisource.org/wiki/%E9%B9%BD%E9%90%B5%E8%AB%96",
                citation_style="Yantie lun, Benyi",
                delivery_policy=DeliveryPolicy.excerpt_allowed,
                human_verified=True,
            ).model_dump(mode="json"),
            Source(
                source_id="src_tongjian_023",
                title="Zizhi Tongjian juan 023",
                source_type=SourceType.chronicle,
                authority_level=AuthorityLevel.background,
                license_status=LicenseStatus.public_domain_text,
                canonical_url="https://zh.wikisource.org/wiki/%E8%B3%87%E6%B2%BB%E9%80%9A%E9%91%91/%E5%8D%B7023",
                citation_style="Zizhi Tongjian, juan 023",
                delivery_policy=DeliveryPolicy.excerpt_allowed,
                human_verified=True,
            ).model_dump(mode="json"),
        ],
        "actors": [
            Actor(
                actor_id="actor_sang_hongyang",
                name="Sang Hongyang",
                role_title="Imperial secretary and fiscal official",
                meeting_position="state_policy_defender",
                stance_summary="Defends state fiscal capacity.",
                interest_constraints=["frontier finance", "state capacity"],
                evidence_ids=[EVIDENCE_ID],
            ).model_dump(mode="json")
        ],
        "events": [
            Event(
                event_id="event_shiyuan_meeting",
                title="Yantie meeting",
                date_label="Shiyuan sixth year",
                event_type="meeting_session",
                summary="Court debate over salt, iron, liquor, and equal transport policies.",
                location_id="chang_an",
                actor_ids=["actor_sang_hongyang"],
                topic_ids=["topic_salt_iron"],
                evidence_ids=[CONTEXT_ID],
            ).model_dump(mode="json")
        ],
        "topics": [
            Topic(
                topic_id="topic_salt_iron",
                title="Salt and iron monopoly",
                summary="The central policy dispute.",
                value_axes=["fiscal_capacity_vs_livelihood"],
                evidence_ids=[EVIDENCE_ID],
            ).model_dump(mode="json")
        ],
        "evidence_units": [
            EvidenceUnit(
                evidence_id=EVIDENCE_ID,
                source_id="src_yantielun",
                canonical_location="juan01_benyi",
                excerpt_original="Short public domain excerpt.",
                paraphrase_zh="State monopoly is defended as fiscal policy.",
                evidence_kind=EvidenceKind.speech_argument,
                speaker_actor_id="actor_sang_hongyang",
                topic_ids=["topic_salt_iron"],
                value_tags=["state_capacity"],
                certainty="direct_text",
                copyright_note="Short excerpt from public domain text.",
                review_status="verified",
            ).model_dump(mode="json"),
            EvidenceUnit(
                evidence_id=CONTEXT_ID,
                source_id="src_tongjian_023",
                canonical_location="shiyuan06",
                excerpt_original="Short public domain chronicle excerpt.",
                paraphrase_zh="The meeting led to a partial policy result.",
                evidence_kind=EvidenceKind.event_record,
                speaker_actor_id=None,
                topic_ids=["topic_salt_iron"],
                value_tags=["policy_result"],
                certainty="direct_text",
                copyright_note="Short excerpt from public domain text.",
                review_status="verified",
            ).model_dump(mode="json"),
        ],
        "claims": [
            {
                "claim_id": "claim_state_defense",
                "claim_type": "original_fact",
                "statement": "Sang Hongyang defended the fiscal value of state policy.",
                "stance": "supports_state_monopoly",
                "evidence_ids": [EVIDENCE_ID],
                "counterevidence_ids": [],
                "external_reference_ids": [],
                "reasoning_note": None,
                "display_zone": "meeting",
            },
            {
                "claim_id": "claim_power_context",
                "claim_type": "curatorial_inference",
                "statement": "The debate should be read within court power constraints.",
                "stance": "explains_context",
                "evidence_ids": [EVIDENCE_ID, CONTEXT_ID],
                "counterevidence_ids": [],
                "external_reference_ids": [],
                "reasoning_note": "The claim links policy defense with chronicle context.",
                "display_zone": "power_network",
            },
        ],
        "relations": [
            {
                "relation_id": "rel_sang_topic",
                "from_id": "actor_sang_hongyang",
                "to_id": "topic_salt_iron",
                "relation_type": "supports",
                "evidence_ids": [EVIDENCE_ID],
                "strength": "explicit_source",
                "note": None,
            }
        ],
        "map_layers": [
            {
                "layer_id": "layer_capital",
                "title": "Capital and meeting site",
                "layer_type": "capital",
                "time_scope": "Western Han",
                "features": [
                    {
                        "feature_id": "feature_chang_an",
                        "title": "Chang'an",
                        "summary": "Court setting for the reconstruction.",
                        "coordinates": [50.0, 50.0],
                        "evidence_ids": [CONTEXT_ID],
                    }
                ],
                "evidence_ids": [CONTEXT_ID],
                "display_style": {"color": "red"},
            }
        ],
        "curated_paths": [
            {
                "path_id": "path_opening_context",
                "title": "Opening context",
                "summary": "A short route through the meeting context.",
                "steps": [
                    {
                        "order": 1,
                        "title": "Read the policy defense",
                        "claim_ids": ["claim_state_defense"],
                        "evidence_ids": [EVIDENCE_ID],
                    }
                ],
            }
        ],
        "external_references": [],
        "lexical_index": {
            "tokenization": "char_bigram_zh_v1",
            "entries": {"盐铁": [EVIDENCE_ID], "桑弘羊": [EVIDENCE_ID]},
        },
    }


def copied_valid_pack_payload() -> dict:
    return deepcopy(valid_pack_payload())


if __name__ == "__main__":
    unittest.main()
