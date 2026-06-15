"""Evidence matrix construction for MetaOS Alpha research execution."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from metaos.compiler import EvidenceRequirement, ResearchCompilation
from metaos.core.schemas import new_id, utc_now
from metaos.search import EvidenceCandidate


class EvidenceAssessment(str, Enum):
    satisfied = "satisfied"
    missing_evidence = "missing_evidence"
    counterevidence_required = "counterevidence_required"
    contested = "contested"


class EvidenceMatrixRow(BaseModel):
    id: str = Field(default_factory=lambda: new_id("emr"))
    task_id: str
    requirement_id: str
    claim_or_question: str
    supporting_evidence: list[EvidenceCandidate] = Field(default_factory=list)
    counter_evidence: list[EvidenceCandidate] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    assessment: EvidenceAssessment = EvidenceAssessment.missing_evidence
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id", "requirement_id", "claim_or_question")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class ResearchExecutionDraft(BaseModel):
    task_id: str
    evidence_matrix: list[EvidenceMatrixRow] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    counterevidence_needed: list[str] = Field(default_factory=list)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("task_id cannot be blank")
        return text


def build_evidence_matrix(
    compilation: ResearchCompilation,
    candidates: list[EvidenceCandidate],
) -> ResearchExecutionDraft:
    rows = [
        build_matrix_row(compilation.research_task.id, requirement, candidates)
        for requirement in compilation.evidence_requirements
    ]
    return ResearchExecutionDraft(
        task_id=compilation.research_task.id,
        evidence_matrix=rows,
        missing_evidence=[
            missing
            for row in rows
            for missing in row.missing_evidence
            if row.assessment in {
                EvidenceAssessment.missing_evidence,
                EvidenceAssessment.counterevidence_required,
            }
        ],
        counterevidence_needed=[
            row.requirement_id
            for row in rows
            if any("counterevidence" in item for item in row.missing_evidence)
        ],
    )


def build_matrix_row(
    task_id: str,
    requirement: EvidenceRequirement,
    candidates: list[EvidenceCandidate],
) -> EvidenceMatrixRow:
    related = [
        candidate
        for candidate in candidates
        if candidate_matches_requirement(candidate, requirement)
    ]
    supporting = [candidate for candidate in related if evidence_stance(candidate) != "counter"]
    counter = [candidate for candidate in related if evidence_stance(candidate) == "counter"]
    missing = missing_evidence_messages(requirement, supporting, counter)
    return EvidenceMatrixRow(
        task_id=task_id,
        requirement_id=requirement.id,
        claim_or_question=requirement.description,
        supporting_evidence=supporting,
        counter_evidence=counter,
        missing_evidence=missing,
        assessment=assess_row(requirement, supporting, counter, missing),
    )


def candidate_matches_requirement(
    candidate: EvidenceCandidate,
    requirement: EvidenceRequirement,
) -> bool:
    metadata = candidate.metadata or {}
    if metadata.get("requirement_id"):
        return str(metadata["requirement_id"]) == requirement.id
    if metadata.get("requirement_type"):
        return str(metadata["requirement_type"]) == requirement.requirement_type.value
    return True


def evidence_stance(candidate: EvidenceCandidate) -> str:
    stance = str((candidate.metadata or {}).get("stance") or "support").strip().lower()
    if stance in {"counter", "counterevidence", "contradicts", "disconfirming"}:
        return "counter"
    return "support"


def missing_evidence_messages(
    requirement: EvidenceRequirement,
    supporting: list[EvidenceCandidate],
    counter: list[EvidenceCandidate],
) -> list[str]:
    missing: list[str] = []
    if len(supporting) < requirement.required_count:
        missing.append(
            f"{requirement.id}: needs {requirement.required_count - len(supporting)} more supporting evidence"
        )
    if requirement.counterevidence_required and not counter:
        missing.append(f"{requirement.id}: counterevidence required")
    return missing


def assess_row(
    requirement: EvidenceRequirement,
    supporting: list[EvidenceCandidate],
    counter: list[EvidenceCandidate],
    missing: list[str],
) -> EvidenceAssessment:
    if len(supporting) < requirement.required_count:
        return EvidenceAssessment.missing_evidence
    if requirement.counterevidence_required and not counter:
        return EvidenceAssessment.counterevidence_required
    if counter:
        return EvidenceAssessment.contested
    return EvidenceAssessment.satisfied
