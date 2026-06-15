from __future__ import annotations

import unittest
from pathlib import Path

from pydantic import ValidationError

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
from metaos.ledger import ActionSourceType
from metaos.research import ResearchAnswer, SourceStatus, build_evidence_matrix, draft_research_answer
from metaos.search import EvidenceCandidate


class ResearchAnswerTests(unittest.TestCase):
    def test_draft_research_answer_creates_cited_answer_and_action(self) -> None:
        compilation = self.compilation()
        requirement = compilation.evidence_requirements[0]
        citation = Citation(source_id="src_1", asset_id="asset_1", file_path=Path("case.md"))
        execution = build_evidence_matrix(
            compilation,
            [
                self.candidate("chunk_1", "supporting event", requirement.id, "support", citation),
                self.candidate("chunk_2", "counter event", requirement.id, "counter", citation),
            ],
        )

        answer = draft_research_answer(
            compilation,
            execution,
            conclusion="The pattern is plausible but contested.",
            action_title="Review incentive structure before acting",
            personal_reflections=["Check whether my role bias is amplifying this pattern."],
        )

        self.assertEqual(answer.task_id, compilation.research_task.id)
        self.assertEqual(answer.fact_statements[0].source_status, SourceStatus.cited)
        self.assertEqual(answer.model_inferences[0].source_status, SourceStatus.cited)
        self.assertEqual(answer.disputed_views[0].text, "counter event")
        self.assertEqual(answer.personal_reflections[0].source_status, SourceStatus.uncited)
        self.assertEqual(len(answer.actions), 1)
        self.assertEqual(answer.actions[0].source_type, ActionSourceType.research_answer)
        self.assertEqual(answer.actions[0].source_id, answer.id)
        self.assertEqual(answer.actions[0].intent_id, compilation.research_task.intent_id)
        self.assertIsNone(answer.no_action_reason)

    def test_draft_research_answer_can_explicitly_choose_no_action(self) -> None:
        compilation = self.compilation()
        execution = build_evidence_matrix(compilation, [])

        answer = draft_research_answer(
            compilation,
            execution,
            conclusion="Evidence is insufficient for action.",
            no_action_reason="Evidence requirements were not satisfied.",
        )

        self.assertEqual(answer.actions, [])
        self.assertEqual(answer.no_action_reason, "Evidence requirements were not satisfied.")
        self.assertEqual(answer.model_inferences[0].source_status, SourceStatus.uncited)

    def test_research_answer_requires_action_or_no_action_reason(self) -> None:
        with self.assertRaises(ValidationError):
            ResearchAnswer(
                task_id="task_1",
                model_inferences=[],
            )

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
                required_count=1,
                counterevidence_required=True,
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

    def candidate(
        self,
        chunk_id: str,
        text: str,
        requirement_id: str,
        stance: str,
        citation: Citation,
    ) -> EvidenceCandidate:
        return EvidenceCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="item_1",
            text=text,
            score=0.8,
            fused_score=0.1,
            citation=citation,
            metadata={"requirement_id": requirement_id, "stance": stance},
        )


if __name__ == "__main__":
    unittest.main()
