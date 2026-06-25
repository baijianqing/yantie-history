from __future__ import annotations

from typing import Any

from metaos.app.core_alpha_workbench import (
    CoreAlphaApiClient,
    WorkbenchSnapshot,
    binding_rows,
    claim_rows,
    feature_enabled,
    is_adoptable_judgment,
    judgment_state,
    load_workbench_snapshot,
)


def test_judgment_state_distinguishes_blocked_and_adoptable() -> None:
    blocked = {
        "audit_status": "blocked",
        "validity_status": "valid",
        "lifecycle_status": "current",
    }
    acceptable = {
        "audit_status": "acceptable",
        "validity_status": "valid",
        "lifecycle_status": "current",
    }
    provisional = {
        "audit_status": "provisionally_acceptable",
        "validity_status": "valid",
        "lifecycle_status": "current",
    }

    assert judgment_state(blocked)["label"] == "证据链不完整，当前判断不可采纳"
    assert not is_adoptable_judgment(blocked)
    assert judgment_state(acceptable)["label"] == "可采纳判断"
    assert is_adoptable_judgment(acceptable)
    assert judgment_state(provisional)["label"] == "可采纳判断（有非阻断警告）"
    assert is_adoptable_judgment(provisional)


def test_binding_rows_keep_access_policy_and_analysis_role_separate() -> None:
    rows = binding_rows(
        {
            "source_bindings": [
                {
                    "knowledge_scope_source_binding_id": "bind_required",
                    "source_resolution_id": "sr_required",
                    "knowledge_item_id": "ki_1",
                    "knowledge_item_version_id": "kiv_1",
                    "access_policy": "required",
                    "analysis_role": "comparison",
                },
                {
                    "knowledge_scope_source_binding_id": "bind_excluded",
                    "source_resolution_id": "sr_excluded",
                    "knowledge_item_id": "ki_2",
                    "knowledge_item_version_id": None,
                    "access_policy": "excluded",
                    "analysis_role": None,
                },
            ]
        }
    )

    assert rows[0]["access_policy"] == "required"
    assert rows[0]["analysis_role"] == "comparison"
    assert rows[1]["access_policy"] == "excluded"
    assert rows[1]["analysis_role"] == "-"
    assert rows[1]["knowledge_item_version_id"] == "-"


def test_claim_rows_keep_user_attitude_separate_from_evidence_status() -> None:
    rows = claim_rows(
        {
            "claims": [
                {
                    "claim": {
                        "claim_text": "用户接受不等于证据充分。",
                        "claim_version_id": "claim_v1",
                        "evidence_status": "partially_supported",
                        "user_attitude": "accepted",
                        "importance": "core",
                        "expression_role": "core_judgment",
                        "confidence_level": "medium",
                    },
                    "evidence_links": [{"claim_evidence_link_id": "cel_1"}],
                }
            ]
        }
    )

    assert rows == [
        {
            "claim_text": "用户接受不等于证据充分。",
            "evidence_status": "partially_supported",
            "user_attitude": "accepted",
            "importance": "core",
            "expression_role": "core_judgment",
            "confidence_level": "medium",
            "evidence_link_count": 1,
            "claim_version_id": "claim_v1",
        }
    ]


def test_snapshot_loads_public_api_views_and_developer_flag() -> None:
    api = FakeWorkbenchApi()
    snapshot = load_workbench_snapshot(api)

    assert isinstance(snapshot, WorkbenchSnapshot)
    assert snapshot.selected_case is not None
    assert snapshot.selected_case["research_case_id"] == "case_1"
    assert snapshot.knowledge_scope is not None
    assert snapshot.judgment_card is not None
    assert snapshot.developer_diagnostics_enabled
    assert [call[0] for call in api.calls] == [
        "list_research_cases",
        "list_knowledge_items",
        "list_source_resolutions",
        "get_current_knowledge_scope",
        "get_current_judgment_card",
        "list_claims",
        "get_current_judgment_audit",
        "get_judgment_audit",
        "get_current_decision_fitness",
        "list_disposition_proposals",
        "list_features",
    ]


