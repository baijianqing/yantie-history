from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue, ResourceReference
from metaos.core_alpha.contracts.execution import ResearchRunResponse, RunExecutionSpecResponse
from metaos.core_alpha.contracts.scope import (
    EvidenceRequirementResponse,
    KnowledgeScopeSourceBindingResponse,
    KnowledgeScopeVersionResponse,
    ResearchCaseResponse,
    ResearchPlanVersionResponse,
    ResearchQuestionResponse,
    SourceResolutionResponse,
)
from metaos.core_alpha.egress import (
    DataEgressGuard,
    EgressPolicyViolation,
    OutboundDataPolicy,
    OutboundInvocationRequest,
    OutboundMaterial,
)
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork


NOW = datetime(2026, 6, 25, 11, 0, tzinfo=timezone.utc)


def code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


def context(command_id: str = "cmd_1") -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=code("user"),
        actor_id="user_1",
        idempotency_key=f"idem_{command_id}",
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


class FixedClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[OutboundInvocationRequest] = []

    def invoke(self, request: OutboundInvocationRequest) -> dict[str, Any]:
        self.calls.append(request)
        return {"accepted": True, "invocation_id": request.invocation_id}


def case_response() -> ResearchCaseResponse:
    return ResearchCaseResponse(
        research_case_id="case_1",
        title="Egress case",
        root_question_id="rq_1",
        current_question_id="rq_1",
        lifecycle_status="open",
        attention_status="active",
        revision=1,
        created_at=NOW,
        updated_at=NOW,
        current_knowledge_scope_version_id=None,
        current_judgment_card_version_id=None,
        current_research_disposition_id=None,
        parent_research_case_id=None,
        archived_at=None,
    )


def question_response() -> ResearchQuestionResponse:
    return ResearchQuestionResponse(
        research_question_id="rq_1",
        research_case_id="case_1",
        question_text="Evaluate with egress policy.",
        question_role="root",
        created_by="user_1",
        created_at=NOW,
        parent_question_id=None,
    )


def source_resolution(
    source_resolution_id: str,
    *,
    item_id: str,
    version_id: str | None,
    access_policy: str,
) -> SourceResolutionResponse:
    return SourceResolutionResponse(
        source_resolution_id=source_resolution_id,
        research_question_id="rq_1",
        resolution_stage="full",
        raw_anchor=item_id,
        requested_access_policy=access_policy,
        resolution_status="resolved",
        candidate_knowledge_item_ids=[],
        created_at=NOW,
        requested_version_hint=None,
        resolved_knowledge_item_id=item_id,
        resolved_knowledge_item_version_id=version_id,
        ambiguity_reason=None,
        failure_reason=None,
    )


def binding(
    binding_id: str,
    *,
    source_resolution_id: str,
    item_id: str,
    version_id: str | None,
    access_policy: str,
    analysis_role: str | None,
) -> KnowledgeScopeSourceBindingResponse:
    return KnowledgeScopeSourceBindingResponse(
        knowledge_scope_source_binding_id=binding_id,
        knowledge_scope_version_id="ksv_1",
        source_resolution_id=source_resolution_id,
        knowledge_item_id=item_id,
        knowledge_item_version_id=version_id,
        access_policy=access_policy,
        analysis_role=analysis_role,
        created_at=NOW,
    )


def scope_response() -> KnowledgeScopeVersionResponse:
    return KnowledgeScopeVersionResponse(
        knowledge_scope_id="ks_1",
        knowledge_scope_version_id="ksv_1",
        research_case_id="case_1",
        version=1,
        lifecycle_status="current",
        scope_mode="evidence_only",
        default_access_policy="excluded",
        source_bindings=[
            binding(
                "kssb_allowed",
                source_resolution_id="sr_allowed",
                item_id="ki_allowed",
                version_id="kiv_allowed",
                access_policy="required",
                analysis_role="primary",
            ),
            binding(
                "kssb_excluded",
                source_resolution_id="sr_excluded",
                item_id="ki_excluded",
                version_id=None,
                access_policy="excluded",
                analysis_role=None,
            ),
        ],
        created_by="user_1",
        created_at=NOW,
        previous_version_id=None,
    )


def requirement() -> EvidenceRequirementResponse:
    return EvidenceRequirementResponse(
        evidence_requirement_id="er_1",
        requirement_type=code("direct_support"),
        description="Find support.",
        required_knowledge_scope_source_binding_ids=["kssb_allowed"],
        counterevidence_required=True,
        alternative_interpretation_required=False,
        completion_condition="Required source terminal.",
        minimum_count=1,
    )


def plan_response() -> ResearchPlanVersionResponse:
    return ResearchPlanVersionResponse(
        research_plan_id="rp_1",
        research_plan_version_id="rpv_1",
        research_case_id="case_1",
        knowledge_scope_version_id="ksv_1",
        version=1,
        lifecycle_status="current",
        research_mode="claim_evaluation",
        primary_objective="Evaluate the claim.",
        evidence_requirements=[requirement()],
        minimum_completion_condition="Required evidence terminal.",
        created_at=NOW,
        previous_version_id=None,
        stop_conditions=None,
        research_budget=None,
    )


