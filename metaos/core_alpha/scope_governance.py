"""Scope Governance command/query handlers for Core Alpha."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from metaos.core_alpha.commands import ApplicationCommandHandler, CommandExecution, CommandOutcome
from metaos.core_alpha.contracts.common import CommandContext, ResourceReference
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
    AdjustKnowledgeScopeRequest,
    AdjustResearchPlanRequest,
    CreateKnowledgeScopeRequest,
    CreateResearchPlanRequest,
    CreateSourceResolutionsData,
    CreateSourceResolutionsRequest,
    EvidenceRequirementResponse,
    KnowledgeScopeCommandData,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    ResearchCaseLifecycleStatus,
    ResearchPlanCommandData,
    ResearchPlanVersionResponse,
    ResolutionStage,
    ResolutionStatus,
    SourceAnchorInput,
    SourceResolutionResponse,
    VersionLifecycleStatus,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    RecordNotFoundError,
    UnitOfWork,
)
from metaos.knowledge.catalog import (
    KnowledgeCatalogAdapter,
    KnowledgeCatalogItem,
    KnowledgeCatalogVersion,
)


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


@dataclass(frozen=True)
class _CatalogMatch:
    item: KnowledgeCatalogItem
    match_rank: int


class ScopeGovernanceCommandHandler:
    """Application command facade for SourceResolution, KnowledgeScope, and ResearchPlan."""

    def __init__(
        self,
        command_handler: ApplicationCommandHandler,
        catalog: KnowledgeCatalogAdapter,
        *,
        clock: Clock | None = None,
    ):
        self.command_handler = command_handler
        self.catalog = catalog
        self.clock = clock or _now

    def create_source_resolutions(
        self,
        research_case_id: str,
        request: CreateSourceResolutionsRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/source-resolutions",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_source_resolutions(
                uow=uow,
                research_case_id=research_case_id,
                request=request,
                now=now,
            ),
        )

    def create_knowledge_scope(
        self,
        research_case_id: str,
        request: CreateKnowledgeScopeRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        scope_id = _new_id("ks")
        scope_version_id = _new_id("ksv")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/knowledge-scopes",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_knowledge_scope(
                uow=uow,
                research_case_id=research_case_id,
                request=request,
                context=context,
                scope_id=scope_id,
                scope_version_id=scope_version_id,
                now=now,
            ),
        )

    def adjust_knowledge_scope(
        self,
        current_knowledge_scope_version_id: str,
        request: AdjustKnowledgeScopeRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        new_version_id = _new_id("ksv")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/knowledge-scopes/{current_knowledge_scope_version_id}/commands/adjust",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._adjust_knowledge_scope(
                uow=uow,
                current_knowledge_scope_version_id=current_knowledge_scope_version_id,
                request=request,
                context=context,
                new_version_id=new_version_id,
                now=now,
            ),
        )

    def create_research_plan(
        self,
        research_case_id: str,
        request: CreateResearchPlanRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        plan_id = _new_id("rp")
        plan_version_id = _new_id("rpv")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-cases/{research_case_id}/research-plans",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._create_research_plan(
                uow=uow,
                research_case_id=research_case_id,
                request=request,
                plan_id=plan_id,
                plan_version_id=plan_version_id,
                now=now,
            ),
        )

    def adjust_research_plan(
        self,
        current_research_plan_version_id: str,
        request: AdjustResearchPlanRequest,
        *,
        context: CommandContext,
    ) -> CommandExecution:
        now = self._now()
        new_version_id = _new_id("rpv")
        body = request.model_dump(mode="json")
        return self.command_handler.execute(
            scope=f"{context.actor_id}:POST:/alpha/research-plans/{current_research_plan_version_id}/commands/adjust",
            idempotency_key=context.idempotency_key,
            request_body=body,
            context=context,
            callback=lambda uow: self._adjust_research_plan(
                uow=uow,
                current_research_plan_version_id=current_research_plan_version_id,
                request=request,
                new_version_id=new_version_id,
                now=now,
            ),
        )

    def _create_source_resolutions(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        request: CreateSourceResolutionsRequest,
        now: datetime,
    ) -> CommandOutcome:
        question = uow.case_scope.get_question(request.research_question_id)
        if question.research_case_id != research_case_id:
            raise ValueError("source resolutions must belong to the route research case")
        case = uow.case_scope.get_case(research_case_id)
        self._ensure_open(case)
        resolutions = [
            self._resolve_anchor(anchor=anchor, question_id=request.research_question_id, now=now)
            for anchor in request.anchors
        ]
        updated = uow.case_scope.add_source_resolutions(
            resolutions,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = CreateSourceResolutionsData(source_resolutions=resolutions)
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            research_case_id=research_case_id,
            revision=updated.revision,
            event_type_code="source_resolutions_created",
            response_status=201,
        )

    def _create_knowledge_scope(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        request: CreateKnowledgeScopeRequest,
        context: CommandContext,
        scope_id: str,
        scope_version_id: str,
        now: datetime,
    ) -> CommandOutcome:
        case = uow.case_scope.get_case(research_case_id)
        self._ensure_open(case)
        bindings = self._scope_bindings(
            uow=uow,
            request_bindings=request.bindings,
            research_case_id=research_case_id,
            scope_version_id=scope_version_id,
            now=now,
        )
        scope = KnowledgeScopeVersionResponse(
            knowledge_scope_id=scope_id,
            knowledge_scope_version_id=scope_version_id,
            research_case_id=research_case_id,
            version=1,
            lifecycle_status=VersionLifecycleStatus.current,
            scope_mode=request.scope_mode,
            default_access_policy=request.default_access_policy,
            source_bindings=bindings,
            created_by=context.actor_id,
            created_at=now,
            previous_version_id=None,
        )
        updated = uow.case_scope.create_knowledge_scope(
            scope,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = KnowledgeScopeCommandData(knowledge_scope=scope, superseded_version_ref=None)
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            research_case_id=research_case_id,
            revision=updated.revision,
            event_type_code="knowledge_scope_created",
            response_status=201,
        )

    def _adjust_knowledge_scope(
        self,
        *,
        uow: UnitOfWork,
        current_knowledge_scope_version_id: str,
        request: AdjustKnowledgeScopeRequest,
        context: CommandContext,
        new_version_id: str,
        now: datetime,
    ) -> CommandOutcome:
        current = uow.case_scope.get_knowledge_scope_version(current_knowledge_scope_version_id)
        case = uow.case_scope.get_case(current.research_case_id)
        self._ensure_open(case)
        bindings = self._scope_bindings(
            uow=uow,
            request_bindings=request.bindings,
            research_case_id=current.research_case_id,
            scope_version_id=new_version_id,
            now=now,
        )
        scope = KnowledgeScopeVersionResponse(
            knowledge_scope_id=current.knowledge_scope_id,
            knowledge_scope_version_id=new_version_id,
            research_case_id=current.research_case_id,
            version=current.version + 1,
            lifecycle_status=VersionLifecycleStatus.current,
            scope_mode=request.scope_mode,
            default_access_policy=request.default_access_policy,
            source_bindings=bindings,
            created_by=context.actor_id,
            created_at=now,
            previous_version_id=current.knowledge_scope_version_id,
        )
        updated = uow.case_scope.adjust_knowledge_scope(
            scope,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = KnowledgeScopeCommandData(
            knowledge_scope=scope,
            superseded_version_ref=ResourceReference(
                resource_type="knowledge_scope_version",
                resource_id=current.knowledge_scope_version_id,
            ),
        )
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            research_case_id=current.research_case_id,
            revision=updated.revision,
            event_type_code="knowledge_scope_adjusted",
        )

    def _create_research_plan(
        self,
        *,
        uow: UnitOfWork,
        research_case_id: str,
        request: CreateResearchPlanRequest,
        plan_id: str,
        plan_version_id: str,
        now: datetime,
    ) -> CommandOutcome:
        case = uow.case_scope.get_case(research_case_id)
        self._ensure_open(case)
        scope = uow.case_scope.get_knowledge_scope_version(request.knowledge_scope_version_id)
        if scope.research_case_id != research_case_id:
            raise ValueError("research plan scope must belong to the route research case")
        requirements = self._requirements(request.evidence_requirements, scope)
        plan = ResearchPlanVersionResponse(
            research_plan_id=plan_id,
            research_plan_version_id=plan_version_id,
            research_case_id=research_case_id,
            knowledge_scope_version_id=request.knowledge_scope_version_id,
            version=1,
            lifecycle_status=VersionLifecycleStatus.current,
            research_mode=request.research_mode,
            primary_objective=request.primary_objective,
            evidence_requirements=requirements,
            minimum_completion_condition=request.minimum_completion_condition,
            created_at=now,
            previous_version_id=None,
            stop_conditions=None,
            research_budget=None,
        )
        updated = uow.case_scope.create_research_plan(
            plan,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = ResearchPlanCommandData(research_plan=plan, superseded_version_ref=None)
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            research_case_id=research_case_id,
            revision=updated.revision,
            event_type_code="research_plan_created",
            response_status=201,
        )

    def _adjust_research_plan(
        self,
        *,
        uow: UnitOfWork,
        current_research_plan_version_id: str,
        request: AdjustResearchPlanRequest,
        new_version_id: str,
        now: datetime,
    ) -> CommandOutcome:
        current = uow.case_scope.get_research_plan_version(current_research_plan_version_id)
        case = uow.case_scope.get_case(current.research_case_id)
        self._ensure_open(case)
        scope = uow.case_scope.get_knowledge_scope_version(request.knowledge_scope_version_id)
        if scope.research_case_id != current.research_case_id:
            raise ValueError("research plan scope must belong to the same case")
        requirements = self._requirements(request.evidence_requirements, scope)
        plan = ResearchPlanVersionResponse(
            research_plan_id=current.research_plan_id,
            research_plan_version_id=new_version_id,
            research_case_id=current.research_case_id,
            knowledge_scope_version_id=request.knowledge_scope_version_id,
            version=current.version + 1,
            lifecycle_status=VersionLifecycleStatus.current,
            research_mode=request.research_mode,
            primary_objective=request.primary_objective,
            evidence_requirements=requirements,
            minimum_completion_condition=request.minimum_completion_condition,
            created_at=now,
            previous_version_id=current.research_plan_version_id,
            stop_conditions=None,
            research_budget=None,
        )
        updated = uow.case_scope.adjust_research_plan(
            plan,
            expected_case_revision=request.expected_revision,
            updated_at=now,
        )
        data = ResearchPlanCommandData(
            research_plan=plan,
            superseded_version_ref=ResourceReference(
                resource_type="research_plan_version",
                resource_id=current.research_plan_version_id,
            ),
        )
        return self._case_outcome(
            data=data.model_dump(mode="json"),
            research_case_id=current.research_case_id,
            revision=updated.revision,
            event_type_code="research_plan_adjusted",
        )

    def _resolve_anchor(
        self,
        *,
        anchor: SourceAnchorInput,
        question_id: str,
        now: datetime,
    ) -> SourceResolutionResponse:
        matches = self._catalog_matches(anchor.raw_anchor)
        if not matches:
            return SourceResolutionResponse(
                source_resolution_id=_new_id("sr"),
                research_question_id=question_id,
                resolution_stage=ResolutionStage.full,
                raw_anchor=anchor.raw_anchor,
                requested_access_policy=anchor.requested_access_policy,
                resolution_status=ResolutionStatus.not_found,
                candidate_knowledge_item_ids=[],
                created_at=now,
                requested_version_hint=anchor.requested_version_hint,
                resolved_knowledge_item_id=None,
                resolved_knowledge_item_version_id=None,
                ambiguity_reason=None,
                failure_reason="No knowledge item matched the explicit source anchor.",
            )

        best_rank = matches[0].match_rank
        best = [match for match in matches if match.match_rank == best_rank]
        if len(best) > 1:
            return SourceResolutionResponse(
                source_resolution_id=_new_id("sr"),
                research_question_id=question_id,
                resolution_stage=ResolutionStage.full,
                raw_anchor=anchor.raw_anchor,
                requested_access_policy=anchor.requested_access_policy,
                resolution_status=ResolutionStatus.ambiguous,
                candidate_knowledge_item_ids=[match.item.knowledge_item_id for match in best],
                created_at=now,
                requested_version_hint=anchor.requested_version_hint,
                resolved_knowledge_item_id=None,
                resolved_knowledge_item_version_id=None,
                ambiguity_reason="Multiple knowledge items matched the explicit source anchor.",
                failure_reason=None,
            )

        item = best[0].item
        if anchor.requested_access_policy == AccessPolicy.excluded:
            return SourceResolutionResponse(
                source_resolution_id=_new_id("sr"),
                research_question_id=question_id,
                resolution_stage=ResolutionStage.full,
                raw_anchor=anchor.raw_anchor,
                requested_access_policy=anchor.requested_access_policy,
                resolution_status=ResolutionStatus.resolved,
                candidate_knowledge_item_ids=[],
                created_at=now,
                requested_version_hint=anchor.requested_version_hint,
                resolved_knowledge_item_id=item.knowledge_item_id,
                resolved_knowledge_item_version_id=None,
                ambiguity_reason=None,
                failure_reason=None,
            )

        version = self._current_version_or_none(item)
        if version is None or version.availability_status != "available":
            return SourceResolutionResponse(
                source_resolution_id=_new_id("sr"),
                research_question_id=question_id,
                resolution_stage=ResolutionStage.full,
                raw_anchor=anchor.raw_anchor,
                requested_access_policy=anchor.requested_access_policy,
                resolution_status=ResolutionStatus.unavailable,
                candidate_knowledge_item_ids=[item.knowledge_item_id],
                created_at=now,
                requested_version_hint=anchor.requested_version_hint,
                resolved_knowledge_item_id=None,
                resolved_knowledge_item_version_id=None,
                ambiguity_reason=None,
                failure_reason="The matched source has no currently available content version.",
            )

        if not self._version_hint_matches(anchor.requested_version_hint, version):
            return SourceResolutionResponse(
                source_resolution_id=_new_id("sr"),
                research_question_id=question_id,
                resolution_stage=ResolutionStage.full,
                raw_anchor=anchor.raw_anchor,
                requested_access_policy=anchor.requested_access_policy,
                resolution_status=ResolutionStatus.unavailable,
                candidate_knowledge_item_ids=[item.knowledge_item_id],
                created_at=now,
                requested_version_hint=anchor.requested_version_hint,
                resolved_knowledge_item_id=None,
                resolved_knowledge_item_version_id=None,
                ambiguity_reason=None,
                failure_reason="The requested source version is not available in the catalog.",
            )

        return SourceResolutionResponse(
            source_resolution_id=_new_id("sr"),
            research_question_id=question_id,
            resolution_stage=ResolutionStage.full,
            raw_anchor=anchor.raw_anchor,
            requested_access_policy=anchor.requested_access_policy,
            resolution_status=ResolutionStatus.resolved,
            candidate_knowledge_item_ids=[],
            created_at=now,
            requested_version_hint=anchor.requested_version_hint,
            resolved_knowledge_item_id=item.knowledge_item_id,
            resolved_knowledge_item_version_id=version.knowledge_item_version_id,
            ambiguity_reason=None,
            failure_reason=None,
        )

    def _catalog_matches(self, raw_anchor: str) -> list[_CatalogMatch]:
        needle = _normalized(raw_anchor)
        matches: list[_CatalogMatch] = []
        for item in self.catalog.list_items(limit=10000):
            if _normalized(item.title) == needle:
                matches.append(_CatalogMatch(item=item, match_rank=0))
                continue
            aliases = {_normalized(alias) for alias in item.aliases}
            if needle in aliases:
                matches.append(_CatalogMatch(item=item, match_rank=1))
        return sorted(matches, key=lambda match: (match.match_rank, match.item.knowledge_item_id))

    def _current_version_or_none(
        self,
        item: KnowledgeCatalogItem,
    ) -> KnowledgeCatalogVersion | None:
        version_id = item.current_knowledge_item_version_id
        if version_id is None:
            return None
        return self.catalog.get_version(version_id)

    @staticmethod
    def _version_hint_matches(hint: str | None, version: KnowledgeCatalogVersion) -> bool:
        if hint is None:
            return True
        normalized_hint = _normalized(hint)
        return normalized_hint in {
            _normalized(version.knowledge_item_version_id),
            str(version.version),
        }

    def _scope_bindings(
        self,
        *,
        uow: UnitOfWork,
        request_bindings: Sequence[Any],
        research_case_id: str,
        scope_version_id: str,
        now: datetime,
    ) -> list[KnowledgeScopeSourceBindingResponse]:
        bindings: list[KnowledgeScopeSourceBindingResponse] = []
        for binding in request_bindings:
            resolution = self._resolution_for_binding(
                uow=uow,
                source_resolution_id=binding.source_resolution_id,
                research_case_id=research_case_id,
            )
            self._validate_binding_matches_resolution(binding, resolution)
            bindings.append(
                KnowledgeScopeSourceBindingResponse(
                    knowledge_scope_source_binding_id=_new_id("kssb"),
                    knowledge_scope_version_id=scope_version_id,
                    source_resolution_id=binding.source_resolution_id,
                    knowledge_item_id=binding.knowledge_item_id,
                    knowledge_item_version_id=binding.knowledge_item_version_id,
                    access_policy=binding.access_policy,
                    analysis_role=binding.analysis_role,
                    created_at=now,
                )
            )
        return bindings

    @staticmethod
    def _resolution_for_binding(
        *,
        uow: UnitOfWork,
        source_resolution_id: str,
        research_case_id: str,
    ) -> SourceResolutionResponse:
        case_questions = uow.case_scope.list_questions(research_case_id)
        for question in case_questions:
            for resolution in uow.case_scope.list_source_resolutions(question.research_question_id):
                if resolution.source_resolution_id == source_resolution_id:
                    return resolution
        raise RecordNotFoundError(f"source resolution not found: {source_resolution_id}")

    @staticmethod
    def _validate_binding_matches_resolution(
        binding: Any,
        resolution: SourceResolutionResponse,
    ) -> None:
        if resolution.resolution_status != ResolutionStatus.resolved:
            raise ValueError("scope bindings require resolved source resolutions")
        if binding.access_policy != resolution.requested_access_policy:
            raise ValueError("scope binding access policy must match source resolution")
        if binding.knowledge_item_id != resolution.resolved_knowledge_item_id:
            raise ValueError("scope binding knowledge item must match source resolution")
        if binding.access_policy == AccessPolicy.excluded:
            if binding.knowledge_item_version_id is not None:
                raise ValueError("excluded source bindings cannot fix a content version")
            return
        if binding.knowledge_item_version_id != resolution.resolved_knowledge_item_version_id:
            raise ValueError("scope binding content version must match source resolution")

    @staticmethod
    def _requirements(
        requirements: Sequence[Any],
        scope: KnowledgeScopeVersionResponse,
    ) -> list[EvidenceRequirementResponse]:
        valid_binding_ids = {
            binding.knowledge_scope_source_binding_id for binding in scope.source_bindings
        }
        responses: list[EvidenceRequirementResponse] = []
        for requirement in requirements:
            missing = [
                binding_id
                for binding_id in requirement.required_knowledge_scope_source_binding_ids
                if binding_id not in valid_binding_ids
            ]
            if missing:
                raise ValueError("evidence requirement references an unknown scope binding")
            responses.append(
                EvidenceRequirementResponse(
                    evidence_requirement_id=_new_id("er"),
                    requirement_type=requirement.requirement_type,
                    description=requirement.description,
                    required_knowledge_scope_source_binding_ids=list(
                        requirement.required_knowledge_scope_source_binding_ids
                    ),
                    counterevidence_required=requirement.counterevidence_required,
                    alternative_interpretation_required=(
                        requirement.alternative_interpretation_required
                    ),
                    completion_condition=requirement.completion_condition,
                    minimum_count=requirement.minimum_count,
                )
            )
        return responses

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("scope governance clock must return UTC datetimes")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _ensure_open(case: Any) -> None:
        if case.lifecycle_status != ResearchCaseLifecycleStatus.open:
            raise ValueError("research case is not open")

    @staticmethod
    def _case_outcome(
        *,
        data: Mapping[str, Any],
        research_case_id: str,
        revision: int,
        event_type_code: str,
        response_status: int = 200,
    ) -> CommandOutcome:
        return CommandOutcome(
            data=data,
            primary_aggregate_type="research_case",
            primary_aggregate_id=research_case_id,
            primary_aggregate_revision=revision,
            response_status=response_status,
            event_type_code=event_type_code,
            event_payload={"research_case_id": research_case_id},
        )


class ScopeGovernanceQueryHandler:
    """Read-side facade for Scope Governance data."""

    def __init__(self, database: CoreAlphaDatabase):
        self.database = database

    def list_source_resolutions(self, research_question_id: str) -> list[SourceResolutionResponse]:
        with UnitOfWork(self.database, write=False) as uow:
            uow.case_scope.get_question(research_question_id)
            return uow.case_scope.list_source_resolutions(research_question_id)

    def get_knowledge_scope_version(self, version_id: str) -> KnowledgeScopeVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.case_scope.get_knowledge_scope_version(version_id)

    def get_current_knowledge_scope_for_case(
        self,
        research_case_id: str,
    ) -> KnowledgeScopeVersionResponse | None:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.case_scope.get_current_knowledge_scope_for_case(research_case_id)

    def get_research_plan_version(self, version_id: str) -> ResearchPlanVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.case_scope.get_research_plan_version(version_id)

    def get_current_research_plan(self, research_plan_id: str) -> ResearchPlanVersionResponse:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.case_scope.get_current_research_plan(research_plan_id)


__all__ = [
    "ScopeGovernanceCommandHandler",
    "ScopeGovernanceQueryHandler",
]