def test_feature_enabled_requires_matching_enabled_flag() -> None:
    assert feature_enabled(
        [
            {"flag_key": "core_alpha.developer_diagnostics", "enabled": False},
            {"flag_key": "other", "enabled": True},
        ],
        "core_alpha.developer_diagnostics",
    ) is False
    assert feature_enabled(
        [{"flag_key": "core_alpha.developer_diagnostics", "enabled": True}],
        "core_alpha.developer_diagnostics",
    ) is True


def test_api_client_uses_public_route_and_idempotency_for_create_case() -> None:
    client = RecordingCoreAlphaApiClient()

    client.create_research_case(title="问题", question_text="如何判断？")

    assert client.requests == [
        (
            "POST",
            "/alpha/research-cases",
            {
                "title": "问题",
                "question_text": "如何判断？",
                "question_role": "root",
            },
        )
    ]


class RecordingCoreAlphaApiClient(CoreAlphaApiClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://example.test")
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        query: dict[str, str | int] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        assert query is None
        assert idempotency_key is None
        self.requests.append((method, path, payload))
        return {"data": {"research_case": {"research_case_id": "case_1"}}}


class FakeWorkbenchApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _record(self, name: str, *args: Any) -> None:
        self.calls.append((name, args))

    def list_research_cases(self) -> list[dict[str, Any]]:
        self._record("list_research_cases")
        return [
            {
                "research_case_id": "case_1",
                "title": "第一案",
                "current_question_id": "question_1",
                "revision": 3,
            }
        ]

    def get_research_case(self, research_case_id: str) -> dict[str, Any]:
        self._record("get_research_case", research_case_id)
        raise AssertionError("snapshot should use the list row when no explicit case is selected")

    def list_knowledge_items(self) -> list[dict[str, Any]]:
        self._record("list_knowledge_items")
        return [{"knowledge_item_id": "ki_1", "title": "鬼谷子"}]

    def list_source_resolutions(self, research_case_id: str) -> list[dict[str, Any]]:
        self._record("list_source_resolutions", research_case_id)
        return [{"source_resolution_id": "sr_1", "resolution_status": "resolved"}]

    def get_current_knowledge_scope(self, research_case_id: str) -> dict[str, Any]:
        self._record("get_current_knowledge_scope", research_case_id)
        return {"knowledge_scope_version_id": "ks_v1", "source_bindings": []}

    def get_current_judgment_card(self, research_case_id: str) -> dict[str, Any]:
        self._record("get_current_judgment_card", research_case_id)
        return {
            "judgment_card_version_id": "jc_v1",
            "research_run_id": "run_1",
            "audit_status": "acceptable",
            "validity_status": "valid",
            "lifecycle_status": "current",
        }

    def list_claims(self, judgment_card_version_id: str) -> dict[str, Any]:
        self._record("list_claims", judgment_card_version_id)
        return {"claims": []}

    def get_current_judgment_audit(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any]:
        self._record("get_current_judgment_audit", judgment_card_version_id)
        return {"judgment_audit_id": "audit_1"}

    def get_judgment_audit(self, judgment_audit_id: str) -> dict[str, Any]:
        self._record("get_judgment_audit", judgment_audit_id)
        return {"audit_findings": []}

    def get_current_decision_fitness(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any]:
        self._record("get_current_decision_fitness", judgment_card_version_id)
        return {"decision_fitness_id": "fit_1"}

    def list_disposition_proposals(self, research_case_id: str) -> list[dict[str, Any]]:
        self._record("list_disposition_proposals", research_case_id)
        return []

    def list_features(self) -> list[dict[str, Any]]:
        self._record("list_features")
        return [{"flag_key": "core_alpha.developer_diagnostics", "enabled": True}]
