from __future__ import annotations

import unittest
from typing import Any, Callable

from fastapi.testclient import TestClient

import metaos.app.api as api
from metaos.compiler import IssueCompiler, PROMPT_VERSION


class FakeCompilerProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        theme_name = payload["question"].replace("Research ", "")
        return {
            "operator": "decision_support",
            "theme_spec": {
                "theme_name": theme_name,
                "theme_description": f"Runtime theme for {theme_name}",
                "key_terms": [theme_name, "evidence"],
                "synonyms": {theme_name: [f"{theme_name} case"]},
                "positive_patterns": ["cited support"],
                "negative_patterns": ["uncited claim"],
                "required_dimensions": ["facts", "counterevidence"],
                "excluded_dimensions": ["generic news"],
                "evidence_preferences": {"citation_required": True},
            },
            "evidence_requirements": [
                {
                    "requirement_type": "decision_criterion",
                    "description": "Find cited decision evidence",
                    "required_count": 1,
                    "counterevidence_required": True,
                }
            ],
            "research_scope": {
                "included_sources": ["src_alpha"],
                "excluded_sources": ["untrusted_feed"],
                "entity_filters": [theme_name],
                "cost_limit": 30,
                "depth": "standard",
            },
            "research_plan": {
                "steps": [
                    {
                        "order": 1,
                        "operator": "decision_support",
                        "description": "Collect support and counterevidence",
                        "query_hints": [theme_name],
                        "expected_evidence": ["support", "counter"],
                    }
                ],
                "query_plan": [theme_name],
                "stop_conditions": ["requirements satisfied"],
                "prompt_version": PROMPT_VERSION,
            },
        }


class BadCompilerProvider:
    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "operator": "decision_support",
            "theme_spec": {
                "theme_name": "",
                "theme_description": "invalid",
            },
        }


class AlphaResearchCompileApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = FakeCompilerProvider()
        self.original_issue_compiler: Callable = api.issue_compiler
        api.issue_compiler = lambda: IssueCompiler(self.provider)
        self.client = TestClient(api.app)

    def tearDown(self) -> None:
        api.issue_compiler = self.original_issue_compiler

    def test_compile_endpoint_returns_schema_valid_research_compilation(self) -> None:
        response = self.client.post(
            "/alpha/research/compile",
            json={
                "question": "Research Alpha closure",
                "intent_id": "intent_alpha",
                "role_id": "role_builder",
                "attention_budget_id": "budget_today",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(self.provider.calls), 1)
        self.assertEqual(self.provider.calls[0]["intent_id"], "intent_alpha")
        self.assertIn("decision_support", self.provider.calls[0]["allowed_operators"])
        self.assertEqual(payload["operator"], "decision_support")
        self.assertEqual(payload["research_task"]["intent_id"], "intent_alpha")
        self.assertEqual(payload["research_task"]["role_id"], "role_builder")
        self.assertEqual(payload["research_task"]["attention_budget_id"], "budget_today")
        self.assertEqual(payload["theme_spec"]["theme_name"], "Alpha closure")
        self.assertEqual(payload["evidence_requirements"][0]["requirement_type"], "decision_criterion")
        self.assertTrue(payload["evidence_requirements"][0]["counterevidence_required"])
        self.assertEqual(payload["research_plan"]["prompt_version"], PROMPT_VERSION)

    def test_compile_endpoint_uses_same_runtime_path_for_different_themes(self) -> None:
        names = ["功高震主", "角色转换失败"]

        payloads = [
            self.client.post(
                "/alpha/research/compile",
                json={"question": f"Research {name}", "intent_id": "intent_alpha"},
            ).json()
            for name in names
        ]

        self.assertEqual([payload["theme_spec"]["theme_name"] for payload in payloads], names)
        self.assertEqual(len(self.provider.calls), 2)

    def test_compile_endpoint_returns_400_for_invalid_model_output(self) -> None:
        api.issue_compiler = lambda: IssueCompiler(BadCompilerProvider())

        response = self.client.post(
            "/alpha/research/compile",
            json={"question": "Research broken", "intent_id": "intent_alpha"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("theme_name", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
