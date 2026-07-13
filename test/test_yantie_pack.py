from __future__ import annotations

import json
import unittest
from pathlib import Path

from metaos.yantie import ClaimType, EvidencePack, ReviewStatus, SourceType


PACK_PATH = Path(__file__).resolve().parents[1] / "metaos" / "yantie" / "data" / "evidence_pack.json"


def load_pack() -> EvidencePack:
    payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    return EvidencePack.model_validate(payload)


class YantieEvidencePackDataTests(unittest.TestCase):
    def test_pack_meets_mvp_coverage_floor(self) -> None:
        pack = load_pack()

        self.assertGreaterEqual(len(pack.sources), 6)
        self.assertGreaterEqual(len(pack.actors), 6)
        self.assertGreaterEqual(len(pack.events), 8)
        self.assertGreaterEqual(len(pack.evidence_units), 20)
        self.assertGreaterEqual(len(pack.claims), 12)
        self.assertGreaterEqual(len(pack.relations), 20)
        self.assertGreaterEqual(len(pack.map_layers), 3)

        source_types = {source.source_type for source in pack.sources}
        self.assertTrue(
            {
                SourceType.primary_text,
                SourceType.chronicle,
                SourceType.institutional_history,
                SourceType.biography,
                SourceType.later_commentary,
            }.issubset(source_types)
        )

    def test_claims_keep_reflection_separate_from_historical_evidence(self) -> None:
        pack = load_pack()

        non_reflection_claims = [
            claim for claim in pack.claims if claim.claim_type != ClaimType.personal_reflection_prompt
        ]
        self.assertTrue(non_reflection_claims)
        for claim in non_reflection_claims:
            self.assertTrue(claim.evidence_ids, claim.claim_id)

        reflection_claims = [
            claim for claim in pack.claims if claim.claim_type == ClaimType.personal_reflection_prompt
        ]
        self.assertEqual(len(reflection_claims), 1)
        self.assertFalse(reflection_claims[0].evidence_ids)

        display_zones = {claim.display_zone.value for claim in pack.claims}
        self.assertIn("evidence_room", display_zones)

    def test_claim_citations_use_verified_non_external_evidence(self) -> None:
        pack = load_pack()
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}
        sources_by_id = {source.source_id: source for source in pack.sources}

        for claim in pack.claims:
            for evidence_id in [*claim.evidence_ids, *claim.counterevidence_ids]:
                evidence = evidence_by_id[evidence_id]
                source = sources_by_id[evidence.source_id]
                self.assertNotEqual(source.source_type, SourceType.external_echo, claim.claim_id)
                self.assertEqual(evidence.review_status, ReviewStatus.verified, claim.claim_id)

    def test_zizhi_tongjian_chronicle_evidence_covers_meeting_outline(self) -> None:
        pack = load_pack()
        sources_by_id = {source.source_id: source for source in pack.sources}
        manifest_by_id = {entry.source_id: entry for entry in pack.source_manifest}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}

        source = sources_by_id["src_zizhi_tongjian_023"]
        self.assertEqual(source.source_type, SourceType.chronicle)
        self.assertEqual(source.delivery_policy.value, "excerpt_allowed")
        self.assertTrue(source.human_verified)

        chronicle_evidence = [
            evidence for evidence in pack.evidence_units if evidence.source_id == "src_zizhi_tongjian_023"
        ]
        self.assertEqual(len(chronicle_evidence), 4)
        self.assertEqual(manifest_by_id["src_zizhi_tongjian_023"].excerpt_count, len(chronicle_evidence))

        expected_ids = {
            "ev:src_zizhi_tongjian_023:shiyuan06:meeting_question:aa230001",
            "ev:src_zizhi_tongjian_023:shiyuan06:literati_petition:aa230002",
            "ev:src_zizhi_tongjian_023:shiyuan06:sang_reply:aa230003",
            "ev:src_zizhi_tongjian_023:shiyuan06:liquor_office_abolished:aa230004",
        }
        self.assertEqual({evidence.evidence_id for evidence in chronicle_evidence}, expected_ids)

        for evidence in chronicle_evidence:
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertIn("later_chronicle", evidence.value_tags)
            self.assertIn("Public-domain later chronicle", evidence.copyright_note)
            self.assertTrue(evidence.adjacent_context_note)
            self.assertTrue(
                "通鉴" in evidence.adjacent_context_note or "互证" in evidence.adjacent_context_note
            )

        cited_ids = {
            evidence_id
            for claim in pack.claims
            for evidence_id in claim.evidence_ids
            if evidence_id in expected_ids
        }
        self.assertEqual(cited_ids, expected_ids)
        for evidence_id in expected_ids:
            self.assertEqual(evidence_by_id[evidence_id].certainty.value, "direct_text")

    def test_hanshu_shiji_institutional_background_covers_a2_fiscal_system(self) -> None:
        pack = load_pack()
        sources_by_id = {source.source_id: source for source in pack.sources}
        manifest_by_id = {entry.source_id: entry for entry in pack.source_manifest}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}

        self.assertEqual(sources_by_id["src_hanshu_shihuo"].source_type, SourceType.institutional_history)
        self.assertEqual(sources_by_id["src_shiji_pingzhun"].source_type, SourceType.institutional_history)

        hanshu_evidence = [
            evidence for evidence in pack.evidence_units if evidence.source_id == "src_hanshu_shihuo"
        ]
        shiji_evidence = [
            evidence for evidence in pack.evidence_units if evidence.source_id == "src_shiji_pingzhun"
        ]
        self.assertEqual(len(hanshu_evidence), 9)
        self.assertEqual(len(shiji_evidence), 11)
        self.assertEqual(manifest_by_id["src_hanshu_shihuo"].excerpt_count, len(hanshu_evidence))
        self.assertEqual(manifest_by_id["src_shiji_pingzhun"].excerpt_count, len(shiji_evidence))

        expected_ids = {
            "ev:src_hanshu_shihuo:juan024:private_salt_iron_wealth:a2b20001",
            "ev:src_hanshu_shihuo:juan024:suanmin_commerce_tax:a2b20002",
            "ev:src_hanshu_shihuo:juan024:gaomin_breaks_merchants:a2b20003",
            "ev:src_hanshu_shihuo:juan024:bad_iron_price_complaint:a2b20004",
            "ev:src_hanshu_shihuo:juan024:equal_transport_supports_war:a2b20005",
            "ev:src_hanshu_shihuo:juan024:pingzhun_mechanism:a2b20006",
            "ev:src_shiji_pingzhun:juan030:private_salt_iron_wealth:a2b20007",
            "ev:src_shiji_pingzhun:juan030:salt_iron_state_assets:a2b20008",
            "ev:src_shiji_pingzhun:juan030:suanmin_assessment:a2b20009",
            "ev:src_shiji_pingzhun:juan030:gaomin_confiscation:a2b2000a",
            "ev:src_shiji_pingzhun:juan030:bad_iron_complaint:a2b2000b",
            "ev:src_shiji_pingzhun:juan030:pingzhun_market_mechanism:a2b2000c",
        }

        for evidence_id in expected_ids:
            evidence = evidence_by_id[evidence_id]
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertEqual(evidence.certainty.value, "direct_text")
            self.assertIn("institutional_background", evidence.value_tags)
            self.assertIn(evidence.source_id, {"src_hanshu_shihuo", "src_shiji_pingzhun"})

        required_tags = {
            "private_salt_iron_wealth",
            "suanmin",
            "gaomin",
            "monopoly_abuse",
            "equal_transport",
            "price_leveling",
            "market_intervention",
            "institutional_background",
        }
        covered_tags = {
            value_tag
            for evidence_id in expected_ids
            for value_tag in evidence_by_id[evidence_id].value_tags
        }
        self.assertTrue(required_tags.issubset(covered_tags))

    def test_siku_textual_history_marks_yantie_as_compiled_later_framed_text(self) -> None:
        pack = load_pack()
        sources_by_id = {source.source_id: source for source in pack.sources}
        manifest_by_id = {entry.source_id: entry for entry in pack.source_manifest}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}
        claims_by_id = {claim.claim_id: claim for claim in pack.claims}

        source = sources_by_id["src_yantielun_siku"]
        self.assertEqual(source.source_type, SourceType.later_commentary)
        self.assertEqual(source.delivery_policy.value, "excerpt_allowed")
        self.assertTrue(source.human_verified)

        siku_evidence = [
            evidence for evidence in pack.evidence_units if evidence.source_id == "src_yantielun_siku"
        ]
        self.assertEqual(len(siku_evidence), 8)
        self.assertEqual(manifest_by_id["src_yantielun_siku"].excerpt_count, len(siku_evidence))

        expected_ids = {
            "ev:src_yantielun_siku:preface:huan_kuan_author:a2c30001",
            "ev:src_yantielun_siku:preface:text_compilation:a2c30002",
            "ev:src_yantielun_siku:preface:connected_chapters:a2c30003",
            "ev:src_yantielun_siku:preface:named_literati:a2c30004",
            "ev:src_yantielun_siku:preface:confucian_catalog:a2c30005",
            "ev:src_yantielun_siku:preface:qianqingtang_catalog:a2c30006",
        }

        for evidence_id in expected_ids:
            evidence = evidence_by_id[evidence_id]
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertEqual(evidence.certainty.value, "direct_text")
            self.assertIn("textual_history", evidence.value_tags)
            self.assertIn("later_reception", evidence.value_tags)
            self.assertNotEqual(evidence.evidence_kind.value, "event_record")

        required_tags = {
            "huan_kuan",
            "compilation",
            "not_transcript",
            "chapter_structure",
            "named_literati",
            "confucian_catalog",
            "catalog_history",
        }
        covered_tags = {
            value_tag
            for evidence_id in expected_ids
            for value_tag in evidence_by_id[evidence_id].value_tags
        }
        self.assertTrue(required_tags.issubset(covered_tags))

        framing_claim = claims_by_id["claim_text_has_later_framing"]
        self.assertTrue(
            {
                "ev:src_yantielun_siku:preface:text_compilation:a2c30002",
                "ev:src_yantielun_siku:preface:connected_chapters:a2c30003",
                "ev:src_yantielun_siku:preface:confucian_catalog:a2c30005",
                "ev:src_yantielun_siku:preface:qianqingtang_catalog:a2c30006",
            }.issubset(set(framing_claim.evidence_ids))
        )

    def test_lexical_index_supports_fixed_mvp_queries(self) -> None:
        pack = load_pack()

        for token in ["盐铁", "桑弘羊", "霍光", "均输", "榷酤"]:
            self.assertIn(token, pack.lexical_index.entries)
            self.assertTrue(pack.lexical_index.entries[token])

    def test_curated_paths_and_map_layers_are_evidence_backed(self) -> None:
        pack = load_pack()

        for path in pack.curated_paths:
            self.assertTrue(path.steps, path.path_id)
            for step in path.steps:
                self.assertTrue(step.claim_ids, path.path_id)
                self.assertTrue(step.evidence_ids, path.path_id)

        for layer in pack.map_layers:
            self.assertTrue(layer.evidence_ids, layer.layer_id)
            self.assertTrue(layer.features, layer.layer_id)
            for feature in layer.features:
                self.assertTrue(feature.evidence_ids, feature.feature_id)

    def test_philosophy_lens_evidence_is_distinct_from_meeting_fact_evidence(self) -> None:
        pack = load_pack()
        sources_by_id = {source.source_id: source for source in pack.sources}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}

        lens_evidence = [
            evidence for evidence in pack.evidence_units if "philosophy_lens" in evidence.value_tags
        ]
        self.assertGreaterEqual(len(lens_evidence), 24)

        for evidence in lens_evidence:
            source = sources_by_id[evidence.source_id]
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertNotEqual(source.source_type, SourceType.external_echo)
            self.assertTrue(evidence.excerpt_original)
            self.assertTrue(evidence.paraphrase_zh)
            self.assertTrue(evidence.canonical_location)
            self.assertIn("lens", evidence.copyright_note.lower())
            self.assertTrue(evidence.adjacent_context_note)

        original_fact_claims = [
            claim for claim in pack.claims if claim.claim_type == ClaimType.original_fact
        ]
        self.assertTrue(original_fact_claims)
        for claim in original_fact_claims:
            claim_evidence = [evidence_by_id[evidence_id] for evidence_id in claim.evidence_ids]
            self.assertTrue(
                any("philosophy_lens" not in evidence.value_tags for evidence in claim_evidence),
                claim.claim_id,
            )

    def test_huangdi_sijing_huang_lao_lenses_are_bounded(self) -> None:
        pack = load_pack()
        sources_by_id = {source.source_id: source for source in pack.sources}
        manifest_by_id = {entry.source_id: entry for entry in pack.source_manifest}
        evidence_by_id = {evidence.evidence_id: evidence for evidence in pack.evidence_units}

        source = sources_by_id["src_huangdi_sijing"]
        self.assertEqual(source.source_type, SourceType.primary_text)
        self.assertEqual(source.delivery_policy.value, "excerpt_allowed")
        self.assertTrue(source.human_verified)

        huang_lao_evidence = [
            evidence for evidence in pack.evidence_units if evidence.source_id == "src_huangdi_sijing"
        ]
        self.assertEqual(len(huang_lao_evidence), 6)
        self.assertEqual(manifest_by_id["src_huangdi_sijing"].excerpt_count, len(huang_lao_evidence))

        expected_ids = {
            "ev:src_huangdi_sijing:jingfa:dao_generates_law:a2d50001",
            "ev:src_huangdi_sijing:jingfa:law_standard_rectification:a2d50002",
            "ev:src_huangdi_sijing:shiliujing:reduce_harsh_affairs:a2d50003",
            "ev:src_huangdi_sijing:shiliujing:do_not_seize_people_time:a2d50004",
            "ev:src_huangdi_sijing:cheng:name_reality_alignment:a2d50005",
            "ev:src_huangdi_sijing:shiliujing:utmost_stillness_sage:a2d50006",
        }
        self.assertEqual({evidence.evidence_id for evidence in huang_lao_evidence}, expected_ids)

        for evidence in huang_lao_evidence:
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertEqual(evidence.certainty.value, "direct_text")
            self.assertEqual(evidence.evidence_kind.value, "speech_argument")
            self.assertIn("philosophy_lens", evidence.value_tags)
            self.assertIn("huang_lao", evidence.value_tags)
            self.assertLessEqual(len(evidence.excerpt_original or ""), 12)
            self.assertIn("Huang-Lao philosophy lens", evidence.copyright_note)
            self.assertIn("not evidence", evidence.adjacent_context_note or "")
            self.assertIn("Yantie meeting", evidence.adjacent_context_note or "")

        original_fact_claims = [
            claim for claim in pack.claims if claim.claim_type == ClaimType.original_fact
        ]
        for claim in original_fact_claims:
            self.assertFalse(
                any(evidence_id in expected_ids for evidence_id in claim.evidence_ids),
                claim.claim_id,
            )
            self.assertTrue(
                any("philosophy_lens" not in evidence_by_id[evidence_id].value_tags for evidence_id in claim.evidence_ids),
                claim.claim_id,
            )

    def test_yantielun_chapter_evidence_covers_all_sixty_chapters(self) -> None:
        pack = load_pack()

        expected_locations = [
            "卷一·本议第一",
            "卷一·力耕第二",
            "卷一·通有第三",
            "卷一·错币第四",
            "卷一·禁耕第五",
            "卷一·复古第六",
            "卷二·非鞅第七",
            "卷二·晁错第八",
            "卷二·刺权第九",
            "卷二·刺复第十",
            "卷二·论儒第十一",
            "卷二·忧边第十二",
            "卷三·园池第十三",
            "卷三·轻重第十四",
            "卷三·未通第十五",
            "卷四·地广第十六",
            "卷四·贫富第十七",
            "卷四·毁学第十八",
            "卷四·褒贤第十九",
            "卷五·相刺第二十",
            "卷五·殊路第二十一",
            "卷五·讼贤第二十二",
            "卷五·遵道第二十三",
            "卷五·论诽第二十四",
            "卷五·孝养第二十五",
            "卷五·刺议第二十六",
            "卷五·利议第二十七",
            "卷五·国疾第二十八",
            "卷六·散不足第二十九",
            "卷六·救匮第三十",
            "卷六·箴石第三十一",
            "卷六·除狭第三十二",
            "卷六·疾贪第三十三",
            "卷六·后刑第三十四",
            "卷六·授时第三十五",
            "卷六·水旱第三十六",
            "卷七·崇礼第三十七",
            "卷七·备胡第三十八",
            "卷七·执务第三十九",
            "卷七·能言第四十",
            "卷七·取下第四十一",
            "卷七·击之第四十二",
            "卷八·结和第四十三",
            "卷八·诛秦第四十四",
            "卷八·伐功第四十五",
            "卷八·西域第四十六",
            "卷八·世务第四十七",
            "卷八·和亲第四十八",
            "卷九·繇役第四十九",
            "卷九·险固第五十",
            "卷九·论勇第五十一",
            "卷九·论功第五十二",
            "卷九·论邹第五十三",
            "卷九·论菑第五十四",
            "卷十·刑德第五十五",
            "卷十·申韩第五十六",
            "卷十·周秦第五十七",
            "卷十·诏圣第五十八",
            "卷十·大论第五十九",
            "卷十·杂论第六十",
        ]
        yantielun_locations = {
            evidence.canonical_location
            for evidence in pack.evidence_units
            if evidence.source_id == "src_yantielun"
        }

        self.assertEqual(len(expected_locations), 60)
        self.assertTrue(set(expected_locations).issubset(yantielun_locations))
        for number, location in enumerate(expected_locations, start=1):
            matching = [
                evidence
                for evidence in pack.evidence_units
                if evidence.source_id == "src_yantielun" and evidence.canonical_location == location
            ]
            self.assertTrue(matching, location)
            self.assertTrue(
                any(f"yantie_chapter_{number:02d}" in evidence.value_tags for evidence in matching),
                location,
            )


if __name__ == "__main__":
    unittest.main()
