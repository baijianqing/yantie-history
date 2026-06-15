from __future__ import annotations

import unittest
from pathlib import Path

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
from metaos.research import EvidenceAssessment, build_evidence_matrix
from metaos.search import EvidenceCandidate


class ResearchExecutorTests(unittest.TestCase):
    def test_build_evidence_matrix_groups_support_and_counterevidence(self) -> None:
        compilation = self.compilation()
        causal_requirement, fact_requirement = compilation.evidence_requirements
        citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("case.md"))

        draft = build_evidence_matrix(
            compilation,
            [
                self.candidate("chunk_1", causal_requirement.id, "support", citation),
                self.candidate("chunk_2", causal_requirement.id, "support", citation),
                self.candidate("chunk_3", causal_requirement.id, "counter", citation),
                self.candidate("chunk_4", fact_requirement.id, "support", citation),
            ],
        )

        self.assertEqual(draft.task_id, compilation.research_task.id)
        self.assertEqual(len(draft.evidence_matrix), 2)
        causal_row = draft.evidence_matrix[0]
        fact_row = draft.evidence_matrix[1]
        self.assertEqual(causal_row.assessment, EvidenceAssessment.contested)
        self.assertEqual([item.chunk_id for item in causal_row.supporting_evidence], ["chunk_1", "chunk_2"])
        self.assertEqual([item.chunk_id for item in causal_row.counter_evidence], ["chunk_3"])
        self.assertEqual(causal_row.supporting_evidence[0].citation.file_path, Path("case.md"))
        self.assertEqual(fact_row.assessment, EvidenceAssessment.satisfied)
        self.assertEqual(draft.missing_evidence, [])

    def test_build_evidence_matrix_reports_missing_support_and_counterevidence(self) -> None:
        compilation = self.compilation()
        causal_requirement = compilation.evidence_requirements[0]

        draft = build_evidence_matrix(
            compilation,
            [
                self.candidate(
                    "chunk_1",
                    causal_requirement.id,
                    "support",
                    Citation(source_id="src_1", file_path=Path("case.md")),
                )
            ],
        )

        row = draft.evidence_matrix[0]
        self.assertEqual(row.assessment, EvidenceAssessment.missing_evidence)
        self.assertIn("needs 1 more supporting evidence", row.missing_evidence[0])
        self.assertIn("counterevidence required", row.missing_evidence[1])
        self.assertEqual(draft.counterevidence_needed, [causal_requirement.id])

    def compilation(self) -> ResearchCompilation:
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
                id="req_causal",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.causal_link,
                description="Prove or weaken the causal chain",
                required_count=2,
                counterevidence_required=True,
            ),
            EvidenceRequirement(
                id="req_fact",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.primary_fact,
                description="Find primary facts",
                required_count=1,
            ),
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

    def candidate(
        self,
        chunk_id: str,
        requirement_id: str,
        stance: str,
        citation: Citation,
    ) -> EvidenceCandidate:
        return EvidenceCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="item_1",
            text=f"{stance} evidence",
            score=0.8,
            fused_score=0.1,
            citation=citation,
            metadata={"requirement_id": requirement_id, "stance": stance},
        )


if __name__ == "__main__":
    unittest.main()
