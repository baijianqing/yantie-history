from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

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
from metaos.core_alpha.api import DeveloperExtensionRegistry, create_core_alpha_app
from metaos.core_alpha.commands import StaticFeatureFlagRegistry
from metaos.core_alpha.diagnostics import register_diagnostics_developer_routes
from metaos.core_alpha.egress import DataEgressGuard, OutboundDataPolicy
from metaos.core_alpha.persistence import CoreAlphaDatabase, TraceEventRecord, UnitOfWork
from metaos.core_alpha.persistence.repositories import _canonical_json, _payload_hash
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.workspace.catalog import (
    AssetRepository,
    ChunkRepository,
    KnowledgeRepository,
    SourceRepository,
)
from test_core_alpha_openapi import context as feature_context
from test_data_egress import (
    NOW,
    RecordingProvider,
    case_response,
    context,
    execution_spec,
    invocation,
    plan_response,
    question_response,
    run_response,
    scope_response,
    source_resolution,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CoreAlphaDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.workspace_db = self.root / "workspace.sqlite3"
        self.catalog = KnowledgeCatalogAdapter(self.workspace_db)
        self.flags = StaticFeatureFlagRegistry.core_alpha_defaults()
        with UnitOfWork(self.core_db) as uow:
            self.flags.set_override(
                uow=uow,
                context=feature_context(),
                flag_key="core_alpha.developer_diagnostics",
                enabled=True,
                reason="Enable diagnostics routes in test.",
                occurred_at=NOW,
            )
        self.registry = DeveloperExtensionRegistry()
        register_diagnostics_developer_routes(
            self.registry,
            database=self.core_db,
            catalog=self.catalog,
        )
        self.client = TestClient(
            create_core_alpha_app(
                database=self.core_db,
                catalog=self.catalog,
                feature_flags=self.flags,
                developer_extensions=self.registry,
            )
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def seed_case_scope_run(self) -> None:
        with UnitOfWork(self.core_db) as uow:
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
                updated_at=NOW,
            )
            uow.case_scope.create_knowledge_scope(
                scope_response(),
                expected_case_revision=2,
                updated_at=NOW,
            )
            uow.case_scope.create_research_plan(
                plan_response(),
                expected_case_revision=3,
                updated_at=NOW,
            )
            uow.run_evidence.create_research_run(
                research_run=run_response(),
                execution_spec=execution_spec(),
            )
            event_payload = {"research_run_id": "run_1", "debug_payload": "not returned"}
            event_json = _canonical_json(event_payload)
            uow.events.append(
                TraceEventRecord(
                    event_id="event_run_started",
                    event_key="cmd_run_started:research_run_started",
                    event_type_code="research_run_started",
                    event_type_registry_version="core-alpha-v1",
                    aggregate_type="research_run",
                    aggregate_id="run_1",
                    aggregate_revision=1,
                    actor_type_code="user",
                    actor_type_registry_version="core-alpha-v1",
                    actor_id="user_1",
                    correlation_id="corr_1",
                    causation_id="cause_1",
                    trace_id="trace_1",
                    payload_hash=_payload_hash(event_json),
                    payload=event_payload,
                    occurred_at=NOW,
                )
            )

    def seed_material_manifest(self) -> None:
        guard = DataEgressGuard(
            self.core_db,
            OutboundDataPolicy(
                allowed_providers=["local-llm"],
                allowed_sensitive_levels=["public", "internal"],
                allow_full_material_content=False,
                allow_redacted_preview_storage=False,
            ),
        )
        guard.invoke(
            invocation(),
            context=context("cmd_diagnostics_manifest"),
            provider=RecordingProvider(),
        )

    def add_catalog_item(self) -> str:
        path = self.root / "guiguzi.md"
        path.write_text("# Guiguzi\n\nEvidence one.", encoding="utf-8")
        source = Source(
            id="src_guiguzi",
            type=SourceType.local_file,
            uri=path.as_uri(),
            title="Guiguzi",
        )
        asset = Asset(
            id="asset_guiguzi",
            source_id=source.id,
            kind=AssetKind.markdown,
            path=path,
            mime_type="text/markdown",
            sha256=_sha256(path),
            size_bytes=path.stat().st_size,
        )
        item = KnowledgeItem(
            id="ki_guiguzi",
            title="Guiguzi",
            summary="Guiguzi summary",
            category=KnowledgeCategory.philosophy,
            tags=["鬼谷子"],
            markdown_path=path,
            citations=[
                Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=path,
                    excerpt="Evidence one.",
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
        chunk = Chunk(
            id="chunk_guiguzi_1",
            knowledge_item_id=item.id,
            text="Guiguzi first evidence.",
            heading_path=["Guiguzi"],
            ordinal=1,
            citation=Citation(
                source_id=source.id,
                asset_id=asset.id,
                file_path=path,
                page=1,
            ),
        )
        SourceRepository(self.workspace_db).add(source)
        AssetRepository(self.workspace_db).add(asset)
        KnowledgeRepository(self.workspace_db).add(item)
        ChunkRepository(self.workspace_db).add_many([chunk])
        return self.catalog.get_current_version(item.id).knowledge_item_version_id

    def developer_get(self, url: str) -> object:
        return self.client.get(url, headers={"X-Developer-Actor-Id": "dev_1"})

    def test_developer_trace_requires_developer_identity_and_hides_event_payloads(self) -> None:
        self.seed_case_scope_run()

        missing_auth = self.client.get("/alpha/developer/research-runs/run_1/trace")
        self.assertEqual(missing_auth.status_code, 401)
        self.assertEqual(missing_auth.json()["error"]["code"], "authentication_required")

        response = self.developer_get("/alpha/developer/research-runs/run_1/trace")
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["research_trace"]["research_run"]["research_run_id"], "run_1")
        event = data["trace_events"][0]
        self.assertEqual(event["event_type"]["code"], "research_run_started")
        self.assertIn("payload_hash", event)
        self.assertNotIn("payload", event)
        self.assertNotIn("debug_payload", str(data))

    def test_material_manifest_query_returns_sanitized_records(self) -> None:
        self.seed_case_scope_run()
        self.seed_material_manifest()

        response = self.developer_get(
            "/alpha/developer/material-manifests?research_run_id=run_1&provider=local-llm"
        )
        self.assertEqual(response.status_code, 200)
        manifest = response.json()["data"][0]
        self.assertEqual(manifest["provider"], "local-llm")
        material = manifest["materials"][0]
        self.assertEqual(material["content_hash"], "sha256:aaaaaaaa")
        self.assertNotIn("content_text", material)
        self.assertIsNone(material["redacted_preview"])

    def test_index_generation_and_projection_status_routes(self) -> None:
        version_id = self.add_catalog_item()
        with UnitOfWork(self.core_db) as uow:
            uow.projection_checkpoints.put(
                projection_name="developer_trace",
                checkpoint="event_run_started",
                expected_revision=None,
                updated_at=NOW,
            )

        index_response = self.developer_get(
            f"/alpha/developer/index-generations?knowledge_item_version_id={version_id}"
        )
        self.assertEqual(index_response.status_code, 200)
        index_generation = index_response.json()["data"][0]
        self.assertEqual(index_generation["knowledge_item_version_id"], version_id)
        self.assertEqual(index_generation["status"], "ready")

        projection_response = self.developer_get("/alpha/developer/projections/status")
        self.assertEqual(projection_response.status_code, 200)
        projection = projection_response.json()["data"][0]
        self.assertEqual(projection["projection_name"], "developer_trace")
        self.assertEqual(projection["checkpoint"], "event_run_started")

    def test_minimum_slice_does_not_register_case_activity_or_budget_routes(self) -> None:
        self.assertEqual(
            self.developer_get("/alpha/developer/research-cases/case_1/activity").status_code,
            404,
        )
        self.assertEqual(
            self.developer_get("/alpha/developer/research-runs/run_1/budget").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
