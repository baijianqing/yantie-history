from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from metaos.sovereignty import (
    AttentionBudget,
    CognitiveConstitution,
    CurrentRole,
    Intent,
    IntentStatus,
    NotToDoItem,
    NotToDoScope,
    SovereigntyRecordNotFoundError,
    SovereigntyRepository,
    initialize_sovereignty_database,
)


class SovereigntyRepositoryTests(unittest.TestCase):
    def make_repo(self, root: Path) -> SovereigntyRepository:
        database_path = root / "metaos.sqlite3"
        return SovereigntyRepository(database_path)

    def test_initialize_creates_sovereignty_tables_alongside_existing_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "metaos.sqlite3"
            initialize_sovereignty_database(database_path)

            connection = sqlite3.connect(database_path)
            try:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            finally:
                connection.close()

            self.assertIn("jobs", table_names)
            self.assertIn("knowledge_items", table_names)
            self.assertIn("cognitive_constitutions", table_names)
            self.assertIn("intents", table_names)
            self.assertIn("current_roles", table_names)
            self.assertIn("attention_budgets", table_names)
            self.assertIn("not_to_do_items", table_names)

    def test_constitution_round_trips_json_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(Path(temp_dir))
            constitution = CognitiveConstitution(
                principles=["Protect attention", "Prefer evidence"],
                decision_rules=["Use reversible decisions"],
                attention_rules=["No generic feeds"],
                not_to_do_defaults=["Do not chase broad news"],
                risk_preferences={"research_depth": "medium"},
            )

            repo.constitutions.add(constitution)
            loaded = repo.constitutions.get(constitution.id)

            self.assertEqual(loaded, constitution)
            self.assertEqual(repo.constitutions.list(), [constitution])
            with self.assertRaises(SovereigntyRecordNotFoundError):
                repo.constitutions.get("cc_missing")

    def test_intent_update_active_pauses_other_active_intents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(Path(temp_dir))
            first = Intent(title="First", status=IntentStatus.active, priority=2)
            second = Intent(title="Second", status=IntentStatus.paused, priority=1)
            repo.intents.add(first)
            repo.intents.add(second)

            activated = repo.intents.update_active(second.id)

            self.assertEqual(activated.status, IntentStatus.active)
            self.assertEqual(repo.intents.get(first.id).status, IntentStatus.paused)
            self.assertEqual(repo.intents.list(status=IntentStatus.active), [activated])

    def test_current_role_update_active_closes_previous_open_role(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(Path(temp_dir))
            first_start = datetime(2026, 6, 1, tzinfo=timezone.utc)
            second_start = first_start + timedelta(days=1)
            first = CurrentRole(name="Researcher", active_from=first_start)
            second = CurrentRole(name="Builder", active_from=second_start)
            repo.roles.add(first)
            repo.roles.add(second)

            activated = repo.roles.update_active(second.id)

            self.assertIsNone(activated.active_to)
            self.assertIsNotNone(repo.roles.get(first.id).active_to)
            self.assertEqual(repo.roles.list(active_only=True), [activated])

    def test_attention_budget_round_trips_and_lists_by_date(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(Path(temp_dir))
            budget = AttentionBudget(
                date=date(2026, 6, 15),
                total_minutes=240,
                research_minutes=60,
                build_minutes=120,
                review_minutes=30,
                hard_limits={"recommendations": 20},
            )

            repo.attention_budgets.add(budget)
            loaded = repo.attention_budgets.get(budget.id)

            self.assertEqual(loaded, budget)
            self.assertEqual(repo.attention_budgets.get_by_date(date(2026, 6, 15)), [budget])

    def test_not_to_do_update_active_toggles_item(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self.make_repo(Path(temp_dir))
            item = NotToDoItem(
                title="Avoid generic news",
                reason="Not aligned with intent",
                scope=NotToDoScope.intent,
                related_intent_id="intent_alpha",
            )
            repo.not_to_do.add(item)

            disabled = repo.not_to_do.update_active(item.id, active=False)

            self.assertFalse(disabled.active)
            self.assertEqual(repo.not_to_do.list(active=True), [])
            self.assertEqual(repo.not_to_do.list(active=False), [disabled])


if __name__ == "__main__":
    unittest.main()
