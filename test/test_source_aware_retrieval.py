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
from metaos.core_alpha.contracts.execution import (
    CreateResearchRunRequest,
    ExecutionMode,
    ResearchAttemptMode,
)
from metaos.core_alpha.contracts.scope import (
    AccessPolicy,
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
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
from metaos.core_alpha.research_execution import ResearchExecutionCommandHandler
from metaos.core_alpha.scope_governance import ScopeGovernanceCommandHandler
from metaos.core_alpha.source_aware_retrieval import (
    ExecuteResearchPlanRetrievalRequest,
    ReuseExistingEvidenceRequest,
    SourceAwareRetrievalOrchestrator,
)
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.workspace.catalog import (
    AssetRepository,
    ChunkRepository,
    KnowledgeRepository,
    SourceRepository,
)


NOW = datetime(2026, 6, 25, 11, 0, tzinfo=timezone.utc)


def code(value: str) -> OpenCodeValue:
    return OpenCodeValue(code=value, registry_version="core-alpha-v1")


def context(command_id: str, *, idempotency_key: str) -> CommandContext:
    return CommandContext(
        command_id=command_id,
        actor_type=code("user"),
        actor_id="user_1",
        idempotency_key=idempotency_key,
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FixedClock:
    def __init__(self) -> None:
        self.offset = 0

    def __call__(self) -> datetime:
        value = NOW + timedelta(minutes=self.offset)
        self.offset += 1
        return value


class SourceAwareRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.workspace_db = self.root / "workspace.sqlite3"
        self.clock = FixedClock()
        app_handler = ApplicationCommandHandler(self.core_db)
        catalog = KnowledgeCatalogAdapter(self.workspace_db)
        self.case_commands = ResearchCaseCommandHandler(app_handler, clock=self.clock)
        self.scope_commands = ScopeGovernanceCommandHandler(
            app_handler,
            catalog,
            clock=self.clock,
        )
        self.execution_commands = ResearchExecutionCommandHandler(
            app_handler,
            clock=self.clock,
        )
        self.retrieval = SourceAwareRetrievalOrchestrator(
            app_handler,
            catalog,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def add_catalog_item(
        self,
        *,
        item_id: str,
        title: str,
        chunk_texts: list[str],
        aliases: list[str] | None = None,
    ) -> None:
        path = self.root / f"{item_id}.md"
        path.write_text("\n\n".join(chunk_texts), encoding="utf-8")
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
                    excerpt=chunk_texts[0],
                )
            ],
            metadata={
                "source_id": source.id,
                "asset_id": asset.id,
                "language": "en",
                "parser": "markdown-v1",
                "chunker": "test-chunker-v1",
                "index_version": "test-index-v1",
            },
        )
        chunks = [
            Chunk(
                id=f"chunk_{item_id}_{index + 1}",
                knowledge_item_id=item.id,
                text=text,
                heading_path=[title, f"Part {index + 1}"],
                ordinal=index + 1,
                citation=Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=path,
                    page=index + 1,
                ),
            )
            for index, text in enumerate(chunk_texts)
        ]
        SourceRepository(self.workspace_db).add(source)
        AssetRepository(self.workspace_db).add(asset)
        KnowledgeRepository(self.workspace_db).add(item)
        ChunkRepository(self.workspace_db).add_many(chunks)

    def create_case_scope_plan(
        self,
        anchors: list[SourceAnchorInput],
        *,
        binding_roles: dict[str, AnalysisRole],
        research_mode: ResearchMode = ResearchMode.claim_evaluation,
        key_suffix: str = "main",
    ) -> tuple[str, str, str, str, str, list[dict]]:
        case_response = self.case_commands.create_case(
            CreateResearchCaseRequest(
                title=f"Source aware case {key_suffix}",
                question_text="Evaluate hidden intention with bounded sources.",
                question_role=QuestionRole.root,
            ),
            context=context(
                f"cmd_case_{key_suffix}",
                idempotency_key=f"idem_case_{key_suffix}",
            ),
        )
        case_data = case_response.response_body["data"]
        case_id = str(case_data["research_case"]["research_case_id"])
        question_id = str(case_data["research_question"]["research_question_id"])

        resolution_response = self.scope_commands.create_source_resolutions(
            case_id,
            CreateSourceResolutionsRequest(
                expected_revision=1,
                research_question_id=question_id,
                resolution_stage="full",
                anchors=anchors,
            ),
            context=context(
                f"cmd_resolution_{key_suffix}",
                idempotency_key=f"idem_resolution_{key_suffix}",
            ),
        )
        resolutions = list(resolution_response.response_body["data"]["source_resolutions"])
        bindings: list[KnowledgeScopeBindingInput] = []
        for resolution in resolutions:
            access_policy = AccessPolicy(resolution["requested_access_policy"])
            item_id = str(resolution["resolved_knowledge_item_id"])
            role = None if access_policy == AccessPolicy.excluded else binding_roles[item_id]
            bindings.append(
                KnowledgeScopeBindingInput(
                    source_resolution_id=resolution["source_resolution_id"],
                    knowledge_item_id=item_id,
                    knowledge_item_version_id=resolution["resolved_knowledge_item_version_id"],
                    access_policy=access_policy,
                    analysis_role=role,
                )
            )

        scope_response = self.scope_commands.create_knowledge_scope(
            case_id,
            CreateKnowledgeScopeRequest(
                expected_revision=2,
                default_access_policy=AccessPolicy.excluded,
                scope_mode=ScopeMode.evidence_only,
                bindings=bindings,
            ),
            context=context(
                f"cmd_scope_{key_suffix}",
                idempotency_key=f"idem_scope_{key_suffix}",
            ),
        )
        scope = scope_response.response_body["data"]["knowledge_scope"]
        requirement_binding_ids = [
            binding["knowledge_scope_source_binding_id"]
            for binding in scope["source_bindings"]
            if binding["access_policy"] == "required"
        ]
        plan_response = self.scope_commands.create_research_plan(
            case_id,
            CreateResearchPlanRequest(
                expected_revision=3,
                knowledge_scope_version_id=scope["knowledge_scope_version_id"],
                research_mode=research_mode,
                primary_objective="Find evidence for hidden intention.",
                evidence_requirements=[
                    EvidenceRequirementInput(
                        requirement_type=code("direct_support"),
                        description="Find source-local support.",
                        required_knowledge_scope_source_binding_ids=requirement_binding_ids,
                        counterevidence_required=True,
                        alternative_interpretation_required=False,
                        completion_condition="Required sources reach terminal state.",
                        minimum_count=1,
                    )
                ],
                minimum_completion_condition="Every required source is terminal.",
            ),
            context=context(
                f"cmd_plan_{key_suffix}",
                idempotency_key=f"idem_plan_{key_suffix}",
            ),
        )
        plan = plan_response.response_body["data"]["research_plan"]
        return (
            case_id,
            question_id,
            scope["knowledge_scope_version_id"],
            plan["research_plan_version_id"],
            str(scope["source_bindings"][0]["knowledge_scope_source_binding_id"]),
            list(scope["source_bindings"]),
        )

    def start_run(
        self,
        *,
        case_id: str,
        question_id: str,
        scope_id: str,
        plan_id: str,
        key_suffix: str,
        initial_attempt_mode: ResearchAttemptMode = ResearchAttemptMode.retrieval,
    ) -> tuple[str, str]:
        response = self.execution_commands.start_research_run(
            case_id,
            CreateResearchRunRequest(
                expected_research_case_revision=4,
                research_question_id=question_id,
                knowledge_scope_version_id=scope_id,
                research_plan_version_id=plan_id,
                execution_mode=ExecutionMode.synchronous,
            ),
            context=context(
                f"cmd_start_run_{key_suffix}",
                idempotency_key=f"idem_start_run_{key_suffix}",
            ),
            initial_attempt_mode=initial_attempt_mode,
        )
        data = response.response_body["data"]
        return (
            str(data["research_run"]["research_run_id"]),
            str(data["research_attempt"]["research_attempt_id"]),
        )

    def test_required_sources_are_independent_and_excluded_source_is_clean(self) -> None:
        short_chunks = [
            f"Short source neutral paragraph {index}."
            for index in range(15)
        ]
        short_chunks[7] = "Short source says hidden intention must be tested by indirect signs."
        long_chunks = [
            f"Long source neutral paragraph {index}."
            for index in range(399)
        ]
        long_chunks[250] = "Long source records hidden intention through public speech and private signs."
        excluded_chunks = [
            "Excluded source contains hidden intention material that must not be cited."
        ]
        self.add_catalog_item(item_id="ki_short", title="Short Book", chunk_texts=short_chunks)
        self.add_catalog_item(item_id="ki_long", title="Long Book", chunk_texts=long_chunks)
        self.add_catalog_item(item_id="ki_excluded", title="Excluded Book", chunk_texts=excluded_chunks)
        case_id, question_id, scope_id, plan_id, _binding_id, bindings = self.create_case_scope_plan(
            [
                SourceAnchorInput(raw_anchor="Short Book", requested_access_policy=AccessPolicy.required),
                SourceAnchorInput(raw_anchor="Long Book", requested_access_policy=AccessPolicy.required),
                SourceAnchorInput(raw_anchor="Excluded Book", requested_access_policy=AccessPolicy.excluded),
            ],
            binding_roles={
                "ki_short": AnalysisRole.primary,
                "ki_long": AnalysisRole.comparison,
            },
        )
        run_id, attempt_id = self.start_run(
            case_id=case_id,
            question_id=question_id,
            scope_id=scope_id,
            plan_id=plan_id,
            key_suffix="independent",
        )

        response = self.retrieval.execute_research_plan(
            run_id,
            ExecuteResearchPlanRetrievalRequest(
                research_attempt_id=attempt_id,
                evidence_query="hidden intention",
            ),
            context=context("cmd_retrieval_independent", idempotency_key="idem_retrieval_independent"),
        )

        data = response.response_body["data"]
        reports = {report["knowledge_item_id"]: report for report in data["source_reports"]}
        self.assertEqual(reports["ki_short"]["terminal_status"], "evidence_found")
        self.assertTrue(reports["ki_short"]["full_scan_eligible"])
        self.assertEqual(reports["ki_short"]["active_chunk_count"], 15)
        self.assertEqual(reports["ki_long"]["terminal_status"], "evidence_found")
        self.assertFalse(reports["ki_long"]["full_scan_eligible"])
        self.assertEqual(reports["ki_excluded"]["terminal_status"], "excluded")
        self.assertIsNone(reports["ki_excluded"]["retrieval_run_id"])

        retrieval_binding_ids = {
            retrieval["knowledge_scope_source_binding_id"]
            for retrieval in data["retrieval_runs"]
        }
        excluded_binding_id = next(
            binding["knowledge_scope_source_binding_id"]
            for binding in bindings
            if binding["knowledge_item_id"] == "ki_excluded"
        )
        self.assertNotIn(excluded_binding_id, retrieval_binding_ids)

        evidence_item_ids = {unit["knowledge_item_id"] for unit in data["evidence_units"]}
        self.assertIn("ki_short", evidence_item_ids)
        self.assertIn("ki_long", evidence_item_ids)
        self.assertNotIn("ki_excluded", evidence_item_ids)
        self.assertLessEqual(len(data["context_pack"]["evidence_use_ids"]), 20)

    def test_required_source_without_candidate_reports_no_evidence(self) -> None:
        self.add_catalog_item(
            item_id="ki_plain",
            title="Plain Book",
            chunk_texts=["This source discusses unrelated material."],
        )
        case_id, question_id, scope_id, plan_id, _binding_id, _bindings = self.create_case_scope_plan(
            [SourceAnchorInput(raw_anchor="Plain Book", requested_access_policy=AccessPolicy.required)],
            binding_roles={"ki_plain": AnalysisRole.primary},
            key_suffix="no_evidence",
        )
        run_id, attempt_id = self.start_run(
            case_id=case_id,
            question_id=question_id,
            scope_id=scope_id,
            plan_id=plan_id,
            key_suffix="no_evidence",
        )

        response = self.retrieval.execute_research_plan(
            run_id,
            ExecuteResearchPlanRetrievalRequest(
                research_attempt_id=attempt_id,
                evidence_query="hidden intention",
            ),
            context=context("cmd_retrieval_no_evidence", idempotency_key="idem_retrieval_no_evidence"),
        )

        data = response.response_body["data"]
        self.assertEqual(data["source_reports"][0]["terminal_status"], "no_evidence")
        self.assertEqual(data["retrieval_runs"][0]["retrieval_outcome"], "no_evidence")
        self.assertEqual(data["evidence_units"], [])
        self.assertEqual(data["research_evidence_uses"], [])

    def test_execute_research_plan_is_idempotent(self) -> None:
        self.add_catalog_item(
            item_id="ki_once",
            title="Once Book",
            chunk_texts=["This chunk contains hidden intention evidence."],
        )
        case_id, question_id, scope_id, plan_id, _binding_id, _bindings = self.create_case_scope_plan(
            [SourceAnchorInput(raw_anchor="Once Book", requested_access_policy=AccessPolicy.required)],
            binding_roles={"ki_once": AnalysisRole.primary},
            key_suffix="idempotent",
        )
        run_id, attempt_id = self.start_run(
            case_id=case_id,
            question_id=question_id,
            scope_id=scope_id,
            plan_id=plan_id,
            key_suffix="idempotent",
        )
        request = ExecuteResearchPlanRetrievalRequest(
            research_attempt_id=attempt_id,
            evidence_query="hidden intention",
        )

        first = self.retrieval.execute_research_plan(
            run_id,
            request,
            context=context("cmd_retrieval_once_1", idempotency_key="idem_retrieval_once"),
        )
        replay = self.retrieval.execute_research_plan(
            run_id,
            request,
            context=context("cmd_retrieval_once_2", idempotency_key="idem_retrieval_once"),
        )

        self.assertFalse(first.response_body["command"]["idempotent_replay"])
        self.assertTrue(replay.response_body["command"]["idempotent_replay"])
        self.assertEqual(first.response_body["data"], replay.response_body["data"])
        with UnitOfWork(self.core_db, write=False) as uow:
            self.assertEqual(len(uow.run_evidence.list_retrieval_runs(attempt_id)), 1)
            self.assertEqual(len(uow.run_evidence.list_research_evidence_uses(run_id)), 1)

    def test_reuse_existing_evidence_creates_use_without_retrieval_run(self) -> None:
        self.add_catalog_item(
            item_id="ki_reuse",
            title="Reuse Book",
            chunk_texts=["Reusable hidden intention evidence is present."],
        )
        case_id, question_id, scope_id, plan_id, _binding_id, _bindings = self.create_case_scope_plan(
            [SourceAnchorInput(raw_anchor="Reuse Book", requested_access_policy=AccessPolicy.required)],
            binding_roles={"ki_reuse": AnalysisRole.primary},
            key_suffix="reuse",
        )
        first_run_id, first_attempt_id = self.start_run(
            case_id=case_id,
            question_id=question_id,
            scope_id=scope_id,
            plan_id=plan_id,
            key_suffix="reuse_first",
        )
        first = self.retrieval.execute_research_plan(
            first_run_id,
            ExecuteResearchPlanRetrievalRequest(
                research_attempt_id=first_attempt_id,
                evidence_query="hidden intention",
            ),
            context=context("cmd_retrieval_reuse_first", idempotency_key="idem_retrieval_reuse_first"),
        )
        evidence_id = first.response_body["data"]["evidence_units"][0]["evidence_unit_id"]
        second_run_id, second_attempt_id = self.start_run(
            case_id=case_id,
            question_id=question_id,
            scope_id=scope_id,
            plan_id=plan_id,
            key_suffix="reuse_second",
            initial_attempt_mode=ResearchAttemptMode.reuse_existing_evidence,
        )

        reuse = self.retrieval.reuse_existing_evidence(
            second_run_id,
            ReuseExistingEvidenceRequest(
                research_attempt_id=second_attempt_id,
                evidence_unit_ids=[evidence_id],
            ),
            context=context("cmd_reuse_existing", idempotency_key="idem_reuse_existing"),
        )

        data = reuse.response_body["data"]
        self.assertEqual(data["retrieval_runs"], [])
        self.assertEqual(data["research_evidence_uses"][0]["use_type"], "reused")
        self.assertIsNone(data["research_evidence_uses"][0]["retrieval_run_id"])
        with UnitOfWork(self.core_db, write=False) as uow:
            self.assertEqual(uow.run_evidence.list_retrieval_runs(second_attempt_id), [])
            uses = uow.run_evidence.list_research_evidence_uses(second_run_id)
            self.assertEqual(len(uses), 1)
            self.assertEqual(uses[0].use_type.value, "reused")


if __name__ == "__main__":
    unittest.main()
