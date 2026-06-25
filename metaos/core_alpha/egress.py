"""Outbound Data Policy and MaterialManifest support for Core Alpha."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import Field, StrictBool, model_validator

from metaos.core_alpha.contracts.common import (
    CommandContext,
    HashValue,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    ResourceReference,
    StrictContractModel,
)
from metaos.core_alpha.contracts.egress import (
    EgressPolicyDecision,
    MaterialManifestMaterial,
    MaterialManifestResponse,
)
from metaos.core_alpha.contracts.scope import AccessPolicy
from metaos.core_alpha.persistence.database import CoreAlphaDatabase
from metaos.core_alpha.persistence.unit_of_work import UnitOfWork


Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class OutboundMaterial(StrictContractModel):
    material_ref: ResourceReference
    content_hash: HashValue
    length: int = Field(strict=True, ge=0)
    sensitivity_level: NonEmptyString
    knowledge_item_id: ResourceId | None = None
    source_version_id: ResourceId | None = None
    location: dict[str, Any] | None = None
    redacted_preview: NonEmptyString | None = None
    contains_profile_data: StrictBool = False
    content_text: str | None = None


class OutboundInvocationRequest(StrictContractModel):
    invocation_type: OpenCodeValue
    invocation_id: ResourceId
    provider: NonEmptyString
    purpose: OpenCodeValue
    materials: list[OutboundMaterial]
    research_case_id: ResourceId | None = None
    research_run_id: ResourceId | None = None
    research_attempt_id: ResourceId | None = None
    capability_invocation_id: ResourceId | None = None
    intake_or_import_context_ref: ResourceId | None = None


class OutboundDataPolicy(StrictContractModel):
    policy_version: NonEmptyString = "core-alpha-egress-v1"
    allowed_providers: list[NonEmptyString] = Field(default_factory=list)
    allowed_sensitive_levels: list[NonEmptyString] = Field(default_factory=lambda: ["public", "internal"])
    allow_full_material_content: StrictBool = False
    allow_profile_data: StrictBool = False
    allow_telemetry: StrictBool = False
    allow_redacted_preview_storage: StrictBool = False

    @model_validator(mode="after")
    def validate_unique_sets(self) -> "OutboundDataPolicy":
        if len(self.allowed_providers) != len(set(self.allowed_providers)):
            raise ValueError("allowed providers must be unique")
        if len(self.allowed_sensitive_levels) != len(set(self.allowed_sensitive_levels)):
            raise ValueError("allowed sensitive levels must be unique")
        return self


class EgressDecision(StrictContractModel):
    policy_decision: NonEmptyString
    decision_reason: NonEmptyString
    material_manifest: MaterialManifestResponse

    @property
    def allowed(self) -> bool:
        return self.policy_decision == EgressPolicyDecision.allowed


class ProviderInvocation(Protocol):
    def invoke(self, request: OutboundInvocationRequest) -> Any:
        """Execute the provider call after egress policy approval."""


@dataclass(frozen=True)
class ProviderInvocationResult:
    material_manifest: MaterialManifestResponse
    provider_result: Any


class EgressPolicyViolation(RuntimeError):
    """Raised when an outbound invocation is denied before provider execution."""

    def __init__(self, decision: EgressDecision):
        super().__init__(decision.decision_reason)
        self.decision = decision


class DataEgressGuard:
    """Fail-closed policy gate shared by all external provider adapters."""

    def __init__(
        self,
        database: CoreAlphaDatabase,
        policy: OutboundDataPolicy,
        *,
        clock: Clock | None = None,
    ):
        self.database = database
        self.policy = policy
        self.clock = clock or _now

    def evaluate_and_record(
        self,
        request: OutboundInvocationRequest,
        *,
        context: CommandContext,
    ) -> EgressDecision:
        now = self._now()
        decision, reason = self._decide(request)
        with UnitOfWork(self.database) as uow:
            scope_denial = self._scope_denial_reason(uow, request)
            if scope_denial is not None:
                decision = EgressPolicyDecision.denied
                reason = scope_denial
            manifest = self._manifest(
                request=request,
                decision=decision,
                reason=reason,
                context=context,
                now=now,
            )
            uow.material_manifests.add(manifest)
        return EgressDecision(
            policy_decision=decision,
            decision_reason=reason,
            material_manifest=manifest,
        )

    def invoke(
        self,
        request: OutboundInvocationRequest,
        *,
        context: CommandContext,
        provider: ProviderInvocation,
    ) -> ProviderInvocationResult:
        decision = self.evaluate_and_record(request, context=context)
        if not decision.allowed:
            raise EgressPolicyViolation(decision)
        return ProviderInvocationResult(
            material_manifest=decision.material_manifest,
            provider_result=provider.invoke(request),
        )

    def _decide(self, request: OutboundInvocationRequest) -> tuple[str, str]:
        if request.provider not in self.policy.allowed_providers:
            return EgressPolicyDecision.denied, "Provider is not allowed by the outbound policy."
        if request.purpose.code == "telemetry" and not self.policy.allow_telemetry:
            return EgressPolicyDecision.denied, "Third-party telemetry is disabled in Core Alpha."
        if not request.materials:
            return EgressPolicyDecision.denied, "No materials were declared for outbound inspection."
        for material in request.materials:
            if material.content_text and not self.policy.allow_full_material_content:
                return EgressPolicyDecision.denied, "Full material content is not allowed by the outbound policy."
            if material.contains_profile_data and not self.policy.allow_profile_data:
                return EgressPolicyDecision.denied, "Profile data is not allowed by the outbound policy."
            if material.sensitivity_level not in self.policy.allowed_sensitive_levels:
                return EgressPolicyDecision.denied, "Material sensitivity level is not allowed."
            if material.source_version_id is None and material.knowledge_item_id is not None:
                return EgressPolicyDecision.denied, "Knowledge materials require a source version identity."
        return EgressPolicyDecision.allowed, "All declared materials satisfy the outbound policy."

    def _scope_denial_reason(
        self,
        uow: UnitOfWork,
        request: OutboundInvocationRequest,
    ) -> str | None:
        if request.research_run_id is None:
            return None
        run = uow.run_evidence.get_research_run(request.research_run_id)
        if request.research_attempt_id is not None:
            attempt = uow.run_evidence.get_attempt(request.research_attempt_id)
            if attempt.research_run_id != request.research_run_id:
                raise ValueError("egress attempt must belong to the research run")
        scope = uow.case_scope.get_knowledge_scope_version(run.knowledge_scope_version_id)
        excluded_item_ids = {
            binding.knowledge_item_id
            for binding in scope.source_bindings
            if binding.access_policy == AccessPolicy.excluded
        }
        allowed_version_ids = {
            binding.knowledge_item_version_id
            for binding in scope.source_bindings
            if binding.access_policy != AccessPolicy.excluded
            and binding.knowledge_item_version_id is not None
        }
        for material in request.materials:
            if material.knowledge_item_id in excluded_item_ids:
                return "Material belongs to an excluded source."
            if material.source_version_id is not None and material.source_version_id not in allowed_version_ids:
                return "Material source version is outside the run KnowledgeScope."
        return None

    def _manifest(
        self,
        *,
        request: OutboundInvocationRequest,
        decision: str,
        reason: str,
        context: CommandContext,
        now: datetime,
    ) -> MaterialManifestResponse:
        return MaterialManifestResponse(
            material_manifest_id=_new_id("mm"),
            invocation_type=request.invocation_type,
            invocation_id=request.invocation_id,
            provider=request.provider,
            purpose=request.purpose,
            policy_version=self.policy.policy_version,
            policy_decision=decision,
            decision_reason=reason,
            materials=[
                MaterialManifestMaterial(
                    material_ref=material.material_ref,
                    source_version_id=material.source_version_id,
                    content_hash=material.content_hash,
                    location=material.location,
                    length=material.length,
                    sensitivity_level=material.sensitivity_level,
                    redacted_preview=(
                        material.redacted_preview
                        if self.policy.allow_redacted_preview_storage
                        else None
                    ),
                )
                for material in request.materials
            ],
            contains_profile_data=any(material.contains_profile_data for material in request.materials),
            created_at=now,
            research_case_id=request.research_case_id,
            research_run_id=request.research_run_id,
            research_attempt_id=request.research_attempt_id,
            capability_invocation_id=request.capability_invocation_id,
            intake_or_import_context_ref=request.intake_or_import_context_ref,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            trace_id=context.trace_id,
        )

    def _now(self) -> datetime:
        value = self.clock()
        if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("egress clock must return UTC datetimes")
        return value.astimezone(timezone.utc)


__all__ = [
    "DataEgressGuard",
    "EgressDecision",
    "EgressPolicyDecision",
    "EgressPolicyViolation",
    "MaterialManifestMaterial",
    "MaterialManifestResponse",
    "OutboundDataPolicy",
    "OutboundInvocationRequest",
    "OutboundMaterial",
    "ProviderInvocation",
    "ProviderInvocationResult",
]
