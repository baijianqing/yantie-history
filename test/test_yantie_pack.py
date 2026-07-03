from __future__ import annotations

import json
import re
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

    def test_yantielun_chapter_evidence_covers_sixty_chapters_once(self) -> None:
        pack = load_pack()

        chapter_evidence = [
            evidence
            for evidence in pack.evidence_units
            if evidence.evidence_id.startswith("ev:src_yantielun:chapter_")
        ]
        self.assertEqual(len(chapter_evidence), 60)

        orders = []
        for evidence in chapter_evidence:
            match = re.match(r"ev:src_yantielun:chapter_(\d{3}):text_order:", evidence.evidence_id)
            self.assertIsNotNone(match, evidence.evidence_id)
            orders.append(int(match.group(1)))
            self.assertEqual(evidence.source_id, "src_yantielun")
            self.assertIn("·", evidence.canonical_location)
            self.assertNotIn("?", evidence.canonical_location)
            self.assertNotIn("?", evidence.paraphrase_zh)

        self.assertEqual(sorted(orders), list(range(1, 61)))


if __name__ == "__main__":
    unittest.main()
