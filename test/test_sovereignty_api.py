from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Callable

from fastapi.testclient import TestClient

import metaos.app.api as api
from metaos.sovereignty import SovereigntyRepository


class SovereigntyApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = SovereigntyRepository(Path(self.temp_dir.name) / "metaos.sqlite3")
        self.original_sovereignty_repo: Callable[[], SovereigntyRepository] = api.sovereignty_repo
        api.sovereignty_repo = lambda: self.repo
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api.sovereignty_repo = self.original_sovereignty_repo
        self.temp_dir.cleanup()

    def test_constitution_create_and_list(self) -> None:
        response = self.client.post(
            "/alpha/constitution",
            json={
                "principles": ["Protect attention", "Prefer evidence"],
                "decision_rules": ["Use reversible decisions"],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("cc_"))
        self.assertEqual(payload["principles"], ["Protect attention", "Prefer evidence"])

        list_response = self.client.get("/alpha/constitution")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.json()], [payload["id"]])

    def test_intent_create_active_and_activate_routes(self) -> None:
        first = self.client.post(
            "/alpha/intents",
            json={
                "title": "First intent",
                "status": "active",
                "priority": 2,
                "success_criteria": ["has evidence"],
            },
        ).json()
        second = self.client.post(
            "/alpha/intents",
            json={
                "title": "Second intent",
                "status": "draft",
                "priority": 1,
            },
        ).json()

        activate_response = self.client.post(f"/alpha/intents/{second['id']}/activate")

        self.assertEqual(activate_response.status_code, 200)
        self.assertEqual(activate_response.json()["status"], "active")
        active_response = self.client.get("/alpha/intents/active")
        self.assertEqual(active_response.status_code, 200)
        self.assertEqual([item["id"] for item in active_response.json()], [second["id"]])

        all_intents = {item["id"]: item for item in self.client.get("/alpha/intents").json()}
        self.assertEqual(all_intents[first["id"]]["status"], "paused")
        missing = self.client.post("/alpha/intents/intent_missing/activate")
        self.assertEqual(missing.status_code, 404)

    def test_current_role_set_and_read_active_role(self) -> None:
        self.client.post(
            "/alpha/current-role",
            json={"name": "Researcher", "responsibilities": ["study evidence"]},
        )
        second_response = self.client.post(
            "/alpha/current-role",
            json={"name": "Builder", "allowed_focus": ["ship Alpha"]},
        )

        self.assertEqual(second_response.status_code, 200)
        roles_response = self.client.get("/alpha/current-role")
        self.assertEqual(roles_response.status_code, 200)
        roles = roles_response.json()
        self.assertEqual(len(roles), 1)
        self.assertEqual(roles[0]["name"], "Builder")

    def test_attention_budget_create_and_list(self) -> None:
        response = self.client.post(
            "/alpha/attention-budgets",
            json={
                "date": "2026-06-15",
                "total_minutes": 240,
                "research_minutes": 60,
                "build_minutes": 120,
                "review_minutes": 30,
                "hard_limits": {"recommendations": 20},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["id"].startswith("budget_"))
        self.assertEqual(payload["date"], "2026-06-15")
        self.assertEqual(self.client.get("/alpha/attention-budgets").json()[0]["id"], payload["id"])

        invalid = self.client.post(
            "/alpha/attention-budgets",
            json={
                "date": "2026-06-15",
                "total_minutes": 60,
                "research_minutes": 45,
                "build_minutes": 30,
            },
        )
        self.assertEqual(invalid.status_code, 422)

    def test_not_to_do_create_filter_and_toggle_active(self) -> None:
        response = self.client.post(
            "/alpha/not-to-do",
            json={
                "title": "Avoid generic news",
                "reason": "Not aligned",
                "scope": "intent",
                "related_intent_id": "intent_alpha",
            },
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()
        self.assertTrue(item["active"])

        disabled = self.client.patch(
            f"/alpha/not-to-do/{item['id']}/active",
            json={"active": False},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(disabled.json()["active"])
        self.assertEqual(self.client.get("/alpha/not-to-do?active=true").json(), [])
        self.assertEqual(self.client.get("/alpha/not-to-do?active=false").json()[0]["id"], item["id"])

        invalid = self.client.post(
            "/alpha/not-to-do",
            json={"title": "Needs intent id", "scope": "intent"},
        )
        self.assertEqual(invalid.status_code, 422)

        missing = self.client.patch(
            "/alpha/not-to-do/ntd_missing/active",
            json={"active": False},
        )
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()

