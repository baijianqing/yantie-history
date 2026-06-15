from __future__ import annotations

import unittest
from typing import Any

from pydantic import ValidationError

from metaos.compiler import (
    CognitiveOperator,
    CompileResearchRequest,
    IssueCompiler,
    PROMPT_VERSION,
    ResearchCompilation,
)


class FakeCompilerProvider:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        theme_name = payload["question"].split("：", 1)[-1]
        return {
            "operator": "causal_analysis",
            "theme_spec": {
                "theme_name": theme_name,
                "theme_description": f"Runtime theme for {theme_name}",
                "key_terms": [theme_name, "causal signal", "counterevidence"],
                "synonyms": {theme_name: [f"{theme_name} pattern"]},
                "positive_patterns": ["observable event chain", "actor incentives"],
                "negative_patterns": ["uncited opinion"],
                "required_dimensions": ["facts", "actors", "mechanism"],
                "excluded_dimensions": ["moralizing without evidence"],
                "evidence_preferences": {"counterevidence": True},
            },
            "evidence_requirements": [
                {
                    "requirement_type": "causal_link",
                    "description": "Find cited events that support or weaken the causal chain",
                    "required_count": 2,
                    "source_constraints": {"citation_required": True},
                    "counterevidence_required": True,
                }
            ],
            "research_scope": {
                "included_sources": ["knowledge_base"],
                "excluded_sources": ["uncited_web_claims"],
                "entity_filters": [theme_name],
                "cost_limit": 30,
                "depth": "standard",
            },
            "research_plan": {
                "steps": [
                    {
                        "order": 1,
                        "operator": "causal_analysis",
                        "description": "Collect evidence and counterevidence",
                        "query_hints": [theme_name, "counterevidence"],
                        "expected_evidence": ["supporting events", "contradicting events"],
                    }
                ],
                "query_plan": [theme_name, f"{theme_name} counterevidence"],
                "stop_conditions": ["evidence requirements satisfied"],
                "prompt_version": PROMPT_VERSION,
            },
        }


class BadCompilerProvider:
    def compile_theme(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "operator": "causal_analysis",
            "theme_spec": {
                "theme_name": "",
                "theme_description": "invalid",
            },
        }


class IssueCompilerTests(unittest.TestCase):
    def test_issue_compiler_compiles_five_themes_through_same_runtime_path(self) -> None:
        provider = FakeCompilerProvider()
        compiler = IssueCompiler(provider)
        theme_names = [
            "功高震主",
            "小人得志陷害忠良",
            "听信谗言",
            "功成身退",
            "角色转换失败",
        ]

        compilations = [
            compiler.compile(
                CompileResearchRequest(
                    question=f"研究：{theme_name}",
                    intent_id="intent_alpha",
                    role_id="role_researcher",
                    attention_budget_id="budget_today",
                )
            )
            for theme_name in theme_names
        ]

        self.assertEqual(len(provider.calls), len(theme_names))
        self.assertTrue(all(isinstance(item, ResearchCompilation) for item in compilations))
        self.assertEqual([item.theme_spec.theme_name for item in compilations], theme_names)
        self.assertTrue(all(item.operator == CognitiveOperator.causal_analysis for item in compilations))
        self.assertTrue(
            all(
                item.research_task.theme_spec_id == item.theme_spec.id
                and item.research_task.scope_id == item.research_scope.id
                for item in compilations
            )
        )
        self.assertTrue(
            all(
                call["allowed_operators"] == [operator.value for operator in CognitiveOperator]
                for call in provider.calls
            )
        )

    def test_issue_compiler_rejects_invalid_model_output(self) -> None:
        compiler = IssueCompiler(BadCompilerProvider())

        with self.assertRaises(ValidationError):
            compiler.compile(
                CompileResearchRequest(
                    question="研究：功成身退",
                    intent_id="intent_alpha",
                )
            )


if __name__ == "__main__":
    unittest.main()
