from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from metaos.ministries import (
    MAX_ITEMS_PER_MINISTRY,
    MAX_ITEMS_TOTAL,
    NO_REPORT,
    Ministry,
    MinistryReport,
    RecommendationCandidate,
    RecommendationItem,
    generate_ministry_reports,
)
from metaos.sovereignty import AttentionBudget, Intent


class MinistryRecommendationTests(unittest.TestCase):
    def test_generate_ministry_reports_limits_per_ministry_and_total(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship Alpha")
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=120, research_minutes=60)
        candidates = [
            self.candidate(Ministry.technology, f"tech {index}", score=1 - index * 0.01)
            for index in range(5)
        ] + [
            self.candidate(Ministry.cognition, f"cog {index}", score=0.9 - index * 0.01)
            for index in range(4)
        ] + [
            self.candidate(Ministry.business, f"biz {index}", score=0.8 - index * 0.01)
            for index in range(4)
        ]

        reports = generate_ministry_reports(
            date(2026, 6, 15),
            intent=intent,
            attention_budget=budget,
            candidates=candidates,
        )

        counts = {report.ministry: len(report.items) for report in reports}
        self.assertLessEqual(max(counts.values()), MAX_ITEMS_PER_MINISTRY)
        self.assertLessEqual(sum(counts.values()), MAX_ITEMS_TOTAL)
        self.assertEqual(counts[Ministry.technology], MAX_ITEMS_PER_MINISTRY)
        self.assertEqual(sum(counts.values()), MAX_ITEMS_TOTAL)

    def test_generate_ministry_reports_filters_intent_and_budget(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship Alpha")
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=120, research_minutes=10)
        candidates = [
            self.candidate(Ministry.technology, "too expensive", cost=20, score=1.0),
            self.candidate(Ministry.business, "wrong intent", intent_id="other", cost=5, score=0.99),
            self.candidate(Ministry.cognition, "fits", intent_id="intent_alpha", cost=8, score=0.8),
        ]

        reports = generate_ministry_reports(
            date(2026, 6, 15),
            intent=intent,
            attention_budget=budget,
            candidates=candidates,
        )

        selected_titles = [item.title for report in reports for item in report.items]
        self.assertEqual(selected_titles, ["fits"])
        empty_reports = [report for report in reports if not report.items]
        self.assertEqual({report.empty_reason for report in empty_reports}, {NO_REPORT})

    def test_generate_ministry_reports_returns_no_report_when_empty(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship Alpha")
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=30, research_minutes=10)

        reports = generate_ministry_reports(
            date(2026, 6, 15),
            intent=intent,
            attention_budget=budget,
            candidates=[],
        )

        self.assertEqual(len(reports), 3)
        self.assertTrue(all(report.empty_reason == NO_REPORT for report in reports))
        self.assertTrue(all(report.items == [] for report in reports))

    def test_ministry_report_validates_limits_and_item_ministry(self) -> None:
        with self.assertRaises(ValidationError):
            MinistryReport(
                date=date(2026, 6, 15),
                ministry=Ministry.technology,
                items=[
                    self.item(Ministry.technology, f"item {index}")
                    for index in range(MAX_ITEMS_PER_MINISTRY + 1)
                ],
            )

        with self.assertRaises(ValidationError):
            MinistryReport(
                date=date(2026, 6, 15),
                ministry=Ministry.technology,
                items=[self.item(Ministry.business, "wrong ministry")],
            )

    def candidate(
        self,
        ministry: Ministry,
        title: str,
        *,
        cost: int = 5,
        score: float = 0.5,
        intent_id: str | None = None,
    ) -> RecommendationCandidate:
        return RecommendationCandidate(
            ministry=ministry,
            title=title,
            reason="Useful for current intent",
            intent_alignment="Aligned with Ship Alpha",
            reading_cost_minutes=cost,
            cost_of_ignoring="Miss a relevant signal",
            suggested_action="Review and decide",
            score=score,
            intent_id=intent_id,
        )

    def item(self, ministry: Ministry, title: str) -> RecommendationItem:
        return RecommendationItem(
            ministry=ministry,
            title=title,
            reason="Useful",
            intent_alignment="Aligned",
            reading_cost_minutes=1,
            cost_of_ignoring="Miss signal",
            suggested_action="Review",
        )


if __name__ == "__main__":
    unittest.main()
