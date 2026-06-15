from __future__ import annotations

import unittest
from datetime import date

from pydantic import ValidationError

from metaos.compiler import (
    CognitiveOperator,
    EvidenceRequirement,
    EvidenceRequirementType,
    ResearchCompilation,
    ResearchDepth,
    ResearchPlan,
    ResearchPlanStep,
    ResearchScope,
    ResearchTask,
    ResearchTimeRange,
    ThemeSpec,
)


class CompilerSchemaTests(unittest.TestCase):
    def test_five_required_themes_are_theme_spec_data_not_code_branches(self) -> None:
        theme_names = [
            "功高震主",
            "小人得志陷害忠良",
            "听信谗言",
            "功成身退",
            "角色转换失败",
        ]

        compilations = [self.compile_theme(theme_name) for theme_name in theme_names]

        self.assertEqual(
            [compilation.theme_spec.theme_name for compilation in compilations],
            theme_names,
        )
        self.assertTrue(all(isinstance(compilation.theme_spec, ThemeSpec) for compilation in compilations))
        self.assertTrue(all(compilation.operator == CognitiveOperator.causal_analysis for compilation in compilations))
        self.assertTrue(
            all(
                requirement.counterevidence_required
                for compilation in compilations
                for requirement in compilation.evidence_requirements
            )
        )

    def test_theme_spec_and_research_scope_validate_input_boundaries(self) -> None:
        with self.assertRaises(ValidationError):
            ThemeSpec(
                task_id="task_1",
                theme_name="Valid",
                theme_description="Valid",
                key_terms=["   "],
            )

        with self.assertRaises(ValidationError):
            ThemeSpec(
                task_id="task_1",
                theme_name="Valid",
                theme_description="Valid",
                synonyms={" ": ["alias"]},
            )

        with self.assertRaises(ValidationError):
            ResearchScope(
                task_id="task_1",
                time_range=ResearchTimeRange(start=date(2026, 6, 16), end=date(2026, 6, 15)),
            )

    def test_research_compilation_requires_linked_task_ids(self) -> None:
        compilation = self.compile_theme("功成身退")
        bad_requirement = EvidenceRequirement(
            task_id="other_task",
            requirement_type=EvidenceRequirementType.counterevidence,
            description="Find disconfirming evidence",
        )

        with self.assertRaises(ValidationError):
            ResearchCompilation(
                research_task=compilation.research_task,
                operator=compilation.operator,
                theme_spec=compilation.theme_spec,
                evidence_requirements=[bad_requirement],
                research_scope=compilation.research_scope,
                research_plan=compilation.research_plan,
            )

    def compile_theme(self, theme_name: str) -> ResearchCompilation:
        task = ResearchTask(
            question=f"如何识别{theme_name}？",
            intent_id="intent_alpha",
            role_id="role_researcher",
            attention_budget_id="budget_today",
            operator=CognitiveOperator.causal_analysis,
        )
        theme = ThemeSpec(
            task_id=task.id,
            theme_name=theme_name,
            theme_description=f"把“{theme_name}”作为运行时主题规格表达。",
            key_terms=[theme_name, "权力结构", "风险信号"],
            synonyms={theme_name: [f"{theme_name}案例", f"{theme_name}模式"]},
            positive_patterns=["出现可观察行为", "存在明确受益方"],
            negative_patterns=["只有情绪评价", "缺少具体事件"],
            required_dimensions=["事实链", "动机", "结构性约束"],
            excluded_dimensions=["泛泛道德评判"],
            evidence_preferences={"counterevidence": True, "source_diversity": "required"},
        )
        requirements = [
            EvidenceRequirement(
                task_id=task.id,
                requirement_type=EvidenceRequirementType.causal_link,
                description="Collect event-level evidence for the claimed causal chain",
                required_count=2,
                source_constraints={"citation_required": True},
                counterevidence_required=True,
            )
        ]
        scope = ResearchScope(
            task_id=task.id,
            included_sources=["knowledge_base"],
            excluded_sources=["uncited_web_claims"],
            entity_filters=[theme_name],
            cost_limit=30,
            depth=ResearchDepth.standard,
        )
        plan = ResearchPlan(
            task_id=task.id,
            steps=[
                ResearchPlanStep(
                    order=1,
                    operator=CognitiveOperator.causal_analysis,
                    description="Build a causal evidence matrix",
                    query_hints=[theme_name, "反证"],
                    expected_evidence=["primary events", "counterevidence"],
                )
            ],
            query_plan=[theme_name, f"{theme_name} 反证"],
            evidence_requirements=requirements,
            stop_conditions=["required evidence gathered", "attention budget exhausted"],
        )
        return ResearchCompilation(
            research_task=task,
            operator=task.operator,
            theme_spec=theme,
            evidence_requirements=requirements,
            research_scope=scope,
            research_plan=plan,
        )


if __name__ == "__main__":
    unittest.main()
