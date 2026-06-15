from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from pydantic import ValidationError

from metaos.sovereignty import (
    AttentionBudget,
    CognitiveConstitution,
    CurrentRole,
    Intent,
    IntentHorizon,
    IntentStatus,
    NotToDoItem,
    NotToDoScope,
)


class SovereigntySchemaTests(unittest.TestCase):
    def test_cognitive_constitution_requires_non_empty_principles(self) -> None:
        constitution = CognitiveConstitution(
            principles=[" protect attention ", "prefer evidence"],
            decision_rules=[" reversible decisions can be faster "],
        )

        self.assertTrue(constitution.id.startswith("cc_"))
        self.assertEqual(constitution.version, 1)
        self.assertEqual(constitution.principles, ["protect attention", "prefer evidence"])
        self.assertEqual(constitution.decision_rules, ["reversible decisions can be faster"])

        with self.assertRaises(ValidationError):
            CognitiveConstitution(principles=[])

        with self.assertRaises(ValidationError):
            CognitiveConstitution(principles=["   "])

    def test_intent_status_horizon_priority_and_text_cleanup(self) -> None:
        intent = Intent(
            title=" Build MetaOS Alpha ",
            description=" constrain attention ",
            horizon=IntentHorizon.quarter,
            status=IntentStatus.active,
            priority=1,
            success_criteria=[" evidence-backed answers "],
            constraints=[" no theme branches "],
            constitution_id=" cc_1 ",
        )

        self.assertTrue(intent.id.startswith("intent_"))
        self.assertEqual(intent.title, "Build MetaOS Alpha")
        self.assertEqual(intent.description, "constrain attention")
        self.assertEqual(intent.horizon, IntentHorizon.quarter)
        self.assertEqual(intent.status, IntentStatus.active)
        self.assertEqual(intent.success_criteria, ["evidence-backed answers"])
        self.assertEqual(intent.constraints, ["no theme branches"])
        self.assertEqual(intent.constitution_id, "cc_1")

        with self.assertRaises(ValidationError):
            Intent(title="valid", priority=0)

        with self.assertRaises(ValidationError):
            Intent(title="   ")

    def test_current_role_validates_active_range(self) -> None:
        active_from = datetime(2026, 6, 15, tzinfo=timezone.utc)
        role = CurrentRole(
            name=" Founder ",
            responsibilities=[" decide what matters "],
            allowed_focus=["architecture"],
            forbidden_focus=["random feeds"],
            active_from=active_from,
            active_to=active_from + timedelta(days=30),
        )

        self.assertTrue(role.id.startswith("role_"))
        self.assertEqual(role.name, "Founder")
        self.assertEqual(role.responsibilities, ["decide what matters"])

        with self.assertRaises(ValidationError):
            CurrentRole(
                name="Founder",
                active_from=active_from,
                active_to=active_from - timedelta(seconds=1),
            )

    def test_attention_budget_rejects_over_allocation_and_bad_limits(self) -> None:
        budget = AttentionBudget(
            date=date(2026, 6, 15),
            total_minutes=300,
            research_minutes=90,
            build_minutes=120,
            review_minutes=30,
            content_minutes=30,
            hard_limits={" recommendations ": 20},
        )

        self.assertTrue(budget.id.startswith("budget_"))
        self.assertEqual(budget.hard_limits, {"recommendations": 20})

        with self.assertRaises(ValidationError):
            AttentionBudget(
                date=date(2026, 6, 15),
                total_minutes=60,
                research_minutes=45,
                build_minutes=30,
            )

        with self.assertRaises(ValidationError):
            AttentionBudget(
                date=date(2026, 6, 15),
                total_minutes=60,
                hard_limits={"feeds": -1},
            )

    def test_not_to_do_item_requires_intent_reference_for_intent_scope(self) -> None:
        item = NotToDoItem(
            title=" Avoid generic news ",
            reason="low alignment",
            scope=NotToDoScope.intent,
            related_intent_id=" intent_1 ",
        )

        self.assertTrue(item.id.startswith("ntd_"))
        self.assertEqual(item.title, "Avoid generic news")
        self.assertEqual(item.related_intent_id, "intent_1")
        self.assertTrue(item.active)

        with self.assertRaises(ValidationError):
            NotToDoItem(title="No intent ref", scope=NotToDoScope.intent)

        with self.assertRaises(ValidationError):
            NotToDoItem(title="   ")


if __name__ == "__main__":
    unittest.main()

