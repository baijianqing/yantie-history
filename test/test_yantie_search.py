from __future__ import annotations

import unittest

from metaos.yantie import EvidenceSearchFilters, SearchArchiveStatus, SourceType, search_evidence


class YantieEvidenceSearchTests(unittest.TestCase):
    def test_fixed_mvp_queries_find_expected_evidence(self) -> None:
        fiscal_results = search_evidence("桑弘羊 财政", limit=5)
        self.assertEqual(fiscal_results.archive_status, SearchArchiveStatus.ok)
        self.assertIn("ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d", result_ids(fiscal_results))

        opposition_results = search_evidence("反对 盐铁 官营", limit=5)
        self.assertEqual(opposition_results.archive_status, SearchArchiveStatus.ok)
        self.assertEqual(
            opposition_results.results[0].evidence.evidence_id,
            "ev:src_yantielun:juan01_benyi:literati_abolish:0a1b2c3d",
        )
        self.assertIn("lexical_index", opposition_results.results[0].match_reasons)

        meeting_result = search_evidence("会议 结果", limit=3)
        self.assertEqual(meeting_result.archive_status, SearchArchiveStatus.ok)
        self.assertTrue(
            {
                "ev:src_hanshu_zhaodi:juan007:abolish_liquor_office:ddccbbaa",
                "ev:src_yantielun_siku:preface:partial_result:1234abcd",
            }.issubset(result_ids(meeting_result))
        )

    def test_filters_constrain_results_without_reindexing(self) -> None:
        topic_results = search_evidence(
            "",
            filters={"topic_ids": ["topic_meeting_result"]},
            limit=20,
        )
        self.assertEqual(topic_results.archive_status, SearchArchiveStatus.ok)
        self.assertTrue(topic_results.results)
        for result in topic_results.results:
            self.assertIn("topic_meeting_result", result.evidence.topic_ids)

        chronicle_results = search_evidence(
            "会议 结果",
            filters={"source_types": ["chronicle"]},
            limit=10,
        )
        self.assertEqual(chronicle_results.archive_status, SearchArchiveStatus.ok)
        for result in chronicle_results.results:
            self.assertEqual(result.source.source_type, SourceType.chronicle)

        actor_results = search_evidence(
            "财政",
            filters=EvidenceSearchFilters(actor_ids=["actor_sang_hongyang"]),
            limit=10,
        )
        self.assertIn("ev:src_yantielun:juan01_benyi:border_finance:1a2b3c4d", result_ids(actor_results))

    def test_no_match_returns_archive_insufficient_without_synthetic_answer(self) -> None:
        results = search_evidence("唐朝 科举", limit=5)

        self.assertEqual(results.archive_status, SearchArchiveStatus.archive_insufficient)
        self.assertEqual(results.total, 0)
        self.assertEqual(results.results, [])
        self.assertEqual(results.message, "No verified evidence matches this query.")

    def test_result_order_is_stable_and_limit_is_enforced(self) -> None:
        first = search_evidence("桑弘羊 财政", limit=4)
        second = search_evidence("桑弘羊 财政", limit=4)

        self.assertEqual(result_ids(first), result_ids(second))
        self.assertEqual(len(first.results), 4)
        self.assertTrue(all(result.score > 0 for result in first.results))


def result_ids(results: object) -> list[str]:
    return [result.evidence.evidence_id for result in results.results]


if __name__ == "__main__":
    unittest.main()
