from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from metaos.core_alpha.api import (
    create_core_alpha_app,
    create_core_alpha_app_with_developer_diagnostics,
)
from metaos.core_alpha.commands import StaticFeatureFlagRegistry
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from test_core_alpha_openapi import context
from test_core_alpha_run_evidence_repository import NOW


class CoreAlphaDeveloperOpenApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.core_db = CoreAlphaDatabase(self.root / "core-alpha.db")
        self.core_db.initialize()
        self.catalog = KnowledgeCatalogAdapter(self.root / "workspace.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def enabled_flags(self) -> StaticFeatureFlagRegistry:
        flags = StaticFeatureFlagRegistry.core_alpha_defaults()
        with UnitOfWork(self.core_db) as uow:
            flags.set_override(
                uow=uow,
                context=context(),
                flag_key="core_alpha.developer_diagnostics",
                enabled=True,
                reason="Enable developer diagnostics assembly in test.",
                occurred_at=NOW,
            )
        return flags

    def test_default_core_alpha_app_does_not_expose_developer_routes(self) -> None:
        app = create_core_alpha_app(
            database=self.core_db,
            catalog=self.catalog,
            feature_flags=self.enabled_flags(),
        )
        spec = app.openapi()
        self.assertFalse(
            any(path.startswith("/alpha/developer") for path in spec["paths"])
        )

    def test_developer_diagnostics_app_mounts_minimum_slice_routes_only(self) -> None:
        client = TestClient(
            create_core_alpha_app_with_developer_diagnostics(
                database=self.core_db,
                catalog=self.catalog,
                feature_flags=self.enabled_flags(),
            )
        )
        paths = client.app.openapi()["paths"]

        for expected_path in (
            "/alpha/developer/research-runs/{research_run_id}/trace",
            "/alpha/developer/material-manifests",
            "/alpha/developer/index-generations",
            "/alpha/developer/projections/status",
        ):
            self.assertIn(expected_path, paths)

        self.assertNotIn("/alpha/developer/research-cases/{research_case_id}/activity", paths)
        self.assertNotIn("/alpha/developer/research-runs/{research_run_id}/budget", paths)

    def test_developer_routes_retain_independent_authorization_boundary(self) -> None:
        client = TestClient(
            create_core_alpha_app_with_developer_diagnostics(
                database=self.core_db,
                catalog=self.catalog,
                feature_flags=self.enabled_flags(),
            )
        )

        unauthenticated = client.get("/alpha/developer/research-runs/run_missing/trace")
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(unauthenticated.json()["error"]["code"], "authentication_required")

        authenticated = client.get(
            "/alpha/developer/research-runs/run_missing/trace",
            headers={"X-Developer-Actor-Id": "dev_1"},
        )
        self.assertEqual(authenticated.status_code, 404)
        self.assertEqual(authenticated.json()["error"]["code"], "resource_not_found")

    def test_developer_routes_remain_hidden_when_flag_is_disabled(self) -> None:
        client = TestClient(
            create_core_alpha_app_with_developer_diagnostics(
                database=self.core_db,
                catalog=self.catalog,
            )
        )
        self.assertEqual(
            client.get(
                "/alpha/developer/projections/status",
                headers={"X-Developer-Actor-Id": "dev_1"},
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
