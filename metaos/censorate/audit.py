"""Censorate citation and scope audit for MetaOS Alpha."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from metaos.compiler import ResearchCompilation, ResearchScope
from metaos.core.schemas import Citation, new_id, utc_now
from metaos.research import EvidenceAssessment
from metaos.research import ResearchAnswer, ResearchExecutionDraft, SourceStatus
from metaos.sovereignty import AttentionBudget


class AuditStatus(str, Enum):
    passed = "passed"
    passed_with_risk = "passed_with_risk"
    requires_revision = "requires_revision"
    failed = "failed"


class AuditSeverity(str, Enum):
    info = "info"
    warning = "warning"
    error = "error"


class CitationAuditItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cite_audit"))
    statement_text: str
    issue: str
    severity: AuditSeverity = AuditSeverity.error

    @field_validator("statement_text", "issue")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("field cannot be blank")
        return text


class ScopeAuditItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id("scope_audit"))
    issue: str
    citation: Citation | None = None
    severity: AuditSeverity = AuditSeverity.error

    @field_validator("issue")
    @classmethod
    def validate_issue(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("issue cannot be blank")
        return text


class AuditReport(BaseModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    task_id: str
    status: AuditStatus
    citation_checks: list[CitationAuditItem] = Field(default_factory=list)
    scope_checks: list[ScopeAuditItem] = Field(default_factory=list)
    counterevidence_checks: list[str] = Field(default_factory=list)
    completeness_checks: list[str] = Field(default_factory=list)
    bias_checks: list[str] = Field(default_factory=list)
    cost_checks: list[str] = Field(default_factory=list)
    required_fixes: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("task_id cannot be blank")
        return text


def audit_research_answer(
    answer: ResearchAnswer,
    execution: ResearchExecutionDraft,
    scope: ResearchScope,
) -> AuditReport:
    citation_checks = audit_citations(answer, execution)
    scope_checks = audit_scope(answer, scope)
    required_fixes = [
        item.issue
        for item in [*citation_checks, *scope_checks]
        if item.severity == AuditSeverity.error
    ]
    return AuditReport(
        task_id=answer.task_id,
        status=AuditStatus.requires_revision if required_fixes else AuditStatus.passed,
        citation_checks=citation_checks,
        scope_checks=scope_checks,
        required_fixes=required_fixes,
    )


def audit_research_quality(
    compilation: ResearchCompilation,
    execution: ResearchExecutionDraft,
    *,
    attention_budget: AttentionBudget | None = None,
    retrieval_cost_minutes: int = 0,
    retrieval_channels: list[str] | None = None,
) -> AuditReport:
    counterevidence_checks = counterevidence_quality_checks(execution)
    completeness_checks = completeness_quality_checks(execution)
    bias_checks = bias_quality_checks(compilation, execution, retrieval_channels or [])
    cost_checks = cost_quality_checks(attention_budget, retrieval_cost_minutes)
    required_fixes = [*counterevidence_checks, *completeness_checks, *cost_checks]
    status = quality_status(required_fixes, bias_checks)
    return AuditReport(
        task_id=compilation.research_task.id,
        status=status,
        counterevidence_checks=counterevidence_checks,
        completeness_checks=completeness_checks,
        bias_checks=bias_checks,
        cost_checks=cost_checks,
        required_fixes=required_fixes,
        residual_risks=bias_checks if status == AuditStatus.passed_with_risk else [],
    )


def counterevidence_quality_checks(execution: ResearchExecutionDraft) -> list[str]:
    checks: list[str] = []
    for row in execution.evidence_matrix:
        if row.assessment == EvidenceAssessment.counterevidence_required:
            checks.append(f"{row.requirement_id}: required counterevidence is missing")
        elif any("counterevidence required" in item for item in row.missing_evidence):
            checks.append(f"{row.requirement_id}: required counterevidence is missing")
    return checks


def completeness_quality_checks(execution: ResearchExecutionDraft) -> list[str]:
    checks: list[str] = []
    for row in execution.evidence_matrix:
        if row.assessment == EvidenceAssessment.missing_evidence:
            checks.extend(row.missing_evidence)
    return checks


def bias_quality_checks(
    compilation: ResearchCompilation,
    execution: ResearchExecutionDraft,
    retrieval_channels: list[str],
) -> list[str]:
    checks: list[str] = []
    if len(set(retrieval_channels)) < 2:
        checks.append("retrieval used fewer than two channels; confirmation bias risk remains")
    requires_counter = any(
        requirement.counterevidence_required
        for requirement in compilation.evidence_requirements
    )
    has_counter = any(row.counter_evidence for row in execution.evidence_matrix)
    if requires_counter and not has_counter:
        checks.append("no counterevidence candidates were observed for a counterevidence-required task")
    return checks


def cost_quality_checks(
    attention_budget: AttentionBudget | None,
    retrieval_cost_minutes: int,
) -> list[str]:
    if attention_budget is None:
        return []
    allowed = attention_budget.research_minutes or attention_budget.total_minutes
    if retrieval_cost_minutes > allowed:
        return [
            f"research cost {retrieval_cost_minutes} minutes exceeds attention budget {allowed} minutes"
        ]
    return []


def quality_status(required_fixes: list[str], bias_checks: list[str]) -> AuditStatus:
    if required_fixes:
        return AuditStatus.requires_revision
    if bias_checks:
        return AuditStatus.passed_with_risk
    return AuditStatus.passed


def audit_citations(
    answer: ResearchAnswer,
    execution: ResearchExecutionDraft,
) -> list[CitationAuditItem]:
    evidence_keys = {citation_key(citation) for citation in evidence_citations(execution)}
    checks: list[CitationAuditItem] = []
    for statement in [
        *answer.fact_statements,
        *answer.model_inferences,
        *answer.disputed_views,
    ]:
        if statement.source_status == SourceStatus.uncited or not statement.citations:
            checks.append(
                CitationAuditItem(
                    statement_text=statement.text,
                    issue="statement has no citation",
                )
            )
            continue
        for citation in statement.citations:
            if citation_key(citation) not in evidence_keys:
                checks.append(
                    CitationAuditItem(
                        statement_text=statement.text,
                        issue="statement citation is not present in evidence matrix",
                    )
                )
    return checks


def audit_scope(answer: ResearchAnswer, scope: ResearchScope) -> list[ScopeAuditItem]:
    checks: list[ScopeAuditItem] = []
    included = set(scope.included_sources)
    excluded = set(scope.excluded_sources)
    for citation in answer.citations:
        source_id = citation.source_id or ""
        if included and source_id and source_id not in included:
            checks.append(
                ScopeAuditItem(
                    issue=f"citation source {source_id} is outside included scope",
                    citation=citation,
                )
            )
        if source_id and source_id in excluded:
            checks.append(
                ScopeAuditItem(
                    issue=f"citation source {source_id} is explicitly excluded",
                    citation=citation,
                )
            )
    return checks


def evidence_citations(execution: ResearchExecutionDraft) -> list[Citation]:
    citations: list[Citation] = []
    for row in execution.evidence_matrix:
        for candidate in [*row.supporting_evidence, *row.counter_evidence]:
            if candidate.citation is not None:
                citations.append(candidate.citation)
    return citations


def citation_key(citation: Citation) -> str:
    return json.dumps(citation.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
