"""Zhihu external echo adapter for the Yantie experience."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import Field

from metaos.yantie.schemas import EvidencePack, NonEmptyString, SourceType, YantieModel


class ExternalEchoStatus(str, Enum):
    ok = "ok"
    external_auth_missing = "external_auth_missing"
    external_unavailable = "external_unavailable"
    external_rate_limited = "external_rate_limited"


class ExternalEchoProvider(str, Enum):
    zhihu = "zhihu"
    global_search = "global"
    zhihu_hot_list = "zhihu_hot_list"
    zhida = "zhida"


class ZhihuAdapterConfig(YantieModel):
    access_secret: str | None = None
    base_url: NonEmptyString = "https://developer.zhihu.com"
    timeout_seconds: float = Field(default=8.0, gt=0, le=30)

    @property
    def is_configured(self) -> bool:
        return bool(self.access_secret and self.access_secret.strip())


class ExternalEchoItem(YantieModel):
    title: NonEmptyString
    url: NonEmptyString | None = None
    summary: NonEmptyString | None = None
    provider: ExternalEchoProvider
    source_boundary: SourceType = SourceType.external_echo
    rank: int = Field(ge=1)


class ExternalEchoPayload(YantieModel):
    provider: ExternalEchoProvider
    query: NonEmptyString | None = None
    status: ExternalEchoStatus
    items: list[ExternalEchoItem] = Field(default_factory=list)
    source_boundary: SourceType = SourceType.external_echo
    can_support_claims: bool = False
    writes_to_evidence_pack: bool = False
    message: NonEmptyString | None = None


class ZhidaRequest(YantieModel):
    prompt: NonEmptyString


class ExternalEchoError(RuntimeError):
    def __init__(
        self,
        *,
        code: ExternalEchoStatus,
        status_code: int,
        message: str,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


Clock = Callable[[], float]


class ZhihuExternalEchoAdapter:
    """Small REST adapter that keeps contemporary discussion outside evidence."""

    def __init__(
        self,
        config: ZhihuAdapterConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config or ZhihuAdapterConfig()
        self._transport = transport
        self._clock = clock or time.time

    @classmethod
    def from_env(cls) -> "ZhihuExternalEchoAdapter":
        return cls(
            ZhihuAdapterConfig(
                access_secret=os.getenv("YANTIE_ZHIHU_ACCESS_SECRET") or os.getenv("ZHIHU_ACCESS_SECRET"),
                base_url=os.getenv("YANTIE_ZHIHU_BASE_URL") or "https://developer.zhihu.com",
            )
        )

    @property
    def is_configured(self) -> bool:
        return self.config.is_configured

    def zhihu_search(self, query: str, *, count: int = 5) -> ExternalEchoPayload:
        raw = self._get(
            "/api/v1/content/zhihu_search",
            params={"q": query, "count": count},
        )
        return self._payload(
            provider=ExternalEchoProvider.zhihu,
            query=query,
            raw=raw,
            limit=count,
        )

    def global_search(self, query: str, *, count: int = 5, filter_value: str | None = None) -> ExternalEchoPayload:
        params: dict[str, Any] = {"q": query, "count": count}
        if filter_value:
            params["filter"] = filter_value
        raw = self._get("/api/v1/content/global_search", params=params)
        return self._payload(
            provider=ExternalEchoProvider.global_search,
            query=query,
            raw=raw,
            limit=count,
        )

    def hot_list(self, *, limit: int = 5) -> ExternalEchoPayload:
        raw = self._get("/api/v1/content/hot_list", params={"limit": limit})
        return self._payload(
            provider=ExternalEchoProvider.zhihu_hot_list,
            query=None,
            raw=raw,
            limit=limit,
        )

    def zhida(self, prompt: str) -> ExternalEchoPayload:
        raw = self._post(
            "/v1/chat/completions",
            json_body={
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            },
        )
        return self._payload(
            provider=ExternalEchoProvider.zhida,
            query=prompt,
            raw=raw,
            limit=1,
        )

    def _get(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, *, json_body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, json_body=json_body)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_auth_missing,
                status_code=401,
                message="Zhihu Access Secret is not configured; external echo is disabled.",
                retryable=False,
            )

        headers = {
            "Authorization": f"Bearer {self.config.access_secret}",
            "X-Request-Timestamp": str(int(self._clock())),
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                base_url=self.config.base_url.rstrip("/"),
                timeout=self.config.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, params=params, json=json_body, headers=headers)
        except httpx.HTTPError as exc:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_unavailable,
                status_code=503,
                message="Zhihu external echo is temporarily unavailable.",
                retryable=True,
                details={"error": exc.__class__.__name__},
            ) from exc

        if response.status_code == 429:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_rate_limited,
                status_code=429,
                message="Zhihu external echo is rate limited.",
                retryable=True,
            )
        if response.status_code in {401, 403}:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_auth_missing,
                status_code=401,
                message="Zhihu external echo authentication failed.",
                retryable=False,
            )
        if response.status_code >= 400:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_unavailable,
                status_code=503,
                message="Zhihu external echo returned an unavailable response.",
                retryable=True,
                details={"upstream_status": response.status_code},
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalEchoError(
                code=ExternalEchoStatus.external_unavailable,
                status_code=503,
                message="Zhihu external echo returned invalid JSON.",
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            return {"data": data}
        return data

    def _payload(
        self,
        *,
        provider: ExternalEchoProvider,
        query: str | None,
        raw: dict[str, Any],
        limit: int,
    ) -> ExternalEchoPayload:
        return ExternalEchoPayload(
            provider=provider,
            query=query,
            status=ExternalEchoStatus.ok,
            items=_normalize_items(raw, provider=provider, limit=limit),
            message="External echo only; not historical evidence.",
        )


def create_yantie_external_echo_router(
    *,
    pack: EvidencePack,
    adapter: ZhihuExternalEchoAdapter | None = None,
) -> APIRouter:
    external_adapter = adapter or ZhihuExternalEchoAdapter.from_env()
    router = APIRouter(prefix="/external", tags=["yantie-external-echo"])

    @router.get("/zhihu/search")
    def zhihu_search(
        q: str = Query(min_length=1),
        count: int = Query(default=5, ge=1, le=10),
    ) -> Any:
        return _adapter_response(pack, lambda: external_adapter.zhihu_search(q, count=count))

    @router.get("/global/search")
    def global_search(
        q: str = Query(min_length=1),
        count: int = Query(default=5, ge=1, le=10),
        filter: str | None = None,
    ) -> Any:
        return _adapter_response(pack, lambda: external_adapter.global_search(q, count=count, filter_value=filter))

    @router.get("/zhihu/hot-list")
    def hot_list(limit: int = Query(default=5, ge=1, le=10)) -> Any:
        return _adapter_response(pack, lambda: external_adapter.hot_list(limit=limit))

    @router.post("/zhihu/zhida")
    def zhida(payload: ZhidaRequest) -> Any:
        return _adapter_response(pack, lambda: external_adapter.zhida(payload.prompt))

    return router


def _adapter_response(pack: EvidencePack, call: Callable[[], ExternalEchoPayload]) -> Any:
    try:
        payload = call()
    except ExternalEchoError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code.value,
                    "message": exc.message,
                    "details": exc.details,
                    "retryable": exc.retryable,
                },
                "meta": _meta(pack),
            },
        )
    return {"data": payload.model_dump(mode="json"), "meta": _meta(pack)}


def _normalize_items(raw: dict[str, Any], *, provider: ExternalEchoProvider, limit: int) -> list[ExternalEchoItem]:
    rows = _extract_rows(raw)
    items: list[ExternalEchoItem] = []
    for index, row in enumerate(rows[:limit], start=1):
        item = _normalize_row(row, provider=provider, rank=index)
        if item is not None:
            items.append(item)
    return items


def _extract_rows(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict):
        return [{"summary": str(raw)}]

    data = raw.get("data", raw)
    if isinstance(data, dict):
        for key in ("items", "results", "list", "content"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return [data]
    if isinstance(data, list):
        return data
    return [{"summary": str(data)}]


def _normalize_row(row: Any, *, provider: ExternalEchoProvider, rank: int) -> ExternalEchoItem | None:
    if not isinstance(row, dict):
        text = str(row).strip()
        if not text:
            return None
        return ExternalEchoItem(
            title="External echo result",
            summary=text,
            provider=provider,
            rank=rank,
        )

    title = _first_text(row, "title", "name", "question", "headline") or "External echo result"
    summary = _first_text(row, "summary", "excerpt", "description", "content", "answer")
    url = _first_text(row, "url", "link", "target_url", "source_url")
    return ExternalEchoItem(
        title=title,
        url=url,
        summary=summary,
        provider=provider,
        rank=rank,
    )


def _first_text(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value is not None and not isinstance(value, (dict, list)):
            text = str(value).strip()
            if text:
                return text
    return None


def _meta(pack: EvidencePack) -> dict[str, Any]:
    return {
        "pack_id": pack.pack_id,
        "schema_version": pack.schema_version,
        "served_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


__all__ = [
    "ExternalEchoError",
    "ExternalEchoItem",
    "ExternalEchoPayload",
    "ExternalEchoProvider",
    "ExternalEchoStatus",
    "ZhihuAdapterConfig",
    "ZhihuExternalEchoAdapter",
    "ZhidaRequest",
    "create_yantie_external_echo_router",
]
