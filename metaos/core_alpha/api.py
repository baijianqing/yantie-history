"""Assembly helpers for the Core Alpha FastAPI surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from metaos import __version__
from metaos.core_alpha.api_decision import create_decision_api_router
from metaos.core_alpha.api_judgment import create_judgment_api_router
from metaos.core_alpha.api_scope import create_scope_api_router
from metaos.core_alpha.commands import FeatureFlagSnapshot, StaticFeatureFlagRegistry
from metaos.core_alpha.persistence import CoreAlphaDatabase
from metaos.knowledge.catalog import KnowledgeCatalogAdapter


class FeatureFlagReader(Protocol):
    def get(self, flag_key: str) -> FeatureFlagSnapshot:
        ...

    def list(self) -> list[FeatureFlagSnapshot]:
        ...


@dataclass(frozen=True)
class DeveloperRouterExtension:
    router: APIRouter
    prefix: str = ""


class DeveloperExtensionRegistry:
    """Stable registration point for later diagnostics routers."""

    def __init__(self) -> None:
        self._extensions: list[DeveloperRouterExtension] = []

    def register(self, router: APIRouter, *, prefix: str = "") -> None:
        if prefix and not prefix.startswith("/"):
            raise ValueError("developer extension prefix must start with '/'")
        self._extensions.append(DeveloperRouterExtension(router=router, prefix=prefix))

    def extensions(self) -> list[DeveloperRouterExtension]:
        return list(self._extensions)


def create_core_alpha_app(
    *,
    database: CoreAlphaDatabase,
    catalog: KnowledgeCatalogAdapter,
    feature_flags: FeatureFlagReader | None = None,
    developer_extensions: DeveloperExtensionRegistry | None = None,
) -> FastAPI:
    """Create a standalone Core Alpha API app for tests and later mounting."""

    app = FastAPI(title="MetaOS Core Alpha", version=__version__)
    app.include_router(
        create_core_alpha_api_router(
            database=database,
            catalog=catalog,
            feature_flags=feature_flags,
            developer_extensions=developer_extensions,
        )
    )
    return app


def create_core_alpha_api_router(
    *,
    database: CoreAlphaDatabase,
    catalog: KnowledgeCatalogAdapter,
    feature_flags: FeatureFlagReader | None = None,
    developer_extensions: DeveloperExtensionRegistry | None = None,
) -> APIRouter:
    """Create the unified Minimum Slice public and internal router."""

    flags = feature_flags or StaticFeatureFlagRegistry.core_alpha_defaults()
    extensions = developer_extensions or DeveloperExtensionRegistry()
    router = APIRouter()
    router.include_router(create_scope_api_router(database=database, catalog=catalog))
    router.include_router(create_judgment_api_router(database=database))
    router.include_router(create_decision_api_router(database=database))
    router.include_router(_feature_router(flags))

    if flags.get("core_alpha.developer_diagnostics").enabled:
        for extension in extensions.extensions():
            router.include_router(
                extension.router,
                prefix=f"/alpha/developer{extension.prefix}",
                tags=["core-alpha-developer"],
            )
    return router


def _feature_router(feature_flags: FeatureFlagReader) -> APIRouter:
    router = APIRouter(prefix="/alpha", tags=["core-alpha-features"])

    @router.get("/features")
    def list_feature_flags() -> dict[str, object]:
        return {
            "data": [_feature_snapshot(flag) for flag in feature_flags.list()],
            "page": {"next_cursor": None},
        }

    @router.get("/features/{flag_key}")
    def get_feature_flag(flag_key: str) -> object:
        try:
            return {"data": _feature_snapshot(feature_flags.get(flag_key))}
        except KeyError as exc:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "resource_not_found",
                        "message": str(exc),
                        "details": {},
                        "trace_id": "trace_feature_flag_lookup",
                        "retryable": False,
                    }
                },
            )

    return router


def _feature_snapshot(snapshot: FeatureFlagSnapshot) -> dict[str, object]:
    return {
        "flag_key": snapshot.flag_key,
        "enabled": snapshot.enabled,
        "default_enabled": snapshot.default_enabled,
        "overridden": snapshot.overridden,
        "description": snapshot.description,
    }


__all__ = [
    "DeveloperExtensionRegistry",
    "DeveloperRouterExtension",
    "create_core_alpha_api_router",
    "create_core_alpha_app",
]
