"""Streamlit workbench for the Core Alpha Minimum Slice."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from metaos.core.schemas import Job, JobStatus, JobType
from metaos.ingest.service import DOCUMENT_MIME_TYPES, IngestService
from metaos.tasks.pipeline import OCR_EXTENSIONS, enqueue_document_pipeline
from metaos.tasks.queueing import enqueue_rebuild_chunks
from metaos.workspace.jobs import JobRepository


KNOWLEDGE_PROCESSING_JOB_TYPES = {
    JobType.ingest_document,
    JobType.pdf_route,
    JobType.ocr_document,
    JobType.rebuild_chunks,
    JobType.index_knowledge,
}
ACTIVE_JOB_STATUSES = {JobStatus.pending, JobStatus.running}
SUPPORTED_ASYNC_UPLOAD_EXTENSIONS = tuple(
    sorted(extension.lstrip(".") for extension in DOCUMENT_MIME_TYPES)
)


class CoreAlphaApiError(RuntimeError):
    """Raised when the public Core Alpha API returns an error envelope."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(f"{status_code} {code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message


class WorkbenchApi(Protocol):
    def list_research_cases(self) -> list[dict[str, Any]]:
        ...

    def get_research_case(self, research_case_id: str) -> dict[str, Any]:
        ...

    def create_research_case(self, *, title: str, question_text: str) -> dict[str, Any]:
        ...

    def list_knowledge_items(self) -> list[dict[str, Any]]:
        ...

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
        ...

    def list_source_resolutions(self, research_case_id: str) -> list[dict[str, Any]]:
        ...

    def get_current_knowledge_scope(self, research_case_id: str) -> dict[str, Any] | None:
        ...

    def get_current_judgment_card(self, research_case_id: str) -> dict[str, Any] | None:
        ...

    def list_claims(self, judgment_card_version_id: str) -> dict[str, Any]:
        ...

    def get_current_judgment_audit(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        ...

    def get_judgment_audit(self, judgment_audit_id: str) -> dict[str, Any]:
        ...

    def get_current_decision_fitness(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        ...

    def list_disposition_proposals(self, research_case_id: str) -> list[dict[str, Any]]:
        ...

    def accept_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
        judgment_card_version_id: str,
        decision_fitness_id: str,
        warning_acknowledgement_ids: list[str],
    ) -> dict[str, Any]:
        ...

    def reject_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        ...

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
        ...

    def list_features(self) -> list[dict[str, Any]]:
        ...


class CoreAlphaApiClient:
    """Small HTTP client that talks only to the frozen public Core Alpha API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        *,
        actor_id: str = "user_local",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.actor_id = actor_id
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener()

    def list_research_cases(self) -> list[dict[str, Any]]:
        return _as_list(self._request_json("GET", "/alpha/research-cases"))

    def get_research_case(self, research_case_id: str) -> dict[str, Any]:
        return _as_dict(self._request_json("GET", f"/alpha/research-cases/{research_case_id}"))

    def create_research_case(self, *, title: str, question_text: str) -> dict[str, Any]:
        return _as_dict(
            self._request_json(
                "POST",
                "/alpha/research-cases",
                {
                    "title": title,
                    "question_text": question_text,
                    "question_role": "root",
                },
            )
        )

    def list_knowledge_items(self) -> list[dict[str, Any]]:
        return _as_list(self._request_json("GET", "/alpha/knowledge-items"))

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
        return _as_dict(
            self._request_json(
                "POST",
                f"/alpha/research-cases/{research_case_id}/source-resolutions",
                {
                    "expected_revision": expected_revision,
                    "research_question_id": research_question_id,
                    "resolution_stage": "full",
                    "anchors": [anchor],
                },
            )
        )

    def list_source_resolutions(self, research_case_id: str) -> list[dict[str, Any]]:
        return _as_list(
            self._request_json(
                "GET",
                f"/alpha/research-cases/{research_case_id}/source-resolutions",
            )
        )

    def get_current_knowledge_scope(self, research_case_id: str) -> dict[str, Any] | None:
        return _optional_dict(
            self._request_json(
                "GET",
                f"/alpha/research-cases/{research_case_id}/knowledge-scopes/current",
            )
        )

    def get_current_judgment_card(self, research_case_id: str) -> dict[str, Any] | None:
        return _optional_dict(
            self._request_json(
                "GET",
                f"/alpha/research-cases/{research_case_id}/judgment-cards/current",
            )
        )

    def list_claims(self, judgment_card_version_id: str) -> dict[str, Any]:
        return _as_dict(
            self._request_json(
                "GET",
                f"/alpha/judgment-card-versions/{judgment_card_version_id}/claims",
            )
        )

    def get_current_judgment_audit(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        return _optional_dict(
            self._request_json(
                "GET",
                f"/alpha/judgment-card-versions/{judgment_card_version_id}/audits/current",
            )
        )

    def get_judgment_audit(self, judgment_audit_id: str) -> dict[str, Any]:
        return _as_dict(
            self._request_json("GET", f"/alpha/judgment-audits/{judgment_audit_id}")
        )

    def get_current_decision_fitness(
        self,
        judgment_card_version_id: str,
    ) -> dict[str, Any] | None:
        return _optional_dict(
            self._request_json(
                "GET",
                f"/alpha/judgment-card-versions/{judgment_card_version_id}/decision-fitness/current",
            )
        )

    def list_disposition_proposals(self, research_case_id: str) -> list[dict[str, Any]]:
        return _as_list(
            self._request_json(
                "GET",
                f"/alpha/research-cases/{research_case_id}/disposition-proposals",
            )
        )

    def accept_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
        judgment_card_version_id: str,
        decision_fitness_id: str,
        warning_acknowledgement_ids: list[str],
    ) -> dict[str, Any]:
        return _as_dict(
            self._request_json(
                "POST",
                (
                    "/alpha/disposition-proposal-versions/"
                    f"{disposition_proposal_version_id}/commands/accept"
                ),
                {
                    "expected_revision": expected_revision,
                    "judgment_card_version_id": judgment_card_version_id,
                    "decision_fitness_id": decision_fitness_id,
                    "warning_acknowledgement_ids": warning_acknowledgement_ids,
                },
            )
        )

    def reject_disposition_proposal(
        self,
        disposition_proposal_version_id: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        return _as_dict(
            self._request_json(
                "POST",
                (
                    "/alpha/disposition-proposal-versions/"
                    f"{disposition_proposal_version_id}/commands/reject"
                ),
                {"expected_revision": expected_revision},
            )
        )

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
        payload: dict[str, Any] = {
            "expected_revision": expected_revision,
            "proposed_disposition_type": proposed_disposition_type,
            "reason": reason,
        }
        if defer_until:
            payload["defer_until"] = defer_until
        if observation_condition:
            payload["observation_condition"] = observation_condition
        return _as_dict(
            self._request_json(
                "POST",
                (
                    "/alpha/disposition-proposal-versions/"
                    f"{disposition_proposal_version_id}/commands/adjust"
                ),
                payload,
            )
        )

    def list_features(self) -> list[dict[str, Any]]:
        return _as_list(self._request_json("GET", "/alpha/features"))

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        query: dict[str, str | int] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "Accept": "application/json",
            "X-Actor-Id": self.actor_id,
        }
        body: bytes | None = None
        if method == "POST":
            headers["Content-Type"] = "application/json"
            headers["Idempotency-Key"] = idempotency_key or f"ui_{uuid.uuid4().hex}"
            body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                return _decode_json(response.read())
        except HTTPError as exc:
            decoded = _decode_json(exc.read())
            error = decoded.get("error", {}) if isinstance(decoded, dict) else {}
            raise CoreAlphaApiError(
                exc.code,
                str(error.get("code", "api_error")),
                str(error.get("message", exc.reason)),
            ) from exc
        except URLError as exc:
            raise CoreAlphaApiError(0, "api_unavailable", str(exc.reason)) from exc


@dataclass(frozen=True)
class WorkbenchSnapshot:
    cases: list[dict[str, Any]]
    selected_case: dict[str, Any] | None
    knowledge_items: list[dict[str, Any]]
    source_resolutions: list[dict[str, Any]]
    knowledge_scope: dict[str, Any] | None
    judgment_card: dict[str, Any] | None
    claims_payload: dict[str, Any]
    judgment_audit: dict[str, Any] | None
    audit_detail: dict[str, Any] | None
    decision_fitness: dict[str, Any] | None
    disposition_proposals: list[dict[str, Any]]
    features: list[dict[str, Any]]
    errors: list[str]

    @property
    def developer_diagnostics_enabled(self) -> bool:
        return feature_enabled(self.features, "core_alpha.developer_diagnostics")


def load_workbench_snapshot(
    api: WorkbenchApi,
    *,
    selected_case_id: str | None = None,
) -> WorkbenchSnapshot:
    errors: list[str] = []
    cases = _safe_call(api.list_research_cases, errors, default=[])
    knowledge_items = _safe_call(api.list_knowledge_items, errors, default=[])
    selected_case = _select_case(api, cases, selected_case_id, errors)
    case_id = selected_case.get("research_case_id") if selected_case else None

    source_resolutions: list[dict[str, Any]] = []
    knowledge_scope: dict[str, Any] | None = None
    judgment_card: dict[str, Any] | None = None
    claims_payload: dict[str, Any] = {"claims": []}
    judgment_audit: dict[str, Any] | None = None
    audit_detail: dict[str, Any] | None = None
    decision_fitness: dict[str, Any] | None = None
    disposition_proposals: list[dict[str, Any]] = []

    if case_id:
        source_resolutions = _safe_call(
            lambda: api.list_source_resolutions(case_id),
            errors,
            default=[],
        )
        knowledge_scope = _safe_call(
            lambda: api.get_current_knowledge_scope(case_id),
            errors,
            default=None,
        )
        judgment_card = _safe_call(
            lambda: api.get_current_judgment_card(case_id),
            errors,
            default=None,
        )
        if judgment_card:
            judgment_card_version_id = judgment_card["judgment_card_version_id"]
            claims_payload = _safe_call(
                lambda: api.list_claims(judgment_card_version_id),
                errors,
                default={"claims": []},
            )
            judgment_audit = _safe_call(
                lambda: api.get_current_judgment_audit(judgment_card_version_id),
                errors,
                default=None,
            )
            if judgment_audit:
                audit_id = judgment_audit["judgment_audit_id"]
                audit_detail = _safe_call(
                    lambda: api.get_judgment_audit(audit_id),
                    errors,
                    default=None,
                )
            decision_fitness = _safe_call(
                lambda: api.get_current_decision_fitness(judgment_card_version_id),
                errors,
                default=None,
            )
        disposition_proposals = _safe_call(
            lambda: api.list_disposition_proposals(case_id),
            errors,
            default=[],
        )
    features = _safe_call(api.list_features, errors, default=[])
    return WorkbenchSnapshot(
        cases=cases,
        selected_case=selected_case,
        knowledge_items=knowledge_items,
        source_resolutions=source_resolutions,
        knowledge_scope=knowledge_scope,
        judgment_card=judgment_card,
        claims_payload=claims_payload,
        judgment_audit=judgment_audit,
        audit_detail=audit_detail,
        decision_fitness=decision_fitness,
        disposition_proposals=disposition_proposals,
        features=features,
        errors=errors,
    )


def judgment_state(judgment: dict[str, Any] | None) -> dict[str, str]:
    if not judgment:
        return {"label": "判断草稿", "tone": "info"}
    audit_status = judgment.get("audit_status")
    validity_status = judgment.get("validity_status")
    if audit_status == "blocked":
        return {"label": "证据链不完整，当前判断不可采纳", "tone": "error"}
    if validity_status == "invalid":
        return {"label": "判断已失效", "tone": "error"}
    if validity_status == "needs_review":
        return {"label": "判断需要复核", "tone": "warning"}
    if audit_status == "acceptable":
        return {"label": "可采纳判断", "tone": "success"}
    if audit_status == "provisionally_acceptable":
        return {"label": "可采纳判断（有非阻断警告）", "tone": "warning"}
    if audit_status in {"pending", "auditing"}:
        return {"label": "审计中", "tone": "info"}
    return {"label": "判断草稿", "tone": "info"}


def is_adoptable_judgment(judgment: dict[str, Any] | None) -> bool:
    if not judgment:
        return False
    return (
        judgment.get("audit_status") in {"acceptable", "provisionally_acceptable"}
        and judgment.get("validity_status") == "valid"
        and judgment.get("lifecycle_status") == "current"
    )


def binding_rows(scope: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not scope:
        return []
    rows: list[dict[str, Any]] = []
    for binding in scope.get("source_bindings", []):
        rows.append(
            {
                "binding_id": binding.get("knowledge_scope_source_binding_id"),
                "access_policy": binding.get("access_policy"),
                "analysis_role": binding.get("analysis_role") or "-",
                "knowledge_item_id": binding.get("knowledge_item_id"),
                "knowledge_item_version_id": binding.get("knowledge_item_version_id") or "-",
                "source_resolution_id": binding.get("source_resolution_id"),
            }
        )
    return rows


def source_resolution_rows(resolutions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "raw_anchor": resolution.get("raw_anchor"),
            "access_policy": resolution.get("requested_access_policy"),
            "resolution_status": resolution.get("resolution_status"),
            "knowledge_item_id": resolution.get("resolved_knowledge_item_id") or "-",
            "knowledge_item_version_id": (
                resolution.get("resolved_knowledge_item_version_id") or "-"
            ),
            "reason": resolution.get("ambiguity_reason")
            or resolution.get("failure_reason")
            or "-",
        }
        for resolution in resolutions
    ]


def claim_rows(claims_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in claims_payload.get("claims", []):
        claim = item.get("claim", {})
        evidence_links = item.get("evidence_links", [])
        rows.append(
            {
                "claim_text": claim.get("claim_text"),
                "evidence_status": claim.get("evidence_status"),
                "user_attitude": claim.get("user_attitude"),
                "importance": claim.get("importance"),
                "expression_role": claim.get("expression_role"),
                "confidence_level": claim.get("confidence_level"),
                "evidence_link_count": len(evidence_links),
                "claim_version_id": claim.get("claim_version_id"),
            }
        )
    return rows


def audit_finding_rows(audit_detail: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not audit_detail:
        return []
    return [
        {
            "severity": finding.get("severity"),
            "description": finding.get("description"),
            "affected_claims": ", ".join(finding.get("affected_claim_version_ids", [])),
            "recommended_revision": finding.get("recommended_revision") or "-",
        }
        for finding in audit_detail.get("audit_findings", [])
    ]


def proposal_rows(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "proposal_version_id": proposal.get("disposition_proposal_version_id"),
            "type": proposal.get("proposed_disposition_type"),
            "decision_status": proposal.get("user_decision_status"),
            "lifecycle_status": proposal.get("lifecycle_status"),
            "reason": proposal.get("reason"),
            "revision": proposal.get("revision"),
        }
        for proposal in proposals
    ]


def processing_job_rows(jobs: list[Job]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for job in jobs:
        rows.append(
            {
                "job_id": job.id,
                "type": job.type.value,
                "status": job.status.value,
                "progress": f"{job.progress:.0%}",
                "message": job.message or "-",
                "knowledge_item_id": _job_payload_or_result(job, "knowledge_item_id"),
                "asset_id": _job_payload_or_result(job, "asset_id"),
                "child_job_id": _job_payload_or_result(
                    job,
                    "child_job_id",
                    fallback_key="index_job_id",
                ),
                "error": job.error or "-",
                "updated_at": job.updated_at.isoformat(),
            }
        )
    return rows


def has_active_processing_jobs(jobs: list[Job]) -> bool:
    return any(job.status in ACTIVE_JOB_STATUSES for job in jobs)


def visible_processing_jobs(jobs: list[Job], *, include_history: bool = False) -> list[Job]:
    if include_history:
        return jobs
    return [job for job in jobs if job.status in ACTIVE_JOB_STATUSES]


def _job_payload_or_result(job: Job, key: str, *, fallback_key: str | None = None) -> str:
    value = _job_value(job, key)
    if value is None and fallback_key:
        value = _job_value(job, fallback_key)
    return str(value) if value is not None else "-"


def _job_value(job: Job, key: str) -> Any | None:
    value = job.result.get(key)
    if value is None:
        value = job.payload.get(key)
    return value


def feature_enabled(features: list[dict[str, Any]], flag_key: str) -> bool:
    return any(
        feature.get("flag_key") == flag_key and bool(feature.get("enabled"))
        for feature in features
    )


def render_core_alpha_workbench(
    api: WorkbenchApi | None = None,
    *,
    st_module: Any | None = None,
) -> None:
    st = st_module or _import_streamlit()
    st.title("Core Alpha 认知工作台")

    base_url = st.sidebar.text_input("Core Alpha API", "http://localhost:8000")
    actor_id = st.sidebar.text_input("用户标识", "user_local")
    api_client = api or CoreAlphaApiClient(base_url=base_url, actor_id=actor_id)

    selected_case_id = st.session_state.get("core_alpha_selected_case_id")
    snapshot = load_workbench_snapshot(api_client, selected_case_id=selected_case_id)
    for error in snapshot.errors:
        st.warning(error)

    case_options = {
        f"{case.get('title', '未命名')} · {case.get('research_case_id')}": case
        for case in snapshot.cases
    }
    if case_options:
        labels = list(case_options.keys())
        current_label = next(
            (
                label
                for label, case in case_options.items()
                if snapshot.selected_case
                and case.get("research_case_id")
                == snapshot.selected_case.get("research_case_id")
            ),
            labels[0],
        )
        selected_label = st.selectbox(
            "当前 ResearchCase",
            labels,
            index=labels.index(current_label),
        )
        selected_case_id = case_options[selected_label]["research_case_id"]
        st.session_state["core_alpha_selected_case_id"] = selected_case_id
        if (
            not snapshot.selected_case
            or snapshot.selected_case.get("research_case_id") != selected_case_id
        ):
            snapshot = load_workbench_snapshot(api_client, selected_case_id=selected_case_id)
    else:
        st.info("还没有 ResearchCase。")

    with st.expander("新建 ResearchCase", expanded=not snapshot.cases):
        with st.form("core_alpha_create_case"):
            title = st.text_input("标题")
            question = st.text_area("问题")
            submitted = st.form_submit_button("创建")
            if submitted:
                _run_ui_command(
                    st,
                    lambda: api_client.create_research_case(
                        title=title.strip(),
                        question_text=question.strip(),
                    ),
                    "已创建 ResearchCase。",
                )

    tabs = st.tabs(["知识范围", "判断与证据", "处置", "知识入库", "知识目录"])
    with tabs[0]:
        _render_scope_tab(st, api_client, snapshot)
    with tabs[1]:
        _render_judgment_tab(st, snapshot, base_url)
    with tabs[2]:
        _render_decision_tab(st, api_client, snapshot)
    with tabs[3]:
        _render_ingest_tab(st, snapshot)
    with tabs[4]:
        _render_catalog_tab(st, snapshot)


def _render_scope_tab(st: Any, api: WorkbenchApi, snapshot: WorkbenchSnapshot) -> None:
    case = snapshot.selected_case
    if not case:
        st.info("先创建或选择一个 ResearchCase。")
        return

    st.subheader("来源解析")
    with st.form("core_alpha_source_resolution"):
        raw_anchor = st.text_input("资料锚点")
        access_policy = st.selectbox("访问政策", ["required", "allowed", "excluded"])
        version_hint = st.text_input("版本提示（可选）")
        submitted = st.form_submit_button("解析来源")
        if submitted:
            _run_ui_command(
                st,
                lambda: api.create_source_resolution(
                    research_case_id=case["research_case_id"],
                    research_question_id=case["current_question_id"],
                    expected_revision=case["revision"],
                    raw_anchor=raw_anchor.strip(),
                    access_policy=access_policy,
                    version_hint=version_hint.strip() or None,
                ),
                "已提交来源解析。",
            )

    rows = source_resolution_rows(snapshot.source_resolutions)
    _dataframe_or_empty(st, rows, "暂无 SourceResolution。")

    st.subheader("当前 KnowledgeScope")
    st.caption("required / allowed / excluded 与 primary / comparison / background 是二维关系。")
    _dataframe_or_empty(st, binding_rows(snapshot.knowledge_scope), "暂无 KnowledgeScope。")


def _render_judgment_tab(st: Any, snapshot: WorkbenchSnapshot, base_url: str) -> None:
    judgment = snapshot.judgment_card
    state = judgment_state(judgment)
    _status_message(st, state["tone"], state["label"])
    if not judgment:
        st.info("当前 ResearchCase 还没有 JudgmentCard。")
        return

    st.subheader("判断摘要")
    st.write(judgment.get("summary"))
    st.caption(
        "用户接受 Claim 只表达用户态度，不会改变 evidence_status 或审计状态。"
    )
    _dataframe_or_empty(st, claim_rows(snapshot.claims_payload), "暂无 Claim。")

    st.subheader("审计")
    if snapshot.judgment_audit:
        st.json(snapshot.judgment_audit, expanded=False)
    _dataframe_or_empty(st, audit_finding_rows(snapshot.audit_detail), "暂无 AuditFinding。")

    st.subheader("DecisionFitness")
    if snapshot.decision_fitness:
        st.json(snapshot.decision_fitness, expanded=False)
    else:
        st.info("当前判断没有可用 DecisionFitness。")

    if snapshot.developer_diagnostics_enabled:
        run_id = judgment.get("research_run_id")
        if run_id:
            developer_url = (
                f"{base_url.rstrip('/')}/alpha/developer/research-runs/{run_id}/trace"
            )
            st.link_button("查看 Developer Trace", developer_url)


def _render_decision_tab(st: Any, api: WorkbenchApi, snapshot: WorkbenchSnapshot) -> None:
    judgment = snapshot.judgment_card
    proposals = snapshot.disposition_proposals
    adoptable = is_adoptable_judgment(judgment)
    if judgment and not adoptable:
        st.warning("当前判断不可采纳，不能进入基于可靠判断的行动处置。")
    _dataframe_or_empty(st, proposal_rows(proposals), "暂无 DispositionProposal。")
    if not proposals:
        return

    proposal = proposals[0]
    proposal_id = proposal["disposition_proposal_version_id"]
    revision = int(proposal["revision"])
    with st.form("core_alpha_accept_disposition"):
        st.write("接受当前处置建议")
        warning_ids = st.text_input("WarningAcknowledgement IDs（逗号分隔，可空）")
        submitted = st.form_submit_button("接受", disabled=not adoptable)
        if submitted and judgment:
            _run_ui_command(
                st,
                lambda: api.accept_disposition_proposal(
                    proposal_id,
                    expected_revision=revision,
                    judgment_card_version_id=proposal["judgment_card_version_id"],
                    decision_fitness_id=proposal["decision_fitness_id"],
                    warning_acknowledgement_ids=[
                        item.strip() for item in warning_ids.split(",") if item.strip()
                    ],
                ),
                "已确认 ResearchDisposition。",
            )

    with st.form("core_alpha_adjust_disposition"):
        st.write("调整处置建议")
        disposition_type = st.selectbox(
            "处置类型",
            [
                "continue_research",
                "defer_decision",
                "observe",
                "discard",
                "explicit_no_action",
                "knowledge_only_closure",
                "proceed_to_action",
            ],
        )
        reason = st.text_area("调整理由")
        submitted = st.form_submit_button("提交调整")
        if submitted:
            _run_ui_command(
                st,
                lambda: api.adjust_disposition_proposal(
                    proposal_id,
                    expected_revision=revision,
                    proposed_disposition_type=disposition_type,
                    reason=reason.strip(),
                ),
                "已调整 DispositionProposal。",
            )

    with st.form("core_alpha_reject_disposition"):
        st.write("拒绝当前处置建议")
        submitted = st.form_submit_button("拒绝")
        if submitted:
            _run_ui_command(
                st,
                lambda: api.reject_disposition_proposal(
                    proposal_id,
                    expected_revision=revision,
                ),
                "已拒绝 DispositionProposal。",
            )


def _render_catalog_tab(st: Any, snapshot: WorkbenchSnapshot) -> None:
    rows = [
        {
            "title": item.get("title"),
            "knowledge_item_id": item.get("knowledge_item_id"),
            "current_version": item.get("current_knowledge_item_version_id"),
            "language": item.get("language"),
            "status": item.get("lifecycle_status"),
        }
        for item in snapshot.knowledge_items
    ]
    _dataframe_or_empty(st, rows, "暂无 KnowledgeItem。")


def _render_ingest_tab(st: Any, snapshot: WorkbenchSnapshot) -> None:
    st.subheader("知识入库")
    st.caption(
        "支持文本、Markdown、PDF 和图片。上传后会提交异步处理任务：PDF 会先路由，"
        "扫描件或图片进入 OCR 队列，文本化后入库、切块并提交索引。OCR 需要单独启动 "
        "OCR worker。"
    )
    with st.form("core_alpha_ingest_upload"):
        uploaded = st.file_uploader(
            "上传文件",
            type=list(SUPPORTED_ASYNC_UPLOAD_EXTENSIONS),
        )
        title = st.text_input("标题（可选）")
        submitted = st.form_submit_button("提交处理")
        if not submitted:
            pass
        elif uploaded is None:
            st.warning("请先选择一个文件。")
        else:
            try:
                source, asset = IngestService().add_bytes(
                    filename=uploaded.name,
                    content=uploaded.getvalue(),
                    title=title.strip() or None,
                    note="Submitted from Core Alpha workbench.",
                )
                job = enqueue_document_pipeline(source, asset)
            except Exception as exc:  # noqa: BLE001 - show user-facing failure
                st.error(f"提交处理失败：{exc}")
            else:
                st.success(f"已提交处理任务：{job.id}")
                if asset.path.suffix.lower() == ".pdf":
                    st.caption("PDF 会先分析页面类型；扫描 PDF 需要 OCR worker。")
                elif asset.path.suffix.lower() in OCR_EXTENSIONS:
                    st.caption("图片类文件需要 OCR worker。")

    _render_reprocess_panel(st, snapshot)
    _render_processing_jobs(st)


def _render_reprocess_panel(st: Any, snapshot: WorkbenchSnapshot) -> None:
    st.subheader("重新处理已有知识条目")
    st.caption("重新处理会重新生成知识块，并在完成后提交当前条目的索引任务。")
    if not snapshot.knowledge_items:
        st.info("暂无可重新处理的 KnowledgeItem。")
        return
    item_by_id = {
        str(item["knowledge_item_id"]): item
        for item in snapshot.knowledge_items
        if item.get("knowledge_item_id")
    }
    selected_item_id = st.selectbox(
        "选择知识条目",
        options=list(item_by_id),
        format_func=lambda item_id: str(item_by_id[item_id].get("title") or item_id),
        key="core_alpha_reprocess_item",
    )
    if st.button("重新处理：切块并索引", key="core_alpha_reprocess_button"):
        try:
            job = enqueue_rebuild_chunks(selected_item_id)
        except Exception as exc:  # noqa: BLE001 - show user-facing failure
            st.error(f"提交重新处理失败：{exc}")
        else:
            st.success(f"已提交重新处理任务：{job.id}")


def _render_processing_jobs(st: Any) -> None:
    st.subheader("处理进度")
    include_history = st.checkbox(
        "显示历史处理记录",
        value=False,
        help="默认只显示 pending / running 任务，避免旧完成记录干扰当前 Golden Case 调试。",
    )
    try:
        jobs = [
            job
            for job in JobRepository().list(limit=100)
            if job.type in KNOWLEDGE_PROCESSING_JOB_TYPES
        ]
    except Exception as exc:  # noqa: BLE001 - show user-facing failure
        st.warning(f"读取处理进度失败：{exc}")
        return
    visible_jobs = visible_processing_jobs(jobs, include_history=include_history)
    empty_message = "暂无知识处理任务。" if include_history else "暂无正在处理的知识任务。"
    _dataframe_or_empty(st, processing_job_rows(visible_jobs), empty_message)
    if has_active_processing_jobs(jobs):
        st.caption("有任务正在处理，页面会每 5 秒刷新一次。")
        st.markdown(
            "<script>setTimeout(() => window.location.reload(), 5000);</script>",
            unsafe_allow_html=True,
        )


def _run_ui_command(st: Any, callback: Any, success_message: str) -> None:
    try:
        callback()
    except CoreAlphaApiError as exc:
        st.error(exc.message)
    else:
        st.success(success_message)


def _dataframe_or_empty(st: Any, rows: list[dict[str, Any]], empty_message: str) -> None:
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.info(empty_message)


def _status_message(st: Any, tone: str, message: str) -> None:
    if tone == "success":
        st.success(message)
    elif tone == "warning":
        st.warning(message)
    elif tone == "error":
        st.error(message)
    else:
        st.info(message)


def _select_case(
    api: WorkbenchApi,
    cases: list[dict[str, Any]],
    selected_case_id: str | None,
    errors: list[str],
) -> dict[str, Any] | None:
    if selected_case_id:
        return _safe_call(
            lambda: api.get_research_case(selected_case_id),
            errors,
            default=None,
        )
    return cases[0] if cases else None


def _safe_call(callback: Any, errors: list[str], *, default: Any) -> Any:
    try:
        return callback()
    except CoreAlphaApiError as exc:
        errors.append(exc.message)
        return default


def _as_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data", [])
    return data if isinstance(data, list) else []


def _as_dict(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data", {})
    return data if isinstance(data, dict) else {}


def _optional_dict(response: dict[str, Any]) -> dict[str, Any] | None:
    data = response.get("data")
    return data if isinstance(data, dict) else None


def _decode_json(payload: bytes) -> dict[str, Any]:
    if not payload:
        return {}
    decoded = json.loads(payload.decode("utf-8"))
    return decoded if isinstance(decoded, dict) else {}


def _import_streamlit() -> Any:
    import streamlit as st

    return st


def main() -> None:
    st = _import_streamlit()
    st.set_page_config(page_title="Core Alpha 工作台", layout="wide")
    render_core_alpha_workbench(st_module=st)


if __name__ == "__main__":
    main()
