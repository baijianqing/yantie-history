from __future__ import annotations

import unittest
from pathlib import Path

from metaos.censorate import AuditStatus, audit_research_answer
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
from metaos.research import (
    AnswerStatement,
    ResearchAnswer,
    SourceStatus,
    build_evidence_matrix,
    draft_research_answer,
)
from metaos.search import EvidenceCandidate


class CensorateAuditTests(unittest.TestCase):
    def test_audit_passes_when_answer_citations_match_evidence_and_scope(self) -> None:
        compilation = self.compilation(included_sources=["src_1"])
        requirement = compilation.evidence_requirements[0]
        citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("case.md"))
        execution = build_evidence_matrix(
            compilation,
            [self.candidate("chunk_1", requirement.id, citation)],
        )
        answer = draft_research_answer(
            compilation,
            execution,
            conclusion="The evidence supports a cautious next action.",
            action_title="Create a follow-up checklist",
        )

        report = audit_research_answer(answer, execution, compilation.research_scope)

        self.assertEqual(report.status, AuditStatus.passed)
        self.assertEqual(report.citation_checks, [])
        self.assertEqual(report.scope_checks, [])
        self.assertEqual(report.required_fixes, [])

    def test_audit_flags_uncited_statements(self) -> None:
        compilation = self.compilation(included_sources=["src_1"])
        execution = build_evidence_matrix(compilation, [])
        answer = ResearchAnswer(
            task_id=compilation.research_task.id,
            fact_statements=[
                AnswerStatement(text="Unsupported factual statement", source_status=SourceStatus.uncited)
            ],
            no_action_reason="No action until evidence exists.",
        )

        report = audit_research_answer(answer, execution, compilation.research_scope)

        self.assertEqual(report.status, AuditStatus.requires_revision)
        self.assertEqual(report.citation_checks[0].issue, "statement has no citation")
        self.assertIn("statement has no citation", report.required_fixes)

    def test_audit_flags_citation_not_in_evidence_and_scope_violations(self) -> None:
        compilation = self.compilation(included_sources=["src_1"], excluded_sources=["src_2"])
        evidence_citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("case.md"))
        outside_citation = Citation(source_id="src_2", asset_id="asset_2", file_path=Path("outside.md"))
        requirement = compilation.evidence_requirements[0]
        execution = build_evidence_matrix(
            compilation,
            [self.candidate("chunk_1", requirement.id, evidence_citation)],
        )
        answer = ResearchAnswer(
            task_id=compilation.research_task.id,
            fact_statements=[
                AnswerStatement(
                    text="Statement cites outside source",
                    source_status=SourceStatus.cited,
                    citations=[outside_citation],
                )
            ],
            no_action_reason="Scope violation blocks action.",
            citations=[outside_citation],
        )

        report = audit_research_answer(answer, execution, compilation.research_scope)

        self.assertEqual(report.status, AuditStatus.requires_revision)
        self.assertEqual(
            report.citation_checks[0].issue,
            "statement citation is not present in evidence matrix",
        )
        self.assertEqual(len(report.scope_checks), 2)
        self.assertTrue(any("outside included scope" in item.issue for item in report.scope_checks))
        self.assertTrue(any("explicitly excluded" in item.issue for item in report.scope_checks))

    def compilation(
        self,
        *,
        included_sources: list[str],
        excluded_sources: list[str] | None = None,
    ) -> ResearchCompilation:
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
                id="req_fact",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.primary_fact,
                description="Find primary facts",
                required_count=1,
            )
        ]
        scope = ResearchScope(
            task_id=task.id,
            included_sources=included_sources,
            excluded_sources=excluded_sources or [],
        )
        plan = ResearchPlan(task_id=task.id, evidence_requirements=requirements)
        return ResearchCompilation(
            research_task=task,
            operator=task.operator,
            theme_spec=theme,
            evidence_requirements=requirements,
            research_scope=scope,
            research_plan=plan,
        )

    def candidate(self, chunk_id: str, requirement_id: str, citation: Citation) -> EvidenceCandidate:
        return EvidenceCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="item_1",
            text="supporting evidence",
            score=0.8,
            fused_score=0.1,
            citation=citation,
            metadata={"requirement_id": requirement_id, "stance": "support"},
        )


if __name__ == "__main__":
    unittest.main()
