from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from metaos.app.core_alpha_api import create_app


def test_local_core_alpha_api_entrypoint_serves_public_routes(tmp_path: Path) -> None:
    library = tmp_path / "library"
    app = create_app(library_dir=library)
    client = TestClient(app)

    cases = client.get("/alpha/research-cases")
    features = client.get("/alpha/features")

    assert cases.status_code == 200
    assert cases.json()["data"] == []
    assert features.status_code == 200
    assert (library / "core-alpha.sqlite3").exists()
    assert (library / "metaos.sqlite3").exists()


def test_local_core_alpha_api_can_mount_developer_diagnostics(tmp_path: Path) -> None:
    app = create_app(
        library_dir=tmp_path / "library",
        enable_developer_diagnostics=True,
    )
    client = TestClient(app)

    features = client.get("/alpha/features")
    unauthenticated = client.get("/alpha/developer/projections/status")
    projections = client.get(
        "/alpha/developer/projections/status",
        headers={"X-Developer-Actor-Id": "developer_1"},
    )

    assert features.status_code == 200
    flags = {item["flag_key"]: item for item in features.json()["data"]}
    assert flags["core_alpha.developer_diagnostics"]["enabled"] is True
    assert unauthenticated.status_code == 401
    assert projections.status_code == 200
