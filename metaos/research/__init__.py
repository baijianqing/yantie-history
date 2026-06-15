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
    RESEARCH_EXECUTION_VERSION,
    ResearchExecutionReport,
    ResearchProgressEvent,
    ResearchProgressStage,
    ResearchRetrievalRun,
    execute_research_plan,
    execute_research_plan_with_trace,
    retrieve_research_candidates,
    retrieve_research_candidates_with_trace,
)

__all__ = [
    "AnswerStatement",
    "EvidenceAssessment",
    "EvidenceMatrixRow",
    "EvidenceSearch",
    "RESEARCH_EXECUTION_VERSION",
    "ResearchAnswer",
    "ResearchExecutionDraft",
    "ResearchExecutionReport",
    "ResearchProgressEvent",
    "ResearchProgressStage",
    "ResearchRetrievalRun",
    "SourceStatus",
    "build_evidence_matrix",
    "draft_research_answer",
    "execute_research_plan",
    "execute_research_plan_with_trace",
    "retrieve_research_candidates",
    "retrieve_research_candidates_with_trace",
]
