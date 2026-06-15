"""Research execution contracts for MetaOS Alpha."""

from metaos.research.answer import (
    AnswerStatement,
    ResearchAnswer,
    SourceStatus,
    draft_research_answer,
)
from metaos.research.executor import (
    EvidenceAssessment,
    EvidenceMatrixRow,
    ResearchExecutionDraft,
    build_evidence_matrix,
)
from metaos.research.service import (
    EvidenceSearch,
    execute_research_plan,
    retrieve_research_candidates,
)

__all__ = [
    "AnswerStatement",
    "EvidenceAssessment",
    "EvidenceMatrixRow",
    "EvidenceSearch",
    "ResearchAnswer",
    "ResearchExecutionDraft",
    "SourceStatus",
    "build_evidence_matrix",
    "draft_research_answer",
    "execute_research_plan",
    "retrieve_research_candidates",
]
