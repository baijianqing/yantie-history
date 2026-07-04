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
        self.assertGreaterEqual(len(lens_evidence), 6)

        for evidence in lens_evidence:
            source = sources_by_id[evidence.source_id]
            self.assertEqual(evidence.review_status, ReviewStatus.verified)
            self.assertNotEqual(source.source_type, SourceType.external_echo)
            self.assertTrue(evidence.excerpt_original)
            self.assertTrue(evidence.paraphrase_zh)
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


if __name__ == "__main__":
    unittest.main()