def run_response() -> ResearchRunResponse:
    return ResearchRunResponse(
        research_run_id="run_1",
        research_case_id="case_1",
        research_question_id="rq_1",
        knowledge_scope_version_id="ksv_1",
        research_plan_version_id="rpv_1",
        run_execution_spec_id="rex_1",
        status="running",
        revision=1,
        created_at=NOW + timedelta(minutes=1),
        started_at=NOW + timedelta(minutes=1),
        ended_at=None,
        superseded_by_run_id=None,
    )


def execution_spec() -> RunExecutionSpecResponse:
    return RunExecutionSpecResponse(
        run_execution_spec_id="rex_1",
        research_run_id="run_1",
        knowledge_scope_version_id="ksv_1",
        source_resolution_ids=["sr_allowed", "sr_excluded"],
        research_plan_version_id="rpv_1",
        source_version_ids=["kiv_allowed"],
        index_generation_ids=[],
        retrieval_strategy_version="core-alpha-v1.3-candidate",
        context_strategy_version="core-alpha-context-v1",
        embedding_contract={},
        reranker_contract={"enabled": False},
        capability_contracts=[],
        allowed_implementations=[],
        fallback_policy={},
        prompt_version="prompt-not-bound",
        output_schema_version="schema-not-bound",
        audit_policy_version="audit-not-bound",
        decision_fitness_policy_version="decision-fitness-not-bound",
        egress_policy_version="core-alpha-egress-v1",
        system_safety_limits={},
        created_at=NOW + timedelta(minutes=1),
        budget_snapshot_id=None,
    )


def allowed_material(**updates: object) -> OutboundMaterial:
    payload: dict[str, object] = {
        "material_ref": ResourceReference(resource_type="chunk", resource_id="chunk_allowed_1"),
        "knowledge_item_id": "ki_allowed",
        "source_version_id": "kiv_allowed",
        "content_hash": "sha256:aaaaaaaa",
        "location": {"section_path": ["chapter_1"], "start_offset": 1, "end_offset": 20},
        "length": 120,
        "sensitivity_level": "internal",
        "redacted_preview": "short allowed preview",
        "contains_profile_data": False,
        "content_text": None,
    }
    payload.update(updates)
    return OutboundMaterial.model_validate(payload)


def invocation(**updates: object) -> OutboundInvocationRequest:
    payload: dict[str, object] = {
        "invocation_type": code("llm"),
        "invocation_id": "invocation_1",
        "provider": "local-llm",
        "purpose": code("claim_candidate_generation"),
        "materials": [allowed_material()],
        "research_case_id": "case_1",
        "research_run_id": "run_1",
        "research_attempt_id": None,
        "capability_invocation_id": "capability_1",
        "intake_or_import_context_ref": None,
    }
    payload.update(updates)
    return OutboundInvocationRequest.model_validate(payload)


class DataEgressGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = CoreAlphaDatabase(Path(self.temp_dir.name) / "core-alpha.db")
        self.database.initialize()
        self.clock = FixedClock()
        self.seed_case_scope_run()
        self.guard = DataEgressGuard(
            self.database,
            OutboundDataPolicy(
                allowed_providers=["local-llm"],
                allowed_sensitive_levels=["public", "internal"],
                allow_full_material_content=False,
                allow_redacted_preview_storage=False,
            ),
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed_case_scope_run(self) -> None:
        with UnitOfWork(self.database) as uow:
            uow.case_scope.create_case(
                research_case=case_response(),
                root_question=question_response(),
            )
            uow.case_scope.add_source_resolutions(
                [
                    source_resolution(
                        "sr_allowed",
                        item_id="ki_allowed",
                        version_id="kiv_allowed",
                        access_policy="required",
                    ),
                    source_resolution(
                        "sr_excluded",
                        item_id="ki_excluded",
                        version_id=None,
                        access_policy="excluded",
                    ),
                ],
                expected_case_revision=1,
                updated_at=NOW + timedelta(seconds=1),
            )
            uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW + timedelta(seconds=2),
            )
            uow.case_scope.create_research_plan(
                plan_response(),
                expected_case_revision=3,
                updated_at=NOW + timedelta(seconds=3),
            )
            uow.run_evidence.create_research_run(
                research_run=run_response(),
                execution_spec=execution_spec(),
            )

    def manifests(self) -> list:
        with UnitOfWork(self.database, write=False) as uow:
            return uow.material_manifests.list_for_research_run("run_1")

    def test_allowed_invocation_records_manifest_without_full_content_or_preview(self) -> None:
        provider = RecordingProvider()
        result = self.guard.invoke(
            invocation(),
            context=context("cmd_allowed"),
            provider=provider,
        )

        self.assertEqual(result.provider_result["accepted"], True)
        self.assertEqual(len(provider.calls), 1)
        manifest = result.material_manifest
        self.assertEqual(manifest.policy_decision, "allowed")
        self.assertEqual(manifest.materials[0].source_version_id, "kiv_allowed")
        self.assertIsNone(manifest.materials[0].redacted_preview)
        self.assertEqual(manifest.correlation_id, "corr_1")

        stored = self.manifests()[0]
        self.assertEqual(stored.material_manifest_id, manifest.material_manifest_id)
        self.assertEqual(stored.materials[0].content_hash, "sha256:aaaaaaaa")
        self.assertFalse(hasattr(stored.materials[0], "content_text"))

    def test_unknown_provider_denies_records_manifest_and_does_not_call_provider(self) -> None:
        provider = RecordingProvider()
        with self.assertRaises(EgressPolicyViolation) as raised:
            self.guard.invoke(
                invocation(provider="external-llm", invocation_id="invocation_unknown"),
                context=context("cmd_unknown_provider"),
                provider=provider,
            )

        self.assertEqual(provider.calls, [])
        self.assertIn("Provider is not allowed", str(raised.exception))
        manifests = self.manifests()
        self.assertEqual(len(manifests), 1)
        self.assertEqual(manifests[0].policy_decision, "denied")
        self.assertEqual(manifests[0].provider, "external-llm")

    def test_telemetry_and_sensitive_material_are_fail_closed(self) -> None:
        provider = RecordingProvider()
        with self.assertRaises(EgressPolicyViolation):
            self.guard.invoke(
                invocation(purpose=code("telemetry"), invocation_id="invocation_telemetry"),
                context=context("cmd_telemetry"),
                provider=provider,
            )
        with self.assertRaises(EgressPolicyViolation):
            self.guard.invoke(
                invocation(
                    invocation_id="invocation_private",
                    materials=[allowed_material(sensitivity_level="private")],
                ),
                context=context("cmd_private"),
                provider=provider,
            )

        self.assertEqual(provider.calls, [])
        manifests = self.manifests()
        self.assertEqual([manifest.policy_decision for manifest in manifests], ["denied", "denied"])
        self.assertIn("telemetry", manifests[0].decision_reason)
        self.assertIn("sensitivity", manifests[1].decision_reason)

    def test_full_content_requires_explicit_policy_and_is_never_stored(self) -> None:
        provider = RecordingProvider()
        with self.assertRaises(EgressPolicyViolation):
            self.guard.invoke(
                invocation(
                    invocation_id="invocation_content_denied",
                    materials=[allowed_material(content_text="full private sentence")],
                ),
                context=context("cmd_content_denied"),
                provider=provider,
            )

        permissive = DataEgressGuard(
            self.database,
            OutboundDataPolicy(
                allowed_providers=["local-llm"],
                allow_full_material_content=True,
                allowed_sensitive_levels=["public", "internal"],
            ),
            clock=self.clock,
        )
        permissive.invoke(
            invocation(
                invocation_id="invocation_content_allowed",
                materials=[allowed_material(content_text="full private sentence")],
            ),
            context=context("cmd_content_allowed"),
            provider=provider,
        )
        self.assertEqual(len(provider.calls), 1)
        manifests = self.manifests()
        allowed_manifest = manifests[-1]
        self.assertEqual(allowed_manifest.policy_decision, "allowed")
        self.assertFalse(hasattr(allowed_manifest.materials[0], "content_text"))

    def test_excluded_or_out_of_scope_material_is_denied_and_recorded(self) -> None:
        provider = RecordingProvider()
        with self.assertRaises(EgressPolicyViolation):
            self.guard.invoke(
                invocation(
                    invocation_id="invocation_excluded",
                    materials=[
                        allowed_material(
                            material_ref=ResourceReference(
                                resource_type="chunk",
                                resource_id="chunk_excluded_1",
                            ),
                            knowledge_item_id="ki_excluded",
                            source_version_id="kiv_excluded",
                            content_hash="sha256:bbbbbbbb",
                        )
                    ],
                ),
                context=context("cmd_excluded"),
                provider=provider,
            )
        with self.assertRaises(EgressPolicyViolation):
            self.guard.invoke(
                invocation(
                    invocation_id="invocation_out_of_scope",
                    materials=[
                        allowed_material(
                            knowledge_item_id="ki_other",
                            source_version_id="kiv_other",
                            content_hash="sha256:cccccccc",
                        )
                    ],
                ),
                context=context("cmd_out_of_scope"),
                provider=provider,
            )

        self.assertEqual(provider.calls, [])
        manifests = self.manifests()
        self.assertEqual([manifest.policy_decision for manifest in manifests], ["denied", "denied"])
        self.assertIn("excluded", manifests[0].decision_reason)
        self.assertIn("outside", manifests[1].decision_reason)


if __name__ == "__main__":
    unittest.main()
