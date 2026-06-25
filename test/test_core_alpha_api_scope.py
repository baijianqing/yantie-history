from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
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
from metaos.core_alpha.api_scope import create_scope_api_router
from metaos.core_alpha.persistence import CoreAlphaDatabase
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.workspace.catalog import (
    AssetRepository,
    ChunkRepository,
    KnowledgeRepository,
    SourceRepository,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CoreAlphaScopeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.workspace_db = self.root / "workspace.sqlite3"
        self.app = FastAPI()
        self.app.include_router(
            create_scope_api_router(
                database=self.core_db,
                catalog=KnowledgeCatalogAdapter(self.workspace_db),
            )
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def add_catalog_item(
        self,
        *,
        item_id: str,
        title: str,
        aliases: list[str] | None = None,
        content: str = "# Source\n\nEvidence one.\n\nEvidence two.",
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
            sha256=_sha256(path),
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
        chunks = [
            Chunk(
                id=f"chunk_{item_id}_1",
                knowledge_item_id=item.id,
                text=f"{title} first evidence.",
                heading_path=[title],
                ordinal=1,
                citation=Citation(
                    source_id=source.id,
                    asset_id=asset.id,
                    file_path=path,
                    page=1,
                ),
            )
        ]
        SourceRepository(self.workspace_db).add(source)
        AssetRepository(self.workspace_db).add(asset)
        KnowledgeRepository(self.workspace_db).add(item)
        ChunkRepository(self.workspace_db).add_many(chunks)

    def post(self, url: str, payload: dict, *, idem: str) -> TestClient:
        return self.client.post(
            url,
            json=payload,
            headers={
                "Idempotency-Key": idem,
                "X-Actor-Id": "user_1",
                "X-Trace-Id": f"trace_{idem}",
            },
        )

    def create_case(self) -> dict:
        response = self.post(
            "/alpha/research-cases",
            {
                "title": "Hidden intention",
                "question_text": "How should hidden intention be evaluated?",
                "question_role": "root",
            },
            idem="idem_case",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["data"]

    def test_knowledge_catalog_routes_return_identity_without_private_storage(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="Guiguzi", aliases=["Strategems"])

        items = self.client.get("/alpha/knowledge-items").json()
        self.assertEqual(items["data"][0]["knowledge_item_id"], "ki_guiguzi")
        self.assertEqual(items["data"][0]["item_type"]["code"], "document")

        item = self.client.get("/alpha/knowledge-items/ki_guiguzi").json()
        version_id = item["data"]["current_knowledge_item_version_id"]
        versions = self.client.get("/alpha/knowledge-items/ki_guiguzi/versions").json()
        self.assertEqual(versions["data"][0]["knowledge_item_version_id"], version_id)
        self.assertNotIn("storage_ref", versions["data"][0])

        chunks = self.client.get(f"/alpha/knowledge-item-versions/{version_id}/chunks").json()
        self.assertEqual(chunks["data"][0]["chunk_id"], "chunk_ki_guiguzi_1")
        self.assertIn("text_preview", chunks["data"][0])
        self.assertNotIn("text", chunks["data"][0])

    def test_research_case_commands_use_command_envelope_and_idempotency(self) -> None:
        data = self.create_case()
        case_id = data["research_case"]["research_case_id"]

        replay = self.post(
            "/alpha/research-cases",
            {
                "title": "Hidden intention",
                "question_text": "How should hidden intention be evaluated?",
                "question_role": "root",
            },
            idem="idem_case",
        )
        self.assertEqual(replay.status_code, 201)
        self.assertTrue(replay.json()["command"]["idempotent_replay"])

        fetched = self.client.get(f"/alpha/research-cases/{case_id}").json()
        self.assertEqual(fetched["data"]["revision"], 1)

        archived = self.post(
            f"/alpha/research-cases/{case_id}/commands/archive",
            {"expected_revision": 1},
            idem="idem_archive",
        )
        self.assertEqual(archived.status_code, 200)
        self.assertEqual(archived.json()["data"]["research_case"]["lifecycle_status"], "archived")

    def test_source_resolution_failure_is_successful_domain_record(self) -> None:
        case = self.create_case()
        research_case = case["research_case"]
        question = case["research_question"]

        response = self.post(
            f"/alpha/research-cases/{research_case['research_case_id']}/source-resolutions",
            {
                "expected_revision": research_case["revision"],
                "research_question_id": question["research_question_id"],
                "resolution_stage": "full",
                "anchors": [
                    {
                        "raw_anchor": "Unknown Source",
                        "requested_access_policy": "required",
                        "requested_version_hint": None,
                    }
                ],
            },
            idem="idem_resolve_missing",
        )
        self.assertEqual(response.status_code, 201)
        resolution = response.json()["data"]["source_resolutions"][0]
        self.assertEqual(resolution["resolution_status"], "not_found")

        listed = self.client.get(
            f"/alpha/research-cases/{research_case['research_case_id']}/source-resolutions"
        )
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["data"][0]["resolution_status"], "not_found")

    def test_scope_and_plan_version_routes_create_read_and_adjust(self) -> None:
        self.add_catalog_item(item_id="ki_guiguzi", title="Guiguzi", aliases=["Strategems"])
        case = self.create_case()
        research_case = case["research_case"]
        question = case["research_question"]

        resolved = self.post(
            f"/alpha/research-cases/{research_case['research_case_id']}/source-resolutions",
            {
                "expected_revision": 1,
                "research_question_id": question["research_question_id"],
                "resolution_stage": "full",
                "anchors": [
                    {
                        "raw_anchor": "Strategems",
                        "requested_access_policy": "required",
                        "requested_version_hint": None,
                    }
                ],
            },
            idem="idem_resolve_alias",
        ).json()["data"]["source_resolutions"][0]

        scope = self.post(
            f"/alpha/research-cases/{research_case['research_case_id']}/knowledge-scopes",
            {
                "expected_revision": 2,
                "default_access_policy": "excluded",
                "scope_mode": "evidence_only",
                "bindings": [
                    {
                        "source_resolution_id": resolved["source_resolution_id"],
                        "knowledge_item_id": resolved["resolved_knowledge_item_id"],
                        "knowledge_item_version_id": resolved["resolved_knowledge_item_version_id"],
                        "access_policy": "required",
                        "analysis_role": "primary",
                    }
                ],
            },
            idem="idem_scope",
        )
        self.assertEqual(scope.status_code, 201)
        scope_version = scope.json()["data"]["knowledge_scope"]
        binding_id = scope_version["source_bindings"][0]["knowledge_scope_source_binding_id"]

        current_scope = self.client.get(
            f"/alpha/research-cases/{research_case['research_case_id']}/knowledge-scopes/current"
        )
        self.assertEqual(current_scope.json()["data"]["knowledge_scope_version_id"], scope_version["knowledge_scope_version_id"])

        plan = self.post(
            f"/alpha/research-cases/{research_case['research_case_id']}/research-plans",
            {
                "expected_revision": 3,
                "knowledge_scope_version_id": scope_version["knowledge_scope_version_id"],
                "research_mode": "source_interpretation",
                "primary_objective": "Interpret the source concept.",
                "evidence_requirements": [
                    {
                        "requirement_type": {
                            "code": "direct_support",
                            "registry_version": "core-alpha-v1",
                        },
                        "description": "Find direct source support.",
                        "required_knowledge_scope_source_binding_ids": [binding_id],
                        "counterevidence_required": True,
                        "alternative_interpretation_required": False,
                        "completion_condition": "Required source reached terminal evidence state.",
                        "minimum_count": 1,
                    }
                ],
                "minimum_completion_condition": "Direct support exists or is reported missing.",
            },
            idem="idem_plan",
        )
        self.assertEqual(plan.status_code, 201)
        plan_version = plan.json()["data"]["research_plan"]

        current_plan = self.client.get(
            f"/alpha/research-plans/{plan_version['research_plan_id']}/current"
        )
        self.assertEqual(
            current_plan.json()["data"]["research_plan_version_id"],
            plan_version["research_plan_version_id"],
        )

        adjusted = self.post(
            f"/alpha/research-plan-versions/{plan_version['research_plan_version_id']}/commands/adjust",
            {
                "expected_revision": 4,
                "knowledge_scope_version_id": scope_version["knowledge_scope_version_id"],
                "research_mode": "source_interpretation",
                "primary_objective": "Interpret the source concept with counterevidence.",
                "evidence_requirements": [
                    {
                        "requirement_type": {
                            "code": "direct_support",
                            "registry_version": "core-alpha-v1",
                        },
                        "description": "Find direct source support.",
                        "required_knowledge_scope_source_binding_ids": [binding_id],
                        "counterevidence_required": True,
                        "alternative_interpretation_required": False,
                        "completion_condition": "Required source reached terminal evidence state.",
                        "minimum_count": 1,
                    }
                ],
                "minimum_completion_condition": "Support and counterevidence are both recorded.",
            },
            idem="idem_plan_adjust",
        )
        self.assertEqual(adjusted.status_code, 200)
        self.assertEqual(adjusted.json()["data"]["research_plan"]["version"], 2)
        self.assertEqual(
            adjusted.json()["data"]["superseded_version_ref"]["resource_id"],
            plan_version["research_plan_version_id"],
        )


if __name__ == "__main__":
    unittest.main()
