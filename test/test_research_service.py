from __future__ import annotations

import unittest
from pathlib import Path

from metaos.compiler import (
    CognitiveOperator,
    EvidenceRequirement,
    EvidenceRequirementType,
    ResearchCompilation,
    ResearchPlan,
    ResearchPlanStep,
    ResearchScope,
    ResearchTask,
    ThemeSpec,
)
from metaos.core.schemas import Citation
from metaos.research import (
    EvidenceAssessment,
    execute_research_plan,
    retrieve_research_candidates,
)
from metaos.search import EvidenceCandidate


class FakeEvidenceSearch:
    def __init__(self, requirement_id: str | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self.requirement_id = requirement_id

    def __call__(self, query: str, *, top_k: int = 5):
        self.calls.append((query, top_k))
        if "decision" in query.lower():
            return [
                self.candidate(
                    "chunk_support",
                    "Service flow has cited evidence for action.",
                ),
                self.candidate(
                    "chunk_counter",
                    "Counterevidence: HTTP/RQ wiring gap remains.",
                ),
                self.candidate(
                    "chunk_support",
                    "Service flow has cited evidence for action.",
                ),
            ]
        if "primary" in query.lower():
            return [
                self.candidate(
                    "chunk_fact",
                    "Primary fact: DailySummary can become a reviewable EpisodeSpec.",
                )
            ]
        return []

    def candidate(self, chunk_id: str, text: str) -> EvidenceCandidate:
        metadata = {}
        if self.requirement_id:
            metadata["requirement_id"] = self.requirement_id
        return EvidenceCandidate(
            chunk_id=chunk_id,
            knowledge_item_id="ki_alpha",
            text=text,
            score=0.8,
            fused_score=0.1,
            citation=Citation(
                source_id="src_alpha",
                asset_id="asset_alpha",
                file_path=Path(f"{chunk_id}.md"),
                excerpt=text,
            ),
            metadata=metadata,
        )


class ResearchServiceTests(unittest.TestCase):
    def test_execute_research_plan_recalls_candidates_and_builds_matrix(self) -> None:
        compilation = self.compilation()
        search = FakeEvidenceSearch()

        execution = execute_research_plan(compilation, search, top_k_per_query=3)

        decision_row = execution.evidence_matrix[0]
        fact_row = execution.evidence_matrix[1]
        self.assertEqual(decision_row.assessment, EvidenceAssessment.contested)
        self.assertEqual(fact_row.assessment, EvidenceAssessment.satisfied)
        self.assertEqual(execution.missing_evidence, [])
        self.assertEqual([item.chunk_id for item in decision_row.supporting_evidence], ["chunk_support"])
        self.assertEqual([item.chunk_id for item in decision_row.counter_evidence], ["chunk_counter"])
        self.assertEqual(decision_row.supporting_evidence[0].metadata["requirement_id"], "req_decision")
        self.assertEqual(decision_row.supporting_evidence[0].metadata["requirement_type"], "decision_criterion")
        self.assertEqual(decision_row.counter_evidence[0].metadata["stance"], "counter")
        self.assertEqual(decision_row.supporting_evidence[0].citation.source_id, "src_alpha")
        self.assertTrue(all(top_k == 3 for _, top_k in search.calls))

    def test_retrieve_research_candidates_preserves_explicit_requirement_metadata(self) -> None:
        compilation = self.compilation()
        search = FakeEvidenceSearch(requirement_id="pretagged")

        candidates = retrieve_research_candidates(compilation, search, top_k_per_query=2)

        self.assertEqual(candidates[0].metadata["requirement_id"], "pretagged")
        self.assertEqual(candidates[0].metadata["requirement_type"], "decision_criterion")
        self.assertEqual(candidates[0].metadata["stance"], "support")

    def compilation(self) -> ResearchCompilation:
        task = ResearchTask(
            question="Should Alpha closure proceed?",
            intent_id="intent_alpha",
            operator=CognitiveOperator.decision_support,
        )
        theme = ThemeSpec(
            task_id=task.id,
            theme_name="Alpha closure",
            theme_description="Runtime closure decision",
            key_terms=["Alpha"],
        )
        requirements = [
            EvidenceRequirement(
                id="req_decision",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.decision_criterion,
                description="Decision evidence for Alpha closure",
                required_count=1,
                counterevidence_required=True,
            ),
            EvidenceRequirement(
                id="req_primary",
                task_id=task.id,
                requirement_type=EvidenceRequirementType.primary_fact,
                description="Primary fact for DailySummary video",
                required_count=1,
            ),
        ]
        scope = ResearchScope(task_id=task.id, included_sources=["src_alpha"])
        plan = ResearchPlan(
            task_id=task.id,
            steps=[
                ResearchPlanStep(
                    order=1,
                    operator=CognitiveOperator.decision_support,
                    description="Collect decision evidence",
                    query_hints=["Decision evidence for Alpha closure"],
                )
            ],
            query_plan=[],
            evidence_requirements=requirements,
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
