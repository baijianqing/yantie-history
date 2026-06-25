from __future__ import annotations

import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metaos.core.schemas import (
    Asset,
    AssetKind,
    Chunk,
    Citation,
    KnowledgeCategory,
    KnowledgeItem,
    Source,
    SourceType,
)
from metaos.core_alpha.case_management import ResearchCaseCommandHandler
from metaos.core_alpha.commands import ApplicationCommandHandler
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
    AdjustKnowledgeScopeRequest,
    AdjustResearchPlanRequest,
    AnalysisRole,
    CreateKnowledgeScopeRequest,
    CreateResearchCaseRequest,
    CreateResearchPlanRequest,
    CreateSourceResolutionsRequest,
    EvidenceRequirementInput,
    KnowledgeScopeBindingInput,
    QuestionRole,
    ResearchMode,
    ScopeMode,
    SourceAnchorInput,
)
from metaos.core_alpha.persistence import (
    ConcurrencyConflictError,
    CoreAlphaDatabase,
    UnitOfWork,
)
from metaos.core_alpha.scope_governance import (
    ScopeGovernanceCommandHandler,
    ScopeGovernanceQueryHandler,
)
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.workspace.catalog import (
    AssetRepository,
    ChunkRepository,
    KnowledgeRepository,
    SourceRepository,
)


NOW = datetime(2026, 6, 25, 9, 0, tzinfo=timezone.utc)


def context(command_id: str, *, idempotency_key: str) -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=OpenCodeValue(code="user", registry_version="core-alpha-v1"),
        actor_id="user_1",
        idempotency_key=idempotency_key,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


def code(name: str) -> OpenCodeValue:
    return OpenCodeValue(code=name, registry_version="core-alpha-v1")


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixedClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


class ScopeGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.workspace_db = self.root / "workspace.sqlite3"
        self.clock = FixedClock()
        app_handler = ApplicationCommandHandler(self.core_db)
        self.case_commands = ResearchCaseCommandHandler(app_handler, clock=self.clock)
        self.scope_commands = ScopeGovernanceCommandHandler(
            app_handler,
            KnowledgeCatalogAdapter(self.workspace_db),
            clock=self.clock,
        )
        self.scope_queries = ScopeGovernanceQueryHandler(self.core_db)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def add_catalog_item(
        self,
        *,
        item_id: str,
        title: str,
        aliases: list[str] | None = None,
        content: str = "# Source\n\nEvidence.",
        missing_file: bool = False,
    ) -> None:
        path = self.root / f"{item_id}.md"
        path.write_text(content, encoding="utf-8")
        source = Source(
            id=f"src_{item_id}",
            type=SourceType.local_file,
            uri=path.as_uri(),
            title=title,
        )
        asset = Asset(
            id=f"asset_{item_id}",
            source_id=source.id,
            kind=AssetKind.markdown,
            path=path,
            mime_type="text/markdown",
            sha256=sha_file(path),
            size_bytes=path.stat().st_size,
        )
        if missing_file:
            path.unlink()
        item = KnowledgeItem(
            id=item_id,
            title=title,
            summary=f"{title} summary",
            category=KnowledgeCategory.philosophy,
            tags=aliases or [],
            markdown_path=path,
            citations=[
                Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=path,
                    excerpt="Evidence.",
                )
            ],
            metadata={
                "source_id": source.id,
                "asset_id": asset.id,
                "language": "zh-Hans",
                "parser": "markdown-v1",
                "chunker": "test-chunker-v1",
                "index_version": "test-index-v1",
            },
        )
        chunks = [
            Chunk(
                id=f"chunk_{item_id}_1",
                knowledge_item_id=item.id,
                text=f"{title} first evidence.",
                heading_path=[title],
                ordinal=1,
                citation=Citation(source_id=source.id, asset_id=asset.id, file_path=path, page=1),
            )
        ]
        SourceRepository(self.workspace_db).add(source)
        AssetRepository(self.workspace_db).add(asset)
        KnowledgeRepository(self.workspace_db).add(item)
        ChunkRepository(self.workspace_db).add_many(chunks)

    def create_case(self, *, idempotency_key: str = "idem_create_case") -> tuple[str, str]:
        response = self.case_commands.create_case(
            CreateResearchCaseRequest(
                title="Hidden intention",
                question_text="How should hidden intention be evaluated?",
                question_role=QuestionRole.root,
            ),
            context=context(f"cmd_create_case_{idempotency_key}", idempotency_key=idempotency_key),
        )
        data = response.response_body["data"]
        return (
            str(data["research_case"]["research_case_id"]),
            str(data["research_question"]["research_question_id"]),
        )

    def resolve(
        self,
        case_id: str,
        question_id: str,
        anchors: list[SourceAnchorInput],
        *,
        expected_revision: int,
        command_id: str = "cmd_resolve",
        idempotency_key: str = "idem_resolve",
    ) -> list[dict]:
        response = self.scope_commands.create_source_resolutions(
            case_id,
            CreateSourceResolutionsRequest(
                expected_revision=expected_revision,
                research_question_id=question_id,
                resolution_stage="full",
                anchors=anchors,
            ),
            context=context(command_id, idempotency_key=idempotency_key),
        )
        self.assertEqual(response.status_code, 201)
        return list(response.response_body["data"]["source_resolutions"])

    def direct_requirement(self, binding_id: str) -> EvidenceRequirementInput:
        return EvidenceRequirementInput(
            requirement_type=code("direct_support"),
            description="Find direct evidence.",
            required_knowledge_scope_source_binding_ids=[binding_id],
            counterevidence_required=True,
            alternative_interpretation_required=False,
            completion_condition="Required source has a terminal result.",
            minimum_count=1,
        )

    def test_source_resolution_title_alias_ambiguous_not_found_unavailable_and_excluded(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子", aliases=["捭阖"])
        self.add_catalog_item(item_id="ki_alias", title="别名书", aliases=["共同别名"])
        self.add_catalog_item(item_id="ki_alias_2", title="别名书二", aliases=["共同别名"])
        self.add_catalog_item(item_id="ki_missing_file", title="缺失版本", missing_file=True)
        case_id, question_id = self.create_case()

        results = self.resolve(
            case_id,
            question_id,
            [
                SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required"),
                SourceAnchorInput(raw_anchor="捭阖", requested_access_policy="allowed"),
                SourceAnchorInput(raw_anchor="共同别名", requested_access_policy="required"),
                SourceAnchorInput(raw_anchor="不存在", requested_access_policy="required"),
                SourceAnchorInput(raw_anchor="缺失版本", requested_access_policy="required"),
                SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="excluded"),
            ],
            expected_revision=1,
        )

        by_anchor_policy = {
            (result["raw_anchor"], result["requested_access_policy"]): result
            for result in results
        }
        exact = by_anchor_policy[("鬼谷子", "required")]
        self.assertEqual(exact["resolution_status"], "resolved")
        self.assertEqual(exact["resolved_knowledge_item_id"], "ki_guiguzi")
        self.assertIsNotNone(exact["resolved_knowledge_item_version_id"])

        alias = by_anchor_policy[("捭阖", "allowed")]
        self.assertEqual(alias["resolution_status"], "resolved")
        self.assertEqual(alias["resolved_knowledge_item_id"], "ki_guiguzi")

        ambiguous = by_anchor_policy[("共同别名", "required")]
        self.assertEqual(ambiguous["resolution_status"], "ambiguous")
        self.assertEqual(ambiguous["candidate_knowledge_item_ids"], ["ki_alias", "ki_alias_2"])

        not_found = by_anchor_policy[("不存在", "required")]
        self.assertEqual(not_found["resolution_status"], "not_found")
        self.assertIsNotNone(not_found["failure_reason"])

        unavailable = by_anchor_policy[("缺失版本", "required")]
        self.assertEqual(unavailable["resolution_status"], "unavailable")
        self.assertEqual(unavailable["candidate_knowledge_item_ids"], ["ki_missing_file"])

        excluded = by_anchor_policy[("鬼谷子", "excluded")]
        self.assertEqual(excluded["resolution_status"], "resolved")
        self.assertEqual(excluded["resolved_knowledge_item_id"], "ki_guiguzi")
        self.assertIsNone(excluded["resolved_knowledge_item_version_id"])

    def test_source_resolution_idempotent_replay_does_not_duplicate_records_or_events(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子")
        case_id, question_id = self.create_case()
        request = CreateSourceResolutionsRequest(
            expected_revision=1,
            research_question_id=question_id,
            resolution_stage="full",
            anchors=[SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required")],
        )

        first = self.scope_commands.create_source_resolutions(
            case_id,
            request,
            context=context("cmd_resolve_1", idempotency_key="idem_resolve_once"),
        )
        replay = self.scope_commands.create_source_resolutions(
            case_id,
            request,
            context=context("cmd_resolve_2", idempotency_key="idem_resolve_once"),
        )

        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])
        self.assertEqual(len(self.scope_queries.list_source_resolutions(question_id)), 1)
        with UnitOfWork(self.core_db, write=False) as uow:
            events = uow.events.list_for_aggregate("research_case", case_id)
            self.assertEqual(
                [event.event_type_code for event in events],
                ["research_case_created", "source_resolutions_created"],
            )

    def test_create_and_adjust_knowledge_scope_validate_resolution_bindings(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子")
        self.add_catalog_item(item_id="ki_plato", title="理想国")
        case_id, question_id = self.create_case()
        resolutions = self.resolve(
            case_id,
            question_id,
            [
                SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required"),
                SourceAnchorInput(raw_anchor="理想国", requested_access_policy="excluded"),
            ],
            expected_revision=1,
        )
        required = next(result for result in resolutions if result["requested_access_policy"] == "required")
        excluded = next(result for result in resolutions if result["requested_access_policy"] == "excluded")

        create = self.scope_commands.create_knowledge_scope(
            case_id,
            CreateKnowledgeScopeRequest(
                expected_revision=2,
                default_access_policy=AccessPolicy.excluded,
                scope_mode=ScopeMode.evidence_only,
                bindings=[
                    KnowledgeScopeBindingInput(
                        source_resolution_id=required["source_resolution_id"],
                        knowledge_item_id=required["resolved_knowledge_item_id"],
                        knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                        access_policy=AccessPolicy.required,
                        analysis_role=AnalysisRole.primary,
                    ),
                    KnowledgeScopeBindingInput(
                        source_resolution_id=excluded["source_resolution_id"],
                        knowledge_item_id=excluded["resolved_knowledge_item_id"],
                        knowledge_item_version_id=None,
                        access_policy=AccessPolicy.excluded,
                        analysis_role=None,
                    ),
                ],
            ),
            context=context("cmd_scope_create", idempotency_key="idem_scope_create"),
        )
        self.assertEqual(create.status_code, 201)
        scope = create.response_body["data"]["knowledge_scope"]
        self.assertEqual(scope["version"], 1)
        self.assertEqual(scope["source_bindings"][0]["access_policy"], "required")
        self.assertEqual(scope["source_bindings"][1]["access_policy"], "excluded")
        self.assertEqual(self.scope_queries.get_current_knowledge_scope_for_case(case_id).version, 1)

        adjusted = self.scope_commands.adjust_knowledge_scope(
            scope["knowledge_scope_version_id"],
            AdjustKnowledgeScopeRequest(
                expected_revision=3,
                default_access_policy=AccessPolicy.allowed,
                scope_mode=ScopeMode.evidence_only,
                bindings=[
                    KnowledgeScopeBindingInput(
                        source_resolution_id=required["source_resolution_id"],
                        knowledge_item_id=required["resolved_knowledge_item_id"],
                        knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                        access_policy=AccessPolicy.required,
                        analysis_role=AnalysisRole.comparison,
                    )
                ],
            ),
            context=context("cmd_scope_adjust", idempotency_key="idem_scope_adjust"),
        )
        new_scope = adjusted.response_body["data"]["knowledge_scope"]
        self.assertEqual(new_scope["version"], 2)
        self.assertEqual(
            adjusted.response_body["data"]["superseded_version_ref"]["resource_id"],
            scope["knowledge_scope_version_id"],
        )
        old_scope = self.scope_queries.get_knowledge_scope_version(scope["knowledge_scope_version_id"])
        self.assertEqual(old_scope.lifecycle_status.value, "superseded")

        with self.assertRaises(ConcurrencyConflictError):
            self.scope_commands.adjust_knowledge_scope(
                new_scope["knowledge_scope_version_id"],
                AdjustKnowledgeScopeRequest(
                    expected_revision=3,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=required["source_resolution_id"],
                            knowledge_item_id=required["resolved_knowledge_item_id"],
                            knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_stale", idempotency_key="idem_scope_stale"),
            )

        with self.assertRaises(ValueError):
            self.scope_commands.create_knowledge_scope(
                case_id,
                CreateKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=required["source_resolution_id"],
                            knowledge_item_id="ki_wrong",
                            knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_bad", idempotency_key="idem_scope_bad"),
            )
        with self.assertRaises(ValueError):
            self.scope_commands.create_knowledge_scope(
                case_id,
                CreateKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=required["source_resolution_id"],
                            knowledge_item_id=required["resolved_knowledge_item_id"],
                            knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.allowed,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_bad_policy", idempotency_key="idem_scope_bad_policy"),
            )
        with self.assertRaises(ValueError):
            self.scope_commands.create_knowledge_scope(
                case_id,
                CreateKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=required["source_resolution_id"],
                            knowledge_item_id=required["resolved_knowledge_item_id"],
                            knowledge_item_version_id="kiv_wrong",
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_bad_version", idempotency_key="idem_scope_bad_version"),
            )
        with self.assertRaises(ConcurrencyConflictError):
            self.scope_commands.adjust_knowledge_scope(
                scope["knowledge_scope_version_id"],
                AdjustKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=required["source_resolution_id"],
                            knowledge_item_id=required["resolved_knowledge_item_id"],
                            knowledge_item_version_id=required["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_old_current", idempotency_key="idem_scope_old_current"),
            )

    def test_archived_case_rejects_scope_creation_or_adjustment(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子")
        case_id, question_id = self.create_case()
        resolution = self.resolve(
            case_id,
            question_id,
            [SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required")],
            expected_revision=1,
        )[0]
        scope_response = self.scope_commands.create_knowledge_scope(
            case_id,
            CreateKnowledgeScopeRequest(
                expected_revision=2,
                default_access_policy=AccessPolicy.excluded,
                scope_mode=ScopeMode.evidence_only,
                bindings=[
                    KnowledgeScopeBindingInput(
                        source_resolution_id=resolution["source_resolution_id"],
                        knowledge_item_id=resolution["resolved_knowledge_item_id"],
                        knowledge_item_version_id=resolution["resolved_knowledge_item_version_id"],
                        access_policy=AccessPolicy.required,
                        analysis_role=AnalysisRole.primary,
                    )
                ],
            ),
            context=context("cmd_scope_before_archive", idempotency_key="idem_scope_before_archive"),
        )
        scope = scope_response.response_body["data"]["knowledge_scope"]

        ResearchCaseCommandHandler(
            ApplicationCommandHandler(self.core_db),
            clock=self.clock,
        ).archive_case(
            case_id,
            expected_revision=3,
            context=context("cmd_archive_case", idempotency_key="idem_archive_case"),
        )
        with self.assertRaises(ValueError):
            self.scope_commands.create_knowledge_scope(
                case_id,
                CreateKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=resolution["source_resolution_id"],
                            knowledge_item_id=resolution["resolved_knowledge_item_id"],
                            knowledge_item_version_id=resolution["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_archived", idempotency_key="idem_scope_archived"),
            )
        with self.assertRaises(ValueError):
            self.scope_commands.adjust_knowledge_scope(
                scope["knowledge_scope_version_id"],
                AdjustKnowledgeScopeRequest(
                    expected_revision=4,
                    default_access_policy=AccessPolicy.excluded,
                    scope_mode=ScopeMode.evidence_only,
                    bindings=[
                        KnowledgeScopeBindingInput(
                            source_resolution_id=resolution["source_resolution_id"],
                            knowledge_item_id=resolution["resolved_knowledge_item_id"],
                            knowledge_item_version_id=resolution["resolved_knowledge_item_version_id"],
                            access_policy=AccessPolicy.required,
                            analysis_role=AnalysisRole.primary,
                        )
                    ],
                ),
                context=context("cmd_scope_adjust_archived", idempotency_key="idem_scope_adjust_archived"),
            )

    def test_create_and_adjust_research_plan_validate_binding_ids_and_scope_case(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子")
        self.add_catalog_item(item_id="ki_plato", title="理想国")
        case_id, question_id = self.create_case()
        resolution = self.resolve(
            case_id,
            question_id,
            [SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required")],
            expected_revision=1,
        )[0]
        scope_response = self.scope_commands.create_knowledge_scope(
            case_id,
            CreateKnowledgeScopeRequest(
                expected_revision=2,
                default_access_policy=AccessPolicy.excluded,
                scope_mode=ScopeMode.evidence_only,
                bindings=[
                    KnowledgeScopeBindingInput(
                        source_resolution_id=resolution["source_resolution_id"],
                        knowledge_item_id=resolution["resolved_knowledge_item_id"],
                        knowledge_item_version_id=resolution["resolved_knowledge_item_version_id"],
                        access_policy=AccessPolicy.required,
                        analysis_role=AnalysisRole.primary,
                    )
                ],
            ),
            context=context("cmd_scope_create_plan", idempotency_key="idem_scope_create_plan"),
        )
        scope = scope_response.response_body["data"]["knowledge_scope"]
        binding_id = scope["source_bindings"][0]["knowledge_scope_source_binding_id"]

        plan_response = self.scope_commands.create_research_plan(
            case_id,
            CreateResearchPlanRequest(
                expected_revision=3,
                knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                research_mode=ResearchMode.claim_evaluation,
                primary_objective="Evaluate the claim with bounded evidence.",
                evidence_requirements=[self.direct_requirement(binding_id)],
                minimum_completion_condition="All mandatory requirements terminal.",
            ),
            context=context("cmd_plan_create", idempotency_key="idem_plan_create"),
        )
        self.assertEqual(plan_response.status_code, 201)
        plan = plan_response.response_body["data"]["research_plan"]
        self.assertEqual(plan["version"], 1)
        self.assertEqual(plan["evidence_requirements"][0]["required_knowledge_scope_source_binding_ids"], [binding_id])

        adjusted = self.scope_commands.adjust_research_plan(
            plan["research_plan_version_id"],
            AdjustResearchPlanRequest(
                expected_revision=4,
                knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                research_mode=ResearchMode.fact_lookup,
                primary_objective="Find direct facts only.",
                evidence_requirements=[self.direct_requirement(binding_id)],
                minimum_completion_condition="Direct evidence found or required source terminal.",
            ),
            context=context("cmd_plan_adjust", idempotency_key="idem_plan_adjust"),
        )
        new_plan = adjusted.response_body["data"]["research_plan"]
        self.assertEqual(new_plan["version"], 2)
        old_plan = self.scope_queries.get_research_plan_version(plan["research_plan_version_id"])
        self.assertEqual(old_plan.lifecycle_status.value, "superseded")

        with self.assertRaises(ConcurrencyConflictError):
            self.scope_commands.adjust_research_plan(
                new_plan["research_plan_version_id"],
                AdjustResearchPlanRequest(
                    expected_revision=4,
                    knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                    research_mode=ResearchMode.fact_lookup,
                    primary_objective="Stale plan.",
                    evidence_requirements=[self.direct_requirement(binding_id)],
                    minimum_completion_condition="No stale writes.",
                ),
                context=context("cmd_plan_stale", idempotency_key="idem_plan_stale"),
            )

        with self.assertRaises(ValueError):
            self.scope_commands.create_research_plan(
                case_id,
                CreateResearchPlanRequest(
                    expected_revision=5,
                    knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                    research_mode=ResearchMode.claim_evaluation,
                    primary_objective="Invalid binding reference.",
                    evidence_requirements=[self.direct_requirement("missing_binding")],
                    minimum_completion_condition="Should fail.",
                ),
                context=context("cmd_plan_bad_binding", idempotency_key="idem_plan_bad_binding"),
            )
        with self.assertRaises(ConcurrencyConflictError):
            self.scope_commands.adjust_research_plan(
                plan["research_plan_version_id"],
                AdjustResearchPlanRequest(
                    expected_revision=5,
                    knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                    research_mode=ResearchMode.fact_lookup,
                    primary_objective="Old current version cannot be adjusted.",
                    evidence_requirements=[self.direct_requirement(binding_id)],
                    minimum_completion_condition="Should fail.",
                ),
                context=context("cmd_plan_old_current", idempotency_key="idem_plan_old_current"),
            )

    def test_plan_cannot_reference_scope_from_another_case(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="鬼谷子")
        first_case, first_question = self.create_case()
        first_resolution = self.resolve(
            first_case,
            first_question,
            [SourceAnchorInput(raw_anchor="鬼谷子", requested_access_policy="required")],
            expected_revision=1,
            command_id="cmd_resolve_first",
            idempotency_key="idem_resolve_first",
        )[0]
        first_scope = self.scope_commands.create_knowledge_scope(
            first_case,
            CreateKnowledgeScopeRequest(
                expected_revision=2,
                default_access_policy=AccessPolicy.excluded,
                scope_mode=ScopeMode.evidence_only,
                bindings=[
                    KnowledgeScopeBindingInput(
                        source_resolution_id=first_resolution["source_resolution_id"],
                        knowledge_item_id=first_resolution["resolved_knowledge_item_id"],
                        knowledge_item_version_id=first_resolution["resolved_knowledge_item_version_id"],
                        access_policy=AccessPolicy.required,
                        analysis_role=AnalysisRole.primary,
                    )
                ],
            ),
            context=context("cmd_scope_first", idempotency_key="idem_scope_first"),
        ).response_body["data"]["knowledge_scope"]
        binding_id = first_scope["source_bindings"][0]["knowledge_scope_source_binding_id"]

        second_case, _second_question = self.create_case(idempotency_key="idem_create_second_case")
        with self.assertRaises(ValueError):
            self.scope_commands.create_research_plan(
                second_case,
                CreateResearchPlanRequest(
                    expected_revision=1,
                    knowledge_scope_version_id=first_scope["knowledge_scope_version_id"],
                    research_mode=ResearchMode.claim_evaluation,
                    primary_objective="Cross-case scope must fail.",
                    evidence_requirements=[self.direct_requirement(binding_id)],
                    minimum_completion_condition="Should fail.",
                ),
                context=context("cmd_plan_cross_case", idempotency_key="idem_plan_cross_case"),
            )


if __name__ == "__main__":
    unittest.main()
