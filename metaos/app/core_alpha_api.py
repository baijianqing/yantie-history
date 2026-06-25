"""Local FastAPI entrypoint for the Core Alpha API."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI

from metaos.core_alpha.api import (
    create_core_alpha_app,
    create_core_alpha_app_with_developer_diagnostics,
)
from metaos.core_alpha.commands import StaticFeatureFlagRegistry
from metaos.core_alpha.contracts.common import CommandContext, OpenCodeValue
from metaos.core_alpha.persistence import CoreAlphaDatabase, UnitOfWork
from metaos.knowledge.catalog import KnowledgeCatalogAdapter
from metaos.workspace.paths import WorkspacePaths, ensure_workspace


CORE_ALPHA_DATABASE_ENV = "METAOS_CORE_ALPHA_DATABASE_PATH"
DEVELOPER_DIAGNOSTICS_ENV = "METAOS_CORE_ALPHA_DEVELOPER_DIAGNOSTICS"


def create_app(
    *,
    library_dir: Path | None = None,
    core_alpha_database_path: Path | None = None,
    enable_developer_diagnostics: bool | None = None,
) -> FastAPI:
    """Create a local Core Alpha API app for uvicorn and UI integration."""

    paths = ensure_workspace(library_dir)
    database = CoreAlphaDatabase(
        core_alpha_database_path or _core_alpha_database_path(paths)
    )
    database.initialize()
    catalog = KnowledgeCatalogAdapter(paths.database)
    diagnostics_enabled = (
        _env_flag(DEVELOPER_DIAGNOSTICS_ENV)
        if enable_developer_diagnostics is None
        else enable_developer_diagnostics
    )
    if diagnostics_enabled:
        feature_flags = StaticFeatureFlagRegistry.core_alpha_defaults()
        _enable_developer_diagnostics(database, feature_flags)
        return create_core_alpha_app_with_developer_diagnostics(
            database=database,
            catalog=catalog,
            feature_flags=feature_flags,
        )
    return create_core_alpha_app(database=database, catalog=catalog)


def _core_alpha_database_path(paths: WorkspacePaths) -> Path:
    configured = os.getenv(CORE_ALPHA_DATABASE_ENV)
    if configured:
        return Path(configured).resolve()
    return paths.library / "core-alpha.sqlite3"


def _enable_developer_diagnostics(
    database: CoreAlphaDatabase,
    feature_flags: StaticFeatureFlagRegistry,
) -> None:
    with UnitOfWork(database) as uow:
        feature_flags.set_override(
            uow=uow,
            context=CommandContext(
                command_id=f"cmd_{uuid.uuid4().hex}",
                actor_type=OpenCodeValue(
                    code="developer",
                    registry_version="core-alpha-v1",
                ),
                actor_id="developer_local",
                idempotency_key=f"local_dev_{uuid.uuid4().hex}",
                correlation_id=f"corr_{uuid.uuid4().hex}",
                causation_id=f"cause_{uuid.uuid4().hex}",
                trace_id=f"trace_{uuid.uuid4().hex}",
            ),
            flag_key="core_alpha.developer_diagnostics",
            enabled=True,
            reason="Enable local developer diagnostics API.",
            occurred_at=datetime.now(timezone.utc),
        )


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


__all__ = ["create_app"]
