from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from metaos.censorate import AuditStatus, audit_research_quality
from metaos.compiler import (
    CognitiveOperator,
    EvidenceRequirement,
    EvidenceRequirementType,
    ResearchCompilation,
    ResearchPlan,
    ResearchScope,
    ResearchTask,
    ThemeSpec,
)
from metaos.core.schemas import Citation
from metaos.research import build_evidence_matrix
from metaos.search import EvidenceCandidate
from metaos.sovereignty import AttentionBudget


class CensorateQualityTests(unittest.TestCase):
    def test_quality_audit_flags_missing_counterevidence_completeness_and_cost(self) -> None:
        compilation = self.compilation(required_count=2, counterevidence_required=True)
        requirement = compilation.evidence_requirements[0]
        execution = build_evidence_matrix(
            compilation,
            [self.candidate("chunk_1", requirement.id, "support")],
        )
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=30, research_minutes=10)

        report = audit_research_quality(
            compilation,
            execution,
            attention_budget=budget,
            retrieval_cost_minutes=15,
            retrieval_channels=["vector"],
        )

        self.assertEqual(report.status, AuditStatus.requires_revision)
        self.assertTrue(any("counterevidence" in item for item in report.counterevidence_checks))
        self.assertTrue(any("needs 1 more supporting evidence" in item for item in report.completeness_checks))
        self.assertTrue(any("exceeds attention budget" in item for item in report.cost_checks))
        self.assertEqual(report.required_fixes, [*report.counterevidence_checks, *report.completeness_checks, *report.cost_checks])

    def test_quality_audit_marks_single_channel_as_residual_bias_risk(self) -> None:
        compilation = self.compilation(required_count=1, counterevidence_required=False)
        requirement = compilation.evidence_requirements[0]
        execution = build_evidence_matrix(
            compilation,
            [self.candidate("chunk_1", requirement.id, "support")],
        )

        report = audit_research_quality(
            compilation,
            execution,
            retrieval_cost_minutes=0,
            retrieval_channels=["vector"],
        )

        self.assertEqual(report.status, AuditStatus.passed_with_risk)
        self.assertEqual(report.required_fixes, [])
        self.assertEqual(report.residual_risks, report.bias_checks)

    def test_quality_audit_passes_when_requirements_budget_and_channels_are_satisfied(self) -> None:
        compilation = self.compilation(required_count=1, counterevidence_required=True)
        requirement = compilation.evidence_requirements[0]
        execution = build_evidence_matrix(
            compilation,
            [
                self.candidate("chunk_1", requirement.id, "support"),
                self.candidate("chunk_2", requirement.id, "counter"),
            ],
        )
        budget = AttentionBudget(date=date(2026, 6, 15), total_minutes=60, research_minutes=30)

        report = audit_research_quality(
            compilation,
            execution,
            attention_budget=budget,
            retrieval_cost_minutes=20,
            retrieval_channels=["vector", "full_text"],
        )

        self.assertEqual(report.status, AuditStatus.passed)
        self.assertEqual(report.required_fixes, [])
        self.assertEqual(report.residual_risks, [])

    def compilation(self, *, required_count: int, counterevidence_required: bool) -> ResearchCompilation:
        task = ResearchTask(
            question="研究功高震主",
            intent_id="intent_alpha",
            operator=CognitiveOperator.causal_analysis,
        )
        theme = ThemeSpec(
            task_id=task.id,
            theme_name="功高震主",
            theme_description="Runtime theme",
            key_terms=["功高震主"],
        )
        requirements = [
            EvidenceRequirement(
                id="req_quality",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.causal_link,
                description="Quality requirement",
                required_count=required_count,
                counterevidence_required=counterevidence_required,
            )
        ]
        scope = ResearchScope(task_id=task.id)
        plan = ResearchPlan(task_id=task.id, evidence_requirements=requirements)
        return ResearchCompilation(
            research_task=task,
            operator=task.operator,
            theme_spec=theme,
            evidence_requirements=requirements,
            research_scope=scope,
            research_plan=plan,
        )

    def candidate(self, chunk_id: str, requirement_id: str, stance: str) -> EvidenceCandidate:
        return EvidenceCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="item_1",
            text=f"{stance} evidence",
            score=0.8,
            fused_score=0.1,
            citation=Citation(source_id="src_1", file_path=Path("case.md")),
            metadata={"requirement_id": requirement_id, "stance": stance},
        )


if __name__ == "__main__":
    unittest.main()
