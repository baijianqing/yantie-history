from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from metaos.app.core_alpha_api import create_app
from metaos.app.core_alpha_workbench import (
    binding_rows,
    judgment_state,
    load_workbench_snapshot,
    source_resolution_rows,
)


def test_public_api_source_resolution_and_workbench_snapshot_share_case(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(library_dir=tmp_path / "library"))

    created = client.post(
        "/alpha/research-cases",
        headers={"Idempotency-Key": "idem_e2e_create_case"},
        json={
            "title": "E2E source governance",
            "question_text": "Use only missing-source to answer this.",
            "question_role": "root",
        },
    )
    assert created.status_code == 201
    created_data = created.json()["data"]
    case = created_data["research_case"]
    question = created_data["research_question"]

    resolution = client.post(
        f"/alpha/research-cases/{case['research_case_id']}/source-resolutions",
        headers={"Idempotency-Key": "idem_e2e_source_resolution"},
        json={
            "expected_revision": case["revision"],
            "research_question_id": question["research_question_id"],
            "resolution_stage": "full",
            "anchors": [
                {
                    "raw_anchor": "missing-source",
                    "requested_access_policy": "required",
                }
            ],
        },
    )
    assert resolution.status_code == 201
    source_resolution = resolution.json()["data"]["source_resolutions"][0]
    assert source_resolution["resolution_status"] == "not_found"
    assert source_resolution["requested_access_policy"] == "required"

    snapshot = load_workbench_snapshot(WorkbenchTestClientApi(client))

    assert snapshot.errors == []
    assert snapshot.selected_case is not None
    assert snapshot.selected_case["research_case_id"] == case["research_case_id"]
    assert source_resolution_rows(snapshot.source_resolutions)[0]["resolution_status"] == "not_found"
    assert binding_rows(snapshot.knowledge_scope) == []
    assert judgment_state(snapshot.judgment_card)["label"] == "判断草稿"


def test_developer_diagnostics_is_mounted_but_requires_developer_identity(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(
            library_dir=tmp_path / "library",
            enable_developer_diagnostics=True,
        )
    )

    unauthenticated = client.get("/alpha/developer/projections/status")
    authenticated = client.get(
        "/alpha/developer/projections/status",
        headers={"X-Developer-Actor-Id": "developer_1"},
    )
    features = client.get("/alpha/features")

    assert unauthenticated.status_code == 401
    assert authenticated.status_code == 200
    flags = {flag["flag_key"]: flag for flag in features.json()["data"]}
    assert flags["core_alpha.developer_diagnostics"]["enabled"] is True


class WorkbenchTestClientApi:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def list_research_cases(self) -> list[dict[str, Any]]:
        return self._get_list("/alpha/research-cases")

    def get_research_case(self, research_case_id: str) -> dict[str, Any]:
        return self._get_data(f"/alpha/research-cases/{research_case_id}")

    def create_research_case(self, *, title: str, question_text: str) -> dict[str, Any]:
        response = self.client.post(
            "/alpha/research-cases",
            headers={"Idempotency-Key": "idem_workbench_create_case"},
            json={
                "title": title,
                "question_text": question_text,
                "question_role": "root",
            },
        )
        response.raise_for_status()
        return response.json()["data"]

    def list_knowledge_items(self) -> list[dict[str, Any]]:
        return self._get_list("/alpha/knowledge-items")

    def create_source_resolution(
        self,
        *,
        research_case_id: str,
        research_question_id: str,
        expected_revision: int,
        raw_anchor: str,
        access_policy: str,
        version_hint: str | None = None,
    ) -> dict[str, Any]:
        anchor: dict[str, Any] = {
            "raw_anchor": raw_anchor,
            "requested_access_policy": access_policy,
        }
        if version_hint:
            anchor["requested_version_hint"] = version_hint
        response = self.client.post(
            f"/alpha/research-cases/{research_case_id}/source-resolutions",
            headers={"Idempotency-Key": "idem_workbench_source_resolution"},
            json={
                "expected_revision": expected_revision,
                "research_question_id": research_question_id,
                "resolution_stage": "full",
                "anchors": [anchor],
            },
        )
        response.raise_for_status()
        return response.json()["data"]

    def list_source_resolutions(self, research_case_id: str) -> list[dict[str, Any]]:
        return self._get_list(f"/alpha/research-cases/{research_case_id}/source-resolutions")

    def get_current_knowledge_scope(self, research_case_id: str) -> dict[str, Any] | None:
        return self._get_data(f"/alpha/research-cases/{research_case_id}/knowledge-scopes/current")

    def get_current_judgment_card(self, research_case_id: str) -> dict[str, Any] | None:
        return self._get_data(f"/alpha/research-cases/{research_case_id}/judgment-cards/current")

    def list_claims(self, judgment_card_version_id: str) -> dict[str, Any]:
        return self._get_data(f"/alpha/judgment-card-versions/{judgment_card_version_id}/claims")

    def get_current_judgment_audit(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        return self._get_data(
            f"/alpha/judgment-card-versions/{judgment_card_version_id}/audits/current"
        )

    def get_judgment_audit(self, judgment_audit_id: str) -> dict[str, Any]:
        return self._get_data(f"/alpha/judgment-audits/{judgment_audit_id}")

    def get_current_decision_fitness(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        return self._get_data(
            (
                "/alpha/judgment-card-versions/"
                f"{judgment_card_version_id}/decision-fitness/current"
            )
        )

    def list_disposition_proposals(self, research_case_id: str) -> list[dict[str, Any]]:
        return self._get_list(f"/alpha/research-cases/{research_case_id}/disposition-proposals")

    def accept_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
        judgment_card_version_id: str,
        decision_fitness_id: str,
        warning_acknowledgement_ids: list[str],
    ) -> dict[str, Any]:
        raise NotImplementedError("not needed by the E2E smoke gate")

    def reject_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        raise NotImplementedError("not needed by the E2E smoke gate")

    def adjust_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
        proposed_disposition_type: str,
        reason: str,
        defer_until: str | None = None,
        observation_condition: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("not needed by the E2E smoke gate")

    def list_features(self) -> list[dict[str, Any]]:
        return self._get_list("/alpha/features")

    def _get_list(self, path: str) -> list[dict[str, Any]]:
        data = self._get_data(path)
        assert isinstance(data, list)
        return data

    def _get_data(self, path: str) -> Any:
        response = self.client.get(path)
        response.raise_for_status()
        return response.json()["data"]
