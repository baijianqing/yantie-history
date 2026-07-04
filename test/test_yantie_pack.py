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
