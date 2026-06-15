from __future__ import annotations

import unittest
from datetime import date

from metaos.chancellor import generate_chancellor_briefing
from metaos.ledger import Action, ActionSourceType, DailyReview
from metaos.ministries import Ministry, MinistryReport, NO_REPORT, RecommendationItem
from metaos.research import AnswerStatement, ResearchAnswer, SourceStatus
from metaos.sovereignty import AttentionBudget, CurrentRole, Intent


class ChancellorBriefingTests(unittest.TestCase):
    def test_generate_chancellor_briefing_outputs_focus_deferred_ignore_and_traps(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        role = CurrentRole(
            id="role_builder",
            name="Builder",
            forbidden_focus=["generic news feed"],
        )
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=180)
        review = DailyReview(
            id="review_1",
            date=date(2026, 6, 15),
            actions_missed=["Write weekly report"],
        )
        answer_with_action = ResearchAnswer(
            id="answer_1",
            task_id="task_1",
            model_inferences=[
                AnswerStatement(text="Likely useful", source_status=SourceStatus.uncited)
            ],
            actions=[
                Action(
                    title="Run citation audit",
                    source_type=ActionSourceType.research_answer,
                    source_id="answer_1",
                    intent_id=intent.id,
                )
            ],
        )
        answer_no_action = ResearchAnswer(
            id="answer_2",
            task_id="task_2",
            no_action_reason="Evidence is incomplete.",
        )
        reports = [
            MinistryReport(
                date=date(2026, 6, 15),
                ministry=Ministry.technology,
                items=[
                    RecommendationItem(
                        ministry=Ministry.technology,
                        title="Index health",
                        reason="Maintain retrieval quality",
                        intent_alignment="Supports Alpha",
                        reading_cost_minutes=5,
                        cost_of_ignoring="Miss regression",
                        suggested_action="Check index health",
                    )
                ],
            ),
            MinistryReport(date=date(2026, 6, 15), ministry=Ministry.cognition, empty_reason=NO_REPORT),
            MinistryReport(date=date(2026, 6, 15), ministry=Ministry.business, empty_reason=NO_REPORT),
        ]

        briefing = generate_chancellor_briefing(
            date(2026, 6, 15),
            intent=intent,
            role=role,
            attention_budget=budget,
            daily_review=review,
            research_answers=[answer_with_action, answer_no_action],
            ministry_reports=reports,
        )

        self.assertEqual(briefing.intent_id, intent.id)
        self.assertEqual(briefing.role_id, role.id)
        self.assertEqual(
            briefing.today_focus,
            ["Intent: Ship MetaOS Alpha", "Run citation audit", "Check index health"],
        )
        self.assertIn("Write weekly report", briefing.deferred_items)
        self.assertIn("No action: Evidence is incomplete.", briefing.deferred_items)
        self.assertIn("generic news feed", briefing.ignored_items)
        self.assertIn("cognition: do not force a recommendation today", briefing.ignored_items)
        self.assertIn("Uncited inference present; keep it out of fact statements.", briefing.cognitive_traps)
        self.assertEqual(briefing.source_research_ids, ["answer_1", "answer_2"])
        self.assertEqual(briefing.source_review_id, review.id)

    def test_generate_chancellor_briefing_respects_attention_budget_focus_limit(self) -> None:
        intent = Intent(id="intent_alpha", title="Ship MetaOS Alpha")
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=60)

        briefing = generate_chancellor_briefing(
            date(2026, 6, 15),
            intent=intent,
            role=None,
            attention_budget=budget,
            ministry_reports=[
                MinistryReport(
                    date=date(2026, 6, 15),
                    ministry=Ministry.technology,
                    items=[
                        RecommendationItem(
                            ministry=Ministry.technology,
                            title="One",
                            reason="Useful",
                            intent_alignment="Aligned",
                            reading_cost_minutes=5,
                            cost_of_ignoring="Miss signal",
                            suggested_action="Action one",
                        )
                    ],
                )
            ],
        )

        self.assertEqual(briefing.today_focus, ["Intent: Ship MetaOS Alpha"])


if __name__ == "__main__":
    unittest.main()
