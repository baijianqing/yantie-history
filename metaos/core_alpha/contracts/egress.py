"""Core Alpha contracts for outbound data policy and MaterialManifest."""

from __future__ import annotations

from typing import Any

from pydantic import Field, StrictBool, model_validator

from metaos.core_alpha.contracts.common import (
    HashValue,
    NonEmptyString,
    OpenCodeValue,
    ResourceId,
    ResourceReference,
    StrictContractModel,
    UtcDateTime,
)


class EgressPolicyDecision(str):
    allowed = "allowed"
    denied = "denied"


class MaterialManifestMaterial(StrictContractModel):
    material_ref: ResourceReference
    source_version_id: ResourceId | None
    content_hash: HashValue
    location: dict[str, Any] | None
    length: int = Field(strict=True, ge=0)
    sensitivity_level: NonEmptyString
    redacted_preview: NonEmptyString | None


class MaterialManifestResponse(StrictContractModel):
    material_manifest_id: ResourceId
    invocation_type: OpenCodeValue
    invocation_id: ResourceId
    provider: NonEmptyString
    purpose: OpenCodeValue
    policy_version: NonEmptyString
    policy_decision: NonEmptyString
    decision_reason: NonEmptyString
    materials: list[MaterialManifestMaterial]
    contains_profile_data: StrictBool
    created_at: UtcDateTime
    research_case_id: ResourceId | None = None
    research_run_id: ResourceId | None = None
    research_attempt_id: ResourceId | None = None
    capability_invocation_id: ResourceId | None = None
    intake_or_import_context_ref: ResourceId | None = None
    correlation_id: ResourceId
    causation_id: ResourceId
    trace_id: ResourceId

    @model_validator(mode="after")
    def require_context(self) -> "MaterialManifestResponse":
        has_context = any(
            value is not None
            for value in (
                self.research_case_id,
                self.research_run_id,
                self.capability_invocation_id,
                self.intake_or_import_context_ref,
            )
        )
        if not has_context:
            raise ValueError("material manifest requires a case, run, capability, or import context")
        if self.policy_decision not in {EgressPolicyDecision.allowed, EgressPolicyDecision.denied}:
            raise ValueError("policy_decision must be allowed or denied")
        return self


__all__ = [
    "EgressPolicyDecision",
    "MaterialManifestMaterial",
    "MaterialManifestResponse",
]
