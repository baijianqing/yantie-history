from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.testclient import TestClient

from metaos.core_alpha.api import DeveloperExtensionRegistry, create_core_alpha_app
from metaos.core_alpha.commands import StaticFeatureFlagRegistry
from metaos.core_alpha.contracts.common import CommandContext
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from test_core_alpha_run_evidence_repository import NOW, code


def context() -> CommandContext:
    return CommandContext(
        command_id="cmd_feature_override",
        actor_type=code("developer"),
        actor_id="developer_1",
        idempotency_key="idem_feature_override",
        correlation_id="corr_1",
        causation_id="cause_1",
        trace_id="trace_1",
    )


class CoreAlphaOpenApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.catalog = KnowledgeCatalogAdapter(self.root / "workspace.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def app(
        self,
        *,
        feature_flags: StaticFeatureFlagRegistry | None = None,
        developer_extensions: DeveloperExtensionRegistry | None = None,
    ) -> TestClient:
        return TestClient(
            create_core_alpha_app(
                database=self.core_db,
                catalog=self.catalog,
                feature_flags=feature_flags,
                developer_extensions=developer_extensions,
            )
        )

    def test_openapi_assembles_public_internal_routes_without_duplicate_operation_ids(self) -> None:
        spec = self.app().app.openapi()
        paths = spec["paths"]

        for expected_path in (
            "/alpha/knowledge-items",
            "/alpha/research-cases",
            "/alpha/research-cases/{research_case_id}/research-runs",
            "/alpha/judgment-card-versions/{judgment_card_version_id}/claims",
            "/alpha/disposition-proposal-versions/{disposition_proposal_version_id}/commands/accept",
            "/internal/alpha/candidate-results",
            "/alpha/features",
        ):
            self.assertIn(expected_path, paths)

        self.assertNotIn("/alpha/developer/ping", paths)

        operation_ids: list[str] = []
        for path_item in paths.values():
            for method, operation in path_item.items():
                if method.lower() in {"get", "post"}:
                    operation_ids.append(operation["operationId"])
        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_feature_status_is_read_only_and_defaults_keep_developer_routes_hidden(self) -> None:
        extension = APIRouter()

        @extension.get("/ping")
        def ping() -> dict[str, bool]:
            return {"ok": True}

        registry = DeveloperExtensionRegistry()
        registry.register(extension)
        client = self.app(developer_extensions=registry)

        features = client.get("/alpha/features")
        self.assertEqual(features.status_code, 200)
        flags = {item["flag_key"]: item for item in features.json()["data"]}
        self.assertFalse(flags["core_alpha.developer_diagnostics"]["enabled"])
        self.assertFalse(flags["core_alpha.asynchronous_execution"]["enabled"])
        self.assertFalse(flags["core_alpha.complete_capabilities"]["enabled"])

        one_flag = client.get("/alpha/features/core_alpha.developer_diagnostics")
        self.assertEqual(one_flag.status_code, 200)
        self.assertFalse(one_flag.json()["data"]["enabled"])
        self.assertEqual(client.post("/alpha/features").status_code, 405)
        self.assertEqual(client.get("/alpha/developer/ping").status_code, 404)

    def test_developer_extension_mounts_only_when_diagnostics_flag_is_enabled(self) -> None:
        extension = APIRouter()

        @extension.get("/ping")
        def ping() -> dict[str, bool]:
            return {"ok": True}

        registry = DeveloperExtensionRegistry()
        registry.register(extension)
        flags = StaticFeatureFlagRegistry.core_alpha_defaults()
        with UnitOfWork(self.core_db) as uow:
            flags.set_override(
                uow=uow,
                context=context(),
                flag_key="core_alpha.developer_diagnostics",
                enabled=True,
                reason="Enable developer route assembly in test.",
                occurred_at=NOW,
            )

        client = self.app(feature_flags=flags, developer_extensions=registry)
        response = client.get("/alpha/developer/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        spec = client.app.openapi()
        self.assertIn("/alpha/developer/ping", spec["paths"])

    def test_developer_extension_prefix_must_be_absolute(self) -> None:
        registry = DeveloperExtensionRegistry()
        with self.assertRaises(ValueError):
            registry.register(APIRouter(), prefix="diagnostics")


if __name__ == "__main__":
    unittest.main()
